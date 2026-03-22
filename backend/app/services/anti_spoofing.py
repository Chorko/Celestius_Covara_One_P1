"""
DEVTrails — Anti-Spoofing Verification Service (Layer 3)

Multi-signal cross-validation to detect sophisticated GPS spoofing,
VPN/proxy abuse, emulator usage, and identity misuse.

This layer was added in response to the coordinated GPS-spoofing
syndicate threat. Simple GPS verification is obsolete.
"""

import ipaddress
from datetime import datetime
from backend.app.services.geo_verification import calculate_distance_km

# ── Known VPN / datacenter / TOR IP ranges (sample CIDRs) ──────────────
# In production, this would be a maintained database (e.g., ip2proxy,
# ipinfo.io)
DATACENTER_CIDRS = [
    "10.0.0.0/8",  # Private — should never appear as a public claim IP
    "172.16.0.0/12",  # Private
    "192.168.0.0/16",  # Private
    "100.64.0.0/10",  # CGNAT — common VPN indicator
    "198.51.100.0/24",  # Documentation range (test)
]

# Known emulator user-agent / device fingerprint patterns
EMULATOR_MARKERS = [
    "BlueStacks",
    "Nox",
    "Genymotion",
    "MEmu",
    "LDPlayer",
    "google_sdk",
    "generic_x86",
    "vbox86p",
    "Andy",
    "Xamarin",
]

# ── EXIF vs Browser GPS Cross-Check ─────────────────────────────────────


def check_exif_gps_mismatch(
    evidence_records: list[dict], claim_lat: float, claim_lng: float
) -> dict:
    """
    Compare EXIF GPS from evidence photos against the browser/device GPS
    reported with the claim. Spoofing apps change device GPS but cannot
    alter already-captured EXIF metadata.
    """
    mismatches = []
    best_distance_m = None

    for ev in evidence_records:
        exif_lat = ev.get("exif_lat")
        exif_lng = ev.get("exif_lng")
        if (
            exif_lat is not None
            and exif_lng is not None
            and claim_lat is not None
            and claim_lng is not None
        ):
            dist_km = calculate_distance_km(
                exif_lat, exif_lng, claim_lat, claim_lng
            )
            dist_m = dist_km * 1000
            if best_distance_m is None or dist_m < best_distance_m:
                best_distance_m = dist_m
            if dist_m > 500:
                mismatches.append(
                    {
                        "evidence_id": ev.get("id"),
                        "exif_gps": (exif_lat, exif_lng),
                        "claim_gps": (claim_lat, claim_lng),
                        "distance_m": round(dist_m, 1),
                        "flag": "exif_browser_gps_mismatch",
                    }
                )

    has_exif_gps = any(
        ev.get("exif_lat") is not None for ev in evidence_records
    )

    return {
        "has_exif_gps": has_exif_gps,
        "exif_browser_gps_distance_m": (
            round(best_distance_m, 1) if best_distance_m is not None else None
        ),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "flag": len(mismatches) > 0,
    }


# ── EXIF Timestamp Freshness ────────────────────────────────────────────


def check_exif_timestamp_freshness(
    evidence_records: list[dict], claim_timestamp: str = None
) -> dict:
    """
    Validate that evidence photos were captured within the claim window.
    Reused evidence from old events fails freshness checks.
    """
    stale_evidence = []
    freshness_scores = []

    now = datetime.now(timezone.utc)
    claim_dt = None
    if claim_timestamp:
        try:
            claim_dt = datetime.fromisoformat(
                claim_timestamp.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except Exception:
            claim_dt = now

    for ev in evidence_records:
        exif_ts = ev.get("exif_timestamp")
        if not exif_ts:
            freshness_scores.append(0.5)  # Missing EXIF = uncertain, not fraud
            continue

        try:
            dt_str = exif_ts.replace(":", "-", 2)
            exif_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            ref_dt = claim_dt or now
            lag_hours = abs((ref_dt - exif_dt).total_seconds()) / 3600

            if lag_hours <= 2:
                freshness_scores.append(1.0)
            elif lag_hours <= 24:
                freshness_scores.append(0.7)
            elif lag_hours <= 72:
                freshness_scores.append(0.3)
                stale_evidence.append(
                    {
                        "evidence_id": ev.get("id"),
                        "lag_hours": round(lag_hours, 1),
                    }
                )
            else:
                freshness_scores.append(0.0)
                stale_evidence.append(
                    {
                        "evidence_id": ev.get("id"),
                        "lag_hours": round(lag_hours, 1),
                    }
                )
        except Exception:
            freshness_scores.append(0.5)

    avg_freshness = (
        sum(freshness_scores) / len(freshness_scores)
        if freshness_scores
        else 0.5
    )

    return {
        "freshness_score": round(avg_freshness, 4),
        "stale_count": len(stale_evidence),
        "stale_evidence": stale_evidence,
        "flag": avg_freshness < 0.4,
    }


# ── VPN / Datacenter / TOR IP Detection ─────────────────────────────────


def check_vpn_datacenter_ip(claim_ip: str) -> dict:
    """
    Check if the claim originates from a known VPN endpoint, TOR exit node,
    or cloud datacenter IP. Real gig workers use mobile carrier IPs
    (Jio, Airtel, Vi). This is a SUPPORTING signal, not standalone rejection.
    """
    if not claim_ip:
        return {
            "vpn_flag": False,
            "reason": "no_ip_provided",
            "risk_level": "unknown",
        }

    try:
        ip_obj = ipaddress.ip_address(claim_ip)
        for cidr_str in DATACENTER_CIDRS:
            if ip_obj in ipaddress.ip_network(cidr_str, strict=False):
                return {
                    "vpn_flag": True,
                    "reason": f"IP {claim_ip} in datacenter/VPN range {cidr_str}",
                    "risk_level": "elevated",
                }
    except ValueError:
        return {
            "vpn_flag": False,
            "reason": "invalid_ip",
            "risk_level": "unknown",
        }

    return {"vpn_flag": False, "reason": "carrier_ip", "risk_level": "low"}


# ── Device Continuity Check ──────────────────────────────────────────────


def check_device_continuity(
    worker_context: dict, claim_device_id: str = None
) -> dict:
    """
    Verify the same device is consistently associated with this worker account.
    Fraud rings rotate devices across accounts.
    """
    registered_device = worker_context.get("registered_device_id")
    device_history = worker_context.get("device_history", [])

    if not claim_device_id:
        return {
            "device_match": None,
            "new_device": False,
            "risk_level": "uncertain",
        }

    is_match = (
        (claim_device_id == registered_device) if registered_device else False
    )
    is_new = (
        (claim_device_id not in device_history) if device_history else True
    )

    # New device during red-alert → triggers liveness check
    risk_level = "low"
    if not is_match and is_new:
        risk_level = "high"  # New unregistered device
    elif not is_match:
        risk_level = "medium"  # Known device but not primary

    return {
        "device_match": is_match,
        "new_device": is_new,
        "device_count_on_account": (
            len(set(device_history)) if device_history else 0
        ),
        "risk_level": risk_level,
        "requires_liveness": risk_level == "high",
    }


# ── Movement Plausibility (Impossible Travel) ───────────────────────────


def check_movement_plausibility(
    worker_context: dict,
    claim_lat: float,
    claim_lng: float,
    claim_timestamp: str = None,
) -> dict:
    """
    Check if the worker could have physically traveled from their last
    known location to the claim location in the elapsed time.
    Max realistic speed for urban India: 60 km/h.
    """
    MAX_SPEED_KMH = 60.0

    last_lat = worker_context.get("last_known_lat")
    last_lng = worker_context.get("last_known_lng")
    last_ts = worker_context.get("last_known_timestamp")

    if not all([last_lat, last_lng, last_ts, claim_lat, claim_lng]):
        return {
            "impossible_travel": False,
            "reason": "insufficient_data",
            "risk_level": "uncertain",
        }

    try:
        if isinstance(last_ts, str):
            last_dt = datetime.fromisoformat(
                last_ts.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        else:
            last_dt = last_ts  # type: ignore

        now = datetime.now(timezone.utc)
        if claim_timestamp:
            try:
                claim_dt = datetime.fromisoformat(
                    claim_timestamp.replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                claim_dt = now
        else:
            claim_dt = now

        elapsed_hours = max((claim_dt - last_dt).total_seconds() / 3600, 0.001)
        distance_km = calculate_distance_km(
            last_lat, last_lng, claim_lat, claim_lng  # type: ignore
        )
        required_speed = distance_km / elapsed_hours

        impossible = required_speed > MAX_SPEED_KMH

        return {
            "impossible_travel": impossible,
            "distance_km": round(distance_km, 2),
            "elapsed_hours": round(elapsed_hours, 4),
            "required_speed_kmh": round(required_speed, 1),
            "max_allowed_speed_kmh": MAX_SPEED_KMH,
            "risk_level": "critical" if impossible else "low",
        }
    except Exception:
        return {
            "impossible_travel": False,
            "reason": "calculation_error",
            "risk_level": "uncertain",
        }


# ── Emulator / Root Detection ────────────────────────────────────────────


def check_emulator_signals(device_context: dict) -> dict:
    """
    Detect rooted devices, emulator fingerprints, mock-location permission,
    developer-mode, and sensor inconsistency.
    """
    flags = []

    device_name = (device_context.get("device_model") or "").lower()
    user_agent = (device_context.get("user_agent") or "").lower()

    for marker in EMULATOR_MARKERS:
        if marker.lower() in device_name or marker.lower() in user_agent:
            flags.append(f"emulator_marker:{marker}")

    if device_context.get("is_rooted"):
        flags.append("rooted_device")
    if device_context.get("mock_location_enabled"):
        flags.append("mock_location_enabled")
    if device_context.get("developer_mode"):
        flags.append("developer_mode_active")
    if not device_context.get("has_accelerometer", True):
        flags.append("missing_accelerometer")
    if not device_context.get("has_gyroscope", True):
        flags.append("missing_gyroscope")

    return {
        "emulator_detected": len(flags) > 0,
        "flags": flags,
        "flag_count": len(flags),
        "risk_level": (
            "critical"
            if len(flags) >= 2
            else ("elevated" if len(flags) == 1 else "low")
        ),
    }


# ── Composite Anti-Spoofing Verification ─────────────────────────────────


def verify_anti_spoofing(
    claim_data: dict,
    worker_context: dict,
    evidence_records: list[dict],
    device_context: dict = None,
) -> dict:
    """
    Layer 3 of the 5-Layer Ghost Shift Detector.
    Runs all anti-spoofing checks and produces a composite score.
    """
    claim_lat = claim_data.get("stated_lat") or claim_data.get("lat")
    claim_lng = claim_data.get("stated_lng") or claim_data.get("lng")
    claim_ts = claim_data.get("created_at") or claim_data.get(
        "claim_timestamp"
    )
    claim_ip = claim_data.get("client_ip")
    claim_device_id = claim_data.get("device_id")

    # Run all checks
    gps_check = check_exif_gps_mismatch(evidence_records, claim_lat, claim_lng)  # type: ignore
    freshness_check = check_exif_timestamp_freshness(
        evidence_records, claim_ts
    )
    vpn_check = check_vpn_datacenter_ip(claim_ip)  # type: ignore
    device_check = check_device_continuity(worker_context, claim_device_id)
    movement_check = check_movement_plausibility(
        worker_context, claim_lat, claim_lng, claim_ts  # type: ignore
    )
    emulator_check = check_emulator_signals(device_context or {})

    # ── Composite anti-spoof score (0.0 = definitely spoofed, 1.0 = genuine) ──
    # Weighted by signal confidence hierarchy
    score_components = []

    # GPS mismatch (weight: 0.20)
    if gps_check["has_exif_gps"]:
        gps_score = 0.0 if gps_check["flag"] else 1.0
    else:
        gps_score = 0.5  # Missing EXIF GPS = uncertain
    score_components.append(("exif_gps_match", gps_score, 0.20))

    # Freshness (weight: 0.15)
    score_components.append(
        ("evidence_freshness", freshness_check["freshness_score"], 0.15)
    )

    # VPN (weight: 0.10 — low trust, supporting signal only)
    vpn_score = 0.2 if vpn_check["vpn_flag"] else 1.0
    score_components.append(("network_legitimacy", vpn_score, 0.10))

    # Device continuity (weight: 0.15)
    dev_scores = {"low": 1.0, "medium": 0.6, "high": 0.2, "uncertain": 0.5}
    score_components.append(
        (
            "device_continuity",
            dev_scores.get(device_check["risk_level"], 0.5),
            0.15,
        )
    )

    # Movement plausibility (weight: 0.25 — high trust)
    if movement_check.get("impossible_travel"):
        move_score = 0.0
    elif movement_check.get("risk_level") == "uncertain":
        move_score = 0.5
    else:
        move_score = 1.0
    score_components.append(("movement_plausibility", move_score, 0.25))

    # Emulator detection (weight: 0.15)
    emu_scores = {"low": 1.0, "elevated": 0.3, "critical": 0.0}
    score_components.append(
        (
            "emulator_check",
            emu_scores.get(emulator_check["risk_level"], 0.5),
            0.15,
        )
    )

    # Weighted composite
    composite = sum(score * weight for _, score, weight in score_components)
    composite = round(max(0.0, min(1.0, composite)), 4)

    # Determine anti-spoof verdict
    flags_fired = []
    if gps_check["flag"]:
        flags_fired.append("exif_gps_mismatch")
    if freshness_check["flag"]:
        flags_fired.append("stale_evidence")
    if vpn_check["vpn_flag"]:
        flags_fired.append("vpn_datacenter_ip")
    if device_check.get("requires_liveness"):
        flags_fired.append("new_device_requires_liveness")
    if movement_check.get("impossible_travel"):
        flags_fired.append("impossible_travel")
    if emulator_check["emulator_detected"]:
        flags_fired.append("emulator_detected")

    if composite >= 0.7:
        verdict = "pass"
    elif composite >= 0.4:
        verdict = "review"
    else:
        verdict = "fail"

    return {
        "anti_spoof_score": composite,
        "anti_spoof_verdict": verdict,
        "flags_fired": flags_fired,
        "flag_count": len(flags_fired),
        "requires_liveness_check": device_check.get(
            "requires_liveness", False
        ),
        "checks": {
            "gps_mismatch": gps_check,
            "freshness": freshness_check,
            "vpn_detection": vpn_check,
            "device_continuity": device_check,
            "movement_plausibility": movement_check,
            "emulator_detection": emulator_check,
        },
        "score_breakdown": {
            name: round(score, 4) for name, score, _ in score_components
        },
    }
