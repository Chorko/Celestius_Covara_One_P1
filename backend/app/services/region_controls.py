"""
Covara One — Region Controls & Behavioral Identity Service

Behavioral identity, region-based monitoring, and dynamic trust scoring
to detect fraud that bypasses location spoofing by targeting identity,
behavior, and regional anomalies.
"""

from datetime import datetime

# ── Historical Zone Affinity ─────────────────────────────────────────────


def check_zone_affinity(
    worker_context: dict, claim_zone_id: str = None
) -> dict:
    """
    Check what fraction of a worker's historical deliveries are in the
    claimed zone. A first-ever appearance in a red-alert zone precisely
    during a trigger event is treated as suspicious.
    """
    zone_history = worker_context.get("zone_delivery_counts", {})
    total_deliveries = sum(zone_history.values()) if zone_history else 0

    if total_deliveries == 0:
        return {
            "affinity_score": 0.0,
            "total_deliveries": 0,
            "zone_deliveries": 0,
            "first_time_in_zone": True,
            "risk_level": "elevated",
        }

    zone_deliveries = (
        zone_history.get(claim_zone_id, 0) if claim_zone_id else 0
    )
    affinity = zone_deliveries / total_deliveries

    first_time = zone_deliveries == 0

    if affinity >= 0.3:
        risk_level = "low"
    elif affinity >= 0.05:
        risk_level = "medium"
    elif first_time:
        risk_level = "high"
    else:
        risk_level = "elevated"

    return {
        "affinity_score": round(affinity, 4),
        "total_deliveries": total_deliveries,
        "zone_deliveries": zone_deliveries,
        "first_time_in_zone": first_time,
        "risk_level": risk_level,
    }


# ── Pre-Trigger Presence Requirement ─────────────────────────────────────


def check_pre_trigger_presence(
    worker_context: dict,
    trigger_context: dict = None,
    claim_zone_id: str = None,
) -> dict:
    """
    Worker must demonstrate presence or work continuity in/near the
    affected zone BEFORE or DURING the trigger window. A sudden first
    appearance exactly at event time is treated as suspicious.
    """
    trigger_start = None
    if trigger_context:
        ts = trigger_context.get("started_at") or trigger_context.get(
            "trigger_start"
        )
        if ts:
            try:
                trigger_start = datetime.fromisoformat(
                    str(ts).replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                pass

    # Check last activity in or near the zone
    last_activity_ts = worker_context.get("last_zone_activity_timestamp")
    last_activity_zone = worker_context.get("last_zone_activity_zone_id")

    if not last_activity_ts:
        return {
            "pre_trigger_present": False,
            "reason": "no_activity_history",
            "risk_level": "elevated",
        }

    try:
        if isinstance(last_activity_ts, str):
            activity_dt = datetime.fromisoformat(
                last_activity_ts.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        else:
            activity_dt = last_activity_ts
    except Exception:
        return {
            "pre_trigger_present": False,
            "reason": "unparseable_activity_timestamp",
            "risk_level": "uncertain",
        }

    same_zone = (
        (last_activity_zone == claim_zone_id)
        if claim_zone_id and last_activity_zone
        else None
    )

    # If we know the trigger start time, check if activity was before it
    if trigger_start:
        hours_before_trigger = (
            trigger_start - activity_dt
        ).total_seconds() / 3600
        # Active within 4h before trigger
        was_present_before = 0 <= hours_before_trigger <= 4

        if was_present_before and same_zone is not False:
            return {
                "pre_trigger_present": True,
                "hours_before_trigger": round(hours_before_trigger, 2),
                "same_zone": same_zone,
                "risk_level": "low",
            }
        elif hours_before_trigger < 0:
            # Activity was AFTER trigger — could be legitimate real-time
            return {
                "pre_trigger_present": True,
                "hours_before_trigger": round(hours_before_trigger, 2),
                "same_zone": same_zone,
                "risk_level": "low",
            }
        else:
            return {
                "pre_trigger_present": False,
                "hours_before_trigger": round(hours_before_trigger, 2),
                "same_zone": same_zone,
                "risk_level": (
                    "high" if hours_before_trigger > 12 else "medium"
                ),
            }

    # No trigger start time — just check recency of activity
    hours_since = (datetime.now(timezone.utc) - activity_dt).total_seconds() / 3600
    return {
        "pre_trigger_present": hours_since <= 4,
        "hours_since_activity": round(hours_since, 2),
        "same_zone": same_zone,
        "risk_level": (
            "low"
            if hours_since <= 4
            else ("medium" if hours_since <= 12 else "high")
        ),
    }


# ── Dynamic Trust Score Penalties ────────────────────────────────────────


def calculate_trust_penalty(
    worker_context: dict,
    anti_spoof_flags: list[str] = None,
    evidence_flags: list[str] = None,
) -> dict:
    """
    Accumulated behavioral anomalies feed back into the worker's trust_score.
    A lowered trust score increases their premium at renewal and defaults
    future claims to needs_review.

    Trust penalties are gradual and reversible — clean claim history
    restores the score over time.
    """
    current_trust = worker_context.get("trust_score", 0.75)
    flags = (anti_spoof_flags or []) + (evidence_flags or [])

    # Penalty per flag type
    PENALTY_MAP = {
        "exif_gps_mismatch": 0.05,
        "stale_evidence": 0.03,
        "vpn_datacenter_ip": 0.04,
        "new_device_requires_liveness": 0.02,
        "impossible_travel": 0.10,
        "emulator_detected": 0.12,
        "editor_detected": 0.04,
        "timestamp_chain_broken": 0.05,
        "gps_precision_suspicious": 0.03,
        "camera_device_mismatch": 0.06,
        "exif_mostly_missing": 0.02,
    }

    total_penalty = 0.0
    applied_penalties = []
    for flag in flags:
        # Handle flags with extra info (e.g. "editor_detected:photoshop")
        base_flag = flag.split(":")[0]
        penalty = PENALTY_MAP.get(base_flag, 0.01)
        total_penalty += penalty
        applied_penalties.append({"flag": flag, "penalty": penalty})

    # Cap total penalty at 0.30 per claim
    total_penalty = min(total_penalty, 0.30)

    new_trust = max(0.10, current_trust - total_penalty)

    return {
        "current_trust_score": current_trust,
        "total_penalty": round(total_penalty, 4),
        "new_trust_score": round(new_trust, 4),
        "applied_penalties": applied_penalties,
        "trust_degraded": total_penalty > 0,
    }


# ── Region-Based Claim Volume Monitoring ─────────────────────────────────


def check_zone_claim_volume(
    zone_claims_last_hour: int, zone_avg_hourly: float = 5.0
) -> dict:
    """
    Per-zone real-time claim rate tracking. Flags abnormal spikes.
    Mass-claim throttling: >50 claims from a single zone within 1 hour.
    """
    if zone_avg_hourly <= 0:
        zone_avg_hourly = 5.0

    ratio = zone_claims_last_hour / zone_avg_hourly

    if zone_claims_last_hour > 50:
        return {
            "spike_detected": True,
            "claims_last_hour": zone_claims_last_hour,
            "zone_avg_hourly": zone_avg_hourly,
            "ratio": round(ratio, 2),
            "action": "mass_claim_throttling",
            "risk_level": "critical",
        }
    elif ratio > 3.0:
        return {
            "spike_detected": True,
            "claims_last_hour": zone_claims_last_hour,
            "zone_avg_hourly": zone_avg_hourly,
            "ratio": round(ratio, 2),
            "action": "elevated_review",
            "risk_level": "high",
        }
    else:
        return {
            "spike_detected": False,
            "claims_last_hour": zone_claims_last_hour,
            "zone_avg_hourly": zone_avg_hourly,
            "ratio": round(ratio, 2),
            "action": "normal",
            "risk_level": "low",
        }


# ── Composite Region Controls Evaluation ─────────────────────────────────


def evaluate_region_controls(
    claim_data: dict,
    worker_context: dict,
    trigger_context: dict = None,
    zone_claims_last_hour: int = 0,
    zone_avg_hourly: float = 5.0,
) -> dict:
    """
    Runs all behavioral identity & region control checks.
    Returns composite results and risk assessment.
    """
    claim_zone_id = claim_data.get("zone_id")

    # Run all checks
    zone_affinity = check_zone_affinity(worker_context, claim_zone_id)
    pre_trigger = check_pre_trigger_presence(
        worker_context, trigger_context, claim_zone_id
    )
    zone_volume = check_zone_claim_volume(
        zone_claims_last_hour, zone_avg_hourly
    )

    # Collect risk signals
    risk_signals = []
    if zone_affinity["risk_level"] in ("high", "elevated"):
        risk_signals.append("low_zone_affinity")
    if zone_affinity.get("first_time_in_zone"):
        risk_signals.append("first_time_in_zone")
    if not pre_trigger.get("pre_trigger_present"):
        risk_signals.append("no_pre_trigger_presence")
    if zone_volume["spike_detected"]:
        risk_signals.append("zone_claim_spike")

    # Composite region risk score (0 = safe, 1 = high risk)
    risk_scores = {
        "low": 0.0,
        "medium": 0.3,
        "elevated": 0.5,
        "high": 0.7,
        "critical": 1.0,
        "uncertain": 0.4,
    }

    components = [
        (
            "zone_affinity",
            risk_scores.get(zone_affinity["risk_level"], 0.3),
            0.35,
        ),
        (
            "pre_trigger_presence",
            risk_scores.get(pre_trigger["risk_level"], 0.3),
            0.35,
        ),
        ("zone_volume", risk_scores.get(zone_volume["risk_level"], 0.0), 0.30),
    ]

    region_risk = sum(score * weight for _, score, weight in components)
    region_risk = round(max(0.0, min(1.0, region_risk)), 4)

    return {
        "region_risk_score": region_risk,
        "risk_signals": risk_signals,
        "signal_count": len(risk_signals),
        "checks": {
            "zone_affinity": zone_affinity,
            "pre_trigger_presence": pre_trigger,
            "zone_volume": zone_volume,
        },
        "requires_throttling": zone_volume.get("action")
        == "mass_claim_throttling",
    }
