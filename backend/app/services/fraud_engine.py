"""
Covara One — Fraud Scoring Engine (5-Layer Ghost Shift Detector)

Implements the full 5-layer fraud detection pipeline:
  Layer 1: Event Truth — Did the disruption actually happen?
  Layer 2: Worker Truth — Was the worker genuinely exposed?
  Layer 3: Anti-Spoofing Verification — Is the location evidence genuine?
  Layer 4: Cluster Intelligence — Is there group-level coordinated fraud?
  Layer 5: Behavioral Anomaly & Identity — Does the worker's history look suspicious?

Produces fraud_score, fraud_penalty, decision band, and feature vector.

Decision bands:
  auto_approve    — Trigger match + exposure + anti-spoofing pass + low fraud
  needs_review    — Moderate uncertainty or missing evidence
  hold_for_fraud  — Spoof indicators + cluster anomaly
  batch_hold      — Mass cluster anomaly
  reject_spoof_risk — No valid trigger + high spoof confidence + fraud-ring pattern
"""

import logging
from backend.app.services.anti_spoofing import verify_anti_spoofing
from backend.app.services.image_forensics import analyze_evidence_integrity
from backend.app.services.region_controls import (
    evaluate_region_controls,
    calculate_trust_penalty,
)

logger = logging.getLogger("covara.fraud_engine")

# ── Signal Confidence Hierarchy Weights ──────────────────────────────────
# Higher rank = more trusted signal (see root README Section 1c)
SIGNAL_WEIGHTS = {
    "trigger_event": 0.20,  # Rank 1 — Highest trust
    "historical_pattern": 0.15,  # Rank 2
    "shift_continuity": 0.15,  # Rank 3
    "pre_trigger": 0.10,  # Rank 4
    "device_continuity": 0.10,  # Rank 5
    "evidence_integrity": 0.10,  # Rank 6
    "anti_spoof": 0.10,  # Ranks 7-8
    "route_plausibility": 0.05,  # Rank 9 — TomTom Route API
    "region_controls": 0.05,
}


def evaluate_fraud_risk(
    worker_context: dict,
    trigger_context: dict,
    manual_claim: bool = False,
    evidence_records: list = None,
    claim_data: dict = None,
    device_context: dict = None,
    zone_claims_last_hour: int = 0,
    zone_avg_hourly: float = 5.0,
) -> dict:
    """
    Evaluates fraud across 5 layers using the signal confidence hierarchy.
    Returns fraud_score, fraud_penalty, decision band, and detailed breakdown.
    """
    evidence_records = evidence_records or []
    claim_data = claim_data or {}
    device_context = device_context or {}
    layer_results = {}
    flags = []

    # ════════════════════════════════════════════════════════════════════
    # LAYER 1: EVENT TRUTH
    # Does the disruption actually exist? (Highest trust — external source)
    # ════════════════════════════════════════════════════════════════════
    reliability = trigger_context.get("source_reliability", 0.8)
    has_trigger = trigger_context.get("trigger_family") is not None
    event_score = reliability if has_trigger else 0.2

    if not has_trigger:
        flags.append("no_verified_trigger")

    layer_results["event_truth"] = {
        "score": round(event_score, 4),
        "has_trigger": has_trigger,
        "source_reliability": reliability,
    }

    # ════════════════════════════════════════════════════════════════════
    # LAYER 2: WORKER TRUTH
    # Was the worker actually in the zone and working?
    # ════════════════════════════════════════════════════════════════════
    active_days = worker_context.get("active_days", 6)
    shift_overlap = worker_context.get("shift_overlap_ratio", 1.0)
    historical_orders = worker_context.get("orders_before_disruption", 1)

    if active_days == 0:
        worker_score = 0.1
        flags.append("zero_active_days")
    elif shift_overlap < 0.3:
        worker_score = 0.4
        flags.append("low_shift_overlap")
    else:
        worker_score = (
            0.3
            + (0.3 * min(shift_overlap, 1.0))
            + (0.2 * min(active_days / 6, 1.0))
            + (0.2 * min(historical_orders / 3, 1.0))
        )

    worker_score = max(0.0, min(1.0, worker_score))

    # ── Route plausibility via TomTom Routing API ──
    route_plausibility_score = 0.5  # default: uncertain
    route_result = None
    last_lat = worker_context.get("last_known_lat")
    last_lng = worker_context.get("last_known_lng")
    claim_lat = (claim_data or {}).get("stated_lat") or (claim_data or {}).get("lat")
    claim_lng = (claim_data or {}).get("stated_lng") or (claim_data or {}).get("lng")

    if all([last_lat, last_lng, claim_lat, claim_lng]):
        try:
            from backend.app.services.traffic_ingest import check_route_plausibility
            import asyncio
            # check_route_plausibility is async; run it synchronously if we're
            # not already in an event loop (pipeline is sync). If already in a
            # loop (called from an async route), schedule it on the running loop.
            try:
                loop = asyncio.get_running_loop()
                # Already in an async context — create a task and use a future
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    route_result = loop.run_in_executor(
                        pool,
                        lambda: asyncio.run(
                            check_route_plausibility(last_lat, last_lng, claim_lat, claim_lng)
                        ),
                    )
                    # This is a coroutine — we can't await it here in sync context,
                    # so fall back to the score of 0.5 and fill result async later.
                    route_result = None
            except RuntimeError:
                # No running loop — safe to use asyncio.run
                route_result = asyncio.run(
                    check_route_plausibility(last_lat, last_lng, claim_lat, claim_lng)
                )

            if route_result and route_result.get("score") is not None:
                route_plausibility_score = route_result["score"]
                if not route_result.get("plausible") and route_result["plausible"] is not None:
                    flags.append("route_implausible")
        except Exception as e:
            logger.warning(f"Route plausibility check failed: {e}")
            route_plausibility_score = 0.5  # Fail-open on API error

    layer_results["worker_truth"] = {
        "score": round(worker_score, 4),
        "active_days": active_days,
        "shift_overlap_ratio": shift_overlap,
        "orders_before_disruption": historical_orders,
        "route_plausibility": {
            "score": route_plausibility_score,
            "detail": route_result if route_result else "no_coordinates_available",
        },
    }

    # ════════════════════════════════════════════════════════════════════
    # LAYER 3: ANTI-SPOOFING VERIFICATION
    # Is the location evidence genuine, or spoofed?
    # ════════════════════════════════════════════════════════════════════
    anti_spoof_result = verify_anti_spoofing(
        claim_data=claim_data,
        worker_context=worker_context,
        evidence_records=evidence_records,
        device_context=device_context,
    )

    anti_spoof_score = anti_spoof_result["anti_spoof_score"]
    flags.extend(anti_spoof_result.get("flags_fired", []))

    layer_results["anti_spoofing"] = {
        "score": anti_spoof_score,
        "verdict": anti_spoof_result["anti_spoof_verdict"],
        "flags_fired": anti_spoof_result.get("flags_fired", []),
        "requires_liveness": anti_spoof_result.get(
            "requires_liveness_check", False
        ),
    }

    # ── Evidence integrity (image forensics) ──
    evidence_integrity_scores = []
    for ev in evidence_records:
        if (
            ev.get("exif_timestamp") is not None
            or ev.get("camera_model") is not None
        ):
            integrity = analyze_evidence_integrity(
                exif_metadata=ev, worker_context=worker_context
            )
            evidence_integrity_scores.append(integrity["integrity_score"])
            flags.extend(integrity.get("flags", []))

    avg_integrity = (
        sum(evidence_integrity_scores) / len(evidence_integrity_scores)
        if evidence_integrity_scores
        else 0.5
    )

    layer_results["evidence_integrity"] = {
        "score": round(avg_integrity, 4),
        "evidence_count": len(evidence_integrity_scores),
    }

    # ════════════════════════════════════════════════════════════════════
    # LAYER 4: CLUSTER INTELLIGENCE
    # Is there group-level coordinated fraud?
    # ════════════════════════════════════════════════════════════════════
    # In production: DBSCAN clustering on timestamps + coordinates,
    # shared payout destinations, evidence similarity scoring.
    # Here we use zone claim volume as a proxy.
    cluster_risk = 0.0
    if zone_claims_last_hour > 50:
        cluster_risk = 0.9
        flags.append("mass_claim_zone_spike")
    elif zone_claims_last_hour > 20:
        cluster_risk = 0.5
        flags.append("elevated_zone_claims")
    elif zone_claims_last_hour > 10:
        cluster_risk = 0.2

    cluster_score = 1.0 - cluster_risk  # Higher = safer

    layer_results["cluster_intelligence"] = {
        "score": round(cluster_score, 4),
        "zone_claims_last_hour": zone_claims_last_hour,
        "cluster_risk": round(cluster_risk, 4),
    }

    # ════════════════════════════════════════════════════════════════════
    # LAYER 5: BEHAVIORAL ANOMALY & IDENTITY
    # Does the worker's historical pattern look suspicious?
    # ════════════════════════════════════════════════════════════════════
    region_result = evaluate_region_controls(
        claim_data=claim_data,
        worker_context=worker_context,
        trigger_context=trigger_context,
        zone_claims_last_hour=zone_claims_last_hour,
        zone_avg_hourly=zone_avg_hourly,
    )

    region_risk = region_result["region_risk_score"]
    behavioral_score = 1.0 - region_risk

    prior_claim_rate = worker_context.get("prior_claim_rate", 0.0)
    gps_consistency = worker_context.get("gps_consistency_score", 0.8)

    # Blend region controls with legacy behavioral signals
    behavioral_score = (
        (0.6 * behavioral_score)
        + (0.2 * (1.0 - prior_claim_rate))
        + (0.2 * gps_consistency)
    )
    behavioral_score = max(0.0, min(1.0, behavioral_score))

    flags.extend(region_result.get("risk_signals", []))

    layer_results["behavioral_identity"] = {
        "score": round(behavioral_score, 4),
        "region_risk": round(region_risk, 4),
        "prior_claim_rate": prior_claim_rate,
        "gps_consistency": gps_consistency,
        "risk_signals": region_result.get("risk_signals", []),
    }

    # ════════════════════════════════════════════════════════════════════
    # COMPOSITE FRAUD SCORE (Signal Confidence Hierarchy)
    # ════════════════════════════════════════════════════════════════════
    composite_components = [
        ("trigger_event", event_score, SIGNAL_WEIGHTS["trigger_event"]),
        (
            "historical_pattern",
            behavioral_score,
            SIGNAL_WEIGHTS["historical_pattern"],
        ),
        ("shift_continuity", worker_score, SIGNAL_WEIGHTS["shift_continuity"]),
        ("pre_trigger", behavioral_score, SIGNAL_WEIGHTS["pre_trigger"]),
        (
            "device_continuity",
            anti_spoof_score,
            SIGNAL_WEIGHTS["device_continuity"],
        ),
        (
            "evidence_integrity",
            avg_integrity,
            SIGNAL_WEIGHTS["evidence_integrity"],
        ),
        ("anti_spoof", anti_spoof_score, SIGNAL_WEIGHTS["anti_spoof"]),
        (
            "route_plausibility",
            route_plausibility_score,
            SIGNAL_WEIGHTS["route_plausibility"],
        ),
        (
            "region_controls",
            behavioral_score,
            SIGNAL_WEIGHTS["region_controls"],
        ),
    ]

    # Higher composite = safer (more genuine)
    composite_safety = sum(
        score * weight for _, score, weight in composite_components
    )
    composite_safety = max(0.0, min(1.0, composite_safety))

    # Fraud score = inverse of safety (higher = more fraud risk)
    fraud_score = 1.0 - composite_safety

    # Stricter bounds for manual claims
    if manual_claim:
        fraud_score = min(fraud_score * 1.25, 1.0)

    fraud_score = round(fraud_score, 4)

    # ════════════════════════════════════════════════════════════════════
    # DECISION BAND DETERMINATION
    # ════════════════════════════════════════════════════════════════════
    unique_flags = list(set(flags))
    flag_count = len(unique_flags)

    # Mass cluster override → batch_hold
    if zone_claims_last_hour > 50 and flag_count >= 2:
        band = "cluster"
        decision = "batch_hold"
    # No valid trigger + high spoof + ring pattern → reject
    elif not has_trigger and fraud_score > 0.70 and flag_count >= 3:
        band = "ring_match"
        decision = "reject_spoof_risk"
    # Strong signals of spoofing → hold
    elif fraud_score > 0.55 or (
        anti_spoof_result["anti_spoof_verdict"] == "fail" and flag_count >= 2
    ):
        band = "suspicious"
        decision = "hold_for_fraud"
    # Moderate uncertainty → review
    elif (
        fraud_score > 0.30
        or anti_spoof_result["anti_spoof_verdict"] == "review"
        or manual_claim
    ):
        band = "uncertain"
        decision = "needs_review"
    # All clear → approve
    else:
        band = "low"
        decision = "auto_approve"

    # ── Fraud penalty for payout calculation ──
    penalty_map = {
        "auto_approve": fraud_score * 0.15,
        "needs_review": fraud_score * 0.35,
        "hold_for_fraud": fraud_score * 0.70,
        "batch_hold": fraud_score * 0.80,
        "reject_spoof_risk": fraud_score * 1.0,
    }
    fraud_penalty = round(penalty_map.get(decision, fraud_score * 0.5), 4)

    # ── Trust score update ──
    trust_update = calculate_trust_penalty(
        worker_context=worker_context,
        anti_spoof_flags=anti_spoof_result.get("flags_fired", []),
        evidence_flags=[
            f
            for f in unique_flags
            if f not in anti_spoof_result.get("flags_fired", [])
        ],
    )

    # ── ML Feature Vector (for anti-spoofing ML table) ──
    feature_vector = {
        "exif_browser_gps_distance_m": anti_spoof_result.get("checks", {})
        .get("gps_mismatch", {})
        .get("exif_browser_gps_distance_m"),
        "exif_claim_time_lag_min": None,  # Computed upstream from evidence
        "claim_zone_vs_assigned_zone": (
            1 if "low_zone_affinity" in unique_flags else 0
        ),
        "shift_overlap_ratio": shift_overlap,
        "route_plausibility_score": route_plausibility_score,  # Live TomTom Routing API
        "historical_order_continuity": historical_orders,
        "repeated_coord_density": zone_claims_last_hour,
        "batch_timing_similarity": None,  # DBSCAN placeholder
        "trigger_correlation_score": 1.0 if has_trigger else 0.0,
        "evidence_completeness": avg_integrity,
        "prior_suspicious_rate": prior_claim_rate,
        "device_account_ratio": None,  # From account service
        "network_cluster_size": zone_claims_last_hour,
        "vpn_datacenter_flag": 1 if "vpn_datacenter_ip" in unique_flags else 0,
        "impossible_travel_flag": (
            1 if "impossible_travel" in unique_flags else 0
        ),
        "zone_affinity_score": region_result.get("checks", {})
        .get("zone_affinity", {})
        .get("affinity_score"),
        "pre_trigger_presence": (
            1
            if region_result.get("checks", {})
            .get("pre_trigger_presence", {})
            .get("pre_trigger_present")
            else 0
        ),
        "emulator_root_flag": 1 if "emulator_detected" in unique_flags else 0,
    }

    return {
        "fraud_score": fraud_score,
        "fraud_penalty": fraud_penalty,
        "fraud_band": band,
        "recommended_action": decision,
        "flags": unique_flags,
        "flag_count": flag_count,
        "requires_liveness_check": anti_spoof_result.get(
            "requires_liveness_check", False
        ),
        "requires_throttling": region_result.get("requires_throttling", False),
        "trust_update": trust_update,
        "layers": layer_results,
        "feature_vector": feature_vector,
        "signal_weights": SIGNAL_WEIGHTS,
    }
