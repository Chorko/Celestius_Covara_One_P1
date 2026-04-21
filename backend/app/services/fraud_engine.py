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
    "historical_pattern": 0.14,  # Rank 2
    "shift_continuity": 0.14,  # Rank 3
    "pre_trigger": 0.10,  # Rank 4
    "device_continuity": 0.10,  # Rank 5
    "evidence_integrity": 0.09,  # Rank 6
    "anti_spoof": 0.10,  # Ranks 7-8
    "route_plausibility": 0.04,  # Rank 9 — TomTom Route API
    "region_controls": 0.04,
    "cluster_intelligence": 0.05,
}


def _run_route_plausibility_sync(
    last_lat: float,
    last_lng: float,
    claim_lat: float,
    claim_lng: float,
) -> dict | None:
    """
    Run async route plausibility safely from both sync and async contexts.
    """
    from backend.app.services.traffic_ingest import check_route_plausibility
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            check_route_plausibility(last_lat, last_lng, claim_lat, claim_lng)
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            lambda: asyncio.run(
                check_route_plausibility(last_lat, last_lng, claim_lat, claim_lng)
            )
        )
        return future.result(timeout=3.0)


def _append_calibration_rule(
    rules: list[dict],
    rule: str,
    delta: float,
    category: str,
    reason: str,
) -> None:
    rules.append(
        {
            "rule": rule,
            "delta": round(delta, 4),
            "category": category,
            "reason": reason,
        }
    )


def _compute_fraud_confidence(
    has_trigger: bool,
    evidence_count: int,
    context_present: bool,
    route_result: dict | None,
    signal_confidence: str | None,
) -> float:
    confidence = 0.35
    if has_trigger:
        confidence += 0.20
    if evidence_count > 0:
        confidence += 0.15
    if context_present:
        confidence += 0.12
    if route_result and route_result.get("score") is not None:
        confidence += 0.08

    if signal_confidence == "high":
        confidence += 0.10
    elif signal_confidence == "medium":
        confidence += 0.06

    return round(max(0.0, min(1.0, confidence)), 4)


def _top_signal_contributors(
    composite_components: list[tuple[str, float, float]],
    max_items: int = 4,
) -> list[dict]:
    contributors = []
    for name, score, weight in composite_components:
        risk_impact = max(0.0, (1.0 - score) * weight)
        contributors.append(
            {
                "signal": name,
                "score": round(score, 4),
                "weight": round(weight, 4),
                "risk_impact": round(risk_impact, 4),
            }
        )

    return sorted(
        contributors,
        key=lambda item: item["risk_impact"],
        reverse=True,
    )[:max_items]


def _decision_reason_codes(
    decision: str,
    *,
    has_trigger: bool,
    manual_claim: bool,
    anti_spoof_verdict: str,
    context_present: bool,
    fraud_score: float,
    cluster_risk: float,
    flags: list[str],
) -> list[str]:
    codes: list[str] = []

    if not has_trigger:
        codes.append("trigger_unverified")
    if manual_claim:
        codes.append("manual_claim_strict_mode")
    if anti_spoof_verdict == "fail":
        codes.append("anti_spoof_failed")
    elif anti_spoof_verdict == "review":
        codes.append("anti_spoof_uncertain")
    if manual_claim and not context_present:
        codes.append("missing_signed_device_context")
    if "attestation_failed" in flags:
        codes.append("attestation_failed")
    if "emulator_detected" in flags:
        codes.append("emulator_detected")
    if "new_device_requires_liveness" in flags:
        codes.append("liveness_stepup_required")
    if (
        "high_risk_device_trust" in flags
        or "integrity_verdict_high_risk" in flags
    ):
        codes.append("device_high_risk")
    if "mass_claim_zone_spike" in flags or "zone_claim_spike" in flags:
        codes.append("zone_claim_velocity_spike")

    if cluster_risk >= 0.90:
        codes.append("cluster_risk_critical")
    elif cluster_risk >= 0.50:
        codes.append("cluster_risk_elevated")

    if fraud_score >= 0.55:
        codes.append("fraud_score_critical")
    elif fraud_score >= 0.30:
        codes.append("fraud_score_moderate")

    if decision == "batch_hold":
        codes.append("decision_batch_hold")
    elif decision == "hold_for_fraud":
        codes.append("decision_hold_for_fraud")
    elif decision == "reject_spoof_risk":
        codes.append("decision_reject_spoof_risk")
    elif decision == "needs_review":
        codes.append("decision_needs_review")
    else:
        codes.append("decision_auto_approve")

    deduped = []
    for code in codes:
        if code not in deduped:
            deduped.append(code)
    return deduped


def _risk_tier(decision: str, fraud_score: float, cluster_risk: float) -> str:
    if (
        decision in {"reject_spoof_risk", "batch_hold"}
        or fraud_score >= 0.85
        or cluster_risk >= 0.90
    ):
        return "critical"
    if decision == "hold_for_fraud" or fraud_score >= 0.60:
        return "high"
    if decision == "needs_review" or fraud_score >= 0.35:
        return "elevated"
    if fraud_score >= 0.20:
        return "guarded"
    return "low"


def _build_risk_action_pack(
    *,
    decision: str,
    fraud_score: float,
    cluster_risk: float,
    has_trigger: bool,
    manual_claim: bool,
    anti_spoof_verdict: str,
    flags: list[str],
    requires_liveness_check: bool,
    throttle_strategy: dict,
) -> dict:
    risk_tier = _risk_tier(decision, fraud_score, cluster_risk)
    priority_map = {
        "critical": ("p0", 15),
        "high": ("p1", 60),
        "elevated": ("p2", 240),
        "guarded": ("p3", 720),
        "low": ("p4", 1440),
    }
    review_priority, review_sla_minutes = priority_map[risk_tier]

    challenges: list[str] = []
    if requires_liveness_check or "new_device_requires_liveness" in flags:
        challenges.append("selfie_liveness_stepup")
    if anti_spoof_verdict == "fail" or "attestation_failed" in flags:
        challenges.append("device_attestation_rebind")
    if (
        "emulator_detected" in flags
        or "high_risk_device_trust" in flags
        or "integrity_verdict_high_risk" in flags
    ):
        challenges.append("device_integrity_manual_review")
    if manual_claim and not has_trigger:
        challenges.append("trigger_source_verification")
    if manual_claim and "location_permission_none" in flags:
        challenges.append("location_permission_recheck")
    if bool(throttle_strategy.get("enabled")):
        challenges.append("zone_throttle_cooldown")

    deduped_challenges: list[str] = []
    for challenge in challenges:
        if challenge not in deduped_challenges:
            deduped_challenges.append(challenge)

    controls = [
        {
            "control": "manual_reviewer_assignment",
            "reason": "Prioritize deterministic reviewer ownership and SLA tracking.",
        }
    ]
    if anti_spoof_verdict == "fail":
        controls.append(
            {
                "control": "device_reverification_gate",
                "reason": "Block auto-routing until device trust controls pass.",
            }
        )
    if manual_claim and not has_trigger:
        controls.append(
            {
                "control": "external_trigger_recheck",
                "reason": "No verified trigger found for manual claim declaration.",
            }
        )
    if bool(throttle_strategy.get("enabled")):
        controls.append(
            {
                "control": "zone_velocity_guardrail",
                "reason": str(
                    throttle_strategy.get("reason_code")
                    or "zone_claim_velocity_elevated"
                ),
            }
        )

    return {
        "risk_tier": risk_tier,
        "review_priority": review_priority,
        "review_sla_minutes": review_sla_minutes,
        "required_challenges": deduped_challenges,
        "recommended_controls": controls,
        "throttle_strategy": throttle_strategy,
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
    recent_claims_batch: list = None,
    claim_mode: str = "manual",
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
            route_result = _run_route_plausibility_sync(
                last_lat,
                last_lng,
                claim_lat,
                claim_lng,
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
        "device_trust_score": anti_spoof_result.get("device_trust_score"),
        "device_trust_tier": anti_spoof_result.get("device_trust_tier"),
        "signal_confidence": anti_spoof_result.get("signal_confidence"),
        "attestation_verdict": anti_spoof_result.get("attestation_verdict"),
        "requires_liveness": anti_spoof_result.get(
            "requires_liveness_check", False
        ),
    }

    # ── Evidence integrity (image forensics) ──
    evidence_integrity_scores = []
    ai_probabilities: list[float] = []
    synthid_detection_count = 0
    c2pa_detection_count = 0
    for ev in evidence_records:
        if (
            ev.get("exif_timestamp") is not None
            or ev.get("camera_model") is not None
        ):
            integrity = analyze_evidence_integrity(
                exif_metadata=ev,
                file_bytes=ev.get("_file_bytes"),
                worker_context=worker_context,
            )
            evidence_integrity_scores.append(integrity["integrity_score"])
            flags.extend(integrity.get("flags", []))

            ai_check = (integrity.get("checks") or {}).get("ai_generation") or {}
            try:
                ai_probabilities.append(float(ai_check.get("ai_generated_probability") or 0.0))
            except (TypeError, ValueError):
                ai_probabilities.append(0.0)

            if ai_check.get("synthid_detected"):
                synthid_detection_count += 1
            if ai_check.get("c2pa_metadata_found"):
                c2pa_detection_count += 1

    avg_integrity = (
        sum(evidence_integrity_scores) / len(evidence_integrity_scores)
        if evidence_integrity_scores
        else 0.5
    )

    layer_results["evidence_integrity"] = {
        "score": round(avg_integrity, 4),
        "evidence_count": len(evidence_integrity_scores),
        "max_ai_generated_probability": round(max(ai_probabilities), 4)
        if ai_probabilities
        else 0.0,
        "synthid_detection_count": synthid_detection_count,
        "c2pa_detection_count": c2pa_detection_count,
    }

    # ════════════════════════════════════════════════════════════════════
    # LAYER 4: CLUSTER INTELLIGENCE
    # Is there group-level coordinated fraud?
    # ════════════════════════════════════════════════════════════════════
    # In production: DBSCAN clustering on timestamps + coordinates,
    # shared payout destinations, evidence similarity scoring.
    cluster_risk = 0.0
    batch_timing_similarity = None

    if recent_claims_batch and len(recent_claims_batch) >= 3:
        from datetime import datetime, timezone
        import math
        import statistics

        data: list[tuple[float, float, float]] = []
        for c in recent_claims_batch:
            lat = c.get("stated_lat") or c.get("lat")
            lng = c.get("stated_lng") or c.get("lng")
            ts = c.get("created_at") or c.get("timestamp") or c.get("claimed_at")
            if lat is None or lng is None or ts is None:
                continue

            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                mins = dt.timestamp() / 60.0
                # Normalize minutes to lat/lng scale (1 min ~ 0.001 deg)
                data.append((float(lat), float(lng), mins * 0.001))
            except Exception:
                continue

        claim_lat = (claim_data or {}).get("stated_lat") or (claim_data or {}).get("lat")
        claim_lng = (claim_data or {}).get("stated_lng") or (claim_data or {}).get("lng")
        claim_ts = (
            (claim_data or {}).get("created_at")
            or (claim_data or {}).get("timestamp")
            or (claim_data or {}).get("claimed_at")
        )

        claim_point: tuple[float, float, float] | None = None
        if claim_lat is not None and claim_lng is not None:
            try:
                if claim_ts:
                    claim_dt = datetime.fromisoformat(str(claim_ts).replace("Z", "+00:00"))
                else:
                    claim_dt = datetime.now(timezone.utc)
                claim_mins = claim_dt.timestamp() / 60.0
                claim_point = (float(claim_lat), float(claim_lng), claim_mins * 0.001)
            except Exception:
                claim_point = None

        if len(data) >= 3 and claim_point is not None:
            try:
                import numpy as np
                from sklearn.cluster import DBSCAN
                from sklearn.metrics import pairwise_distances

                X = np.array(data)
                db = DBSCAN(eps=0.005, min_samples=3).fit(X)
                labels = db.labels_

                if np.any(labels != -1):
                    claim_arr = np.array([list(claim_point)])
                    dists = pairwise_distances(claim_arr, X[labels != -1])
                    if float(dists.min()) < 0.005:
                        cluster_risk = 0.95
                        flags.append("dbscan_fraud_cluster_match")
                        flags.append("mass_claim_zone_spike")

                        nearest_idx = int(np.argmin(pairwise_distances(claim_arr, X)))
                        cluster_id = labels[nearest_idx]
                        if cluster_id != -1:
                            cluster_times = X[labels == cluster_id][:, 2] / 0.001
                            batch_timing_similarity = float(np.std(cluster_times))
            except ImportError:
                eps = 0.005
                min_samples = 3

                def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
                    return math.sqrt(
                        ((a[0] - b[0]) ** 2)
                        + ((a[1] - b[1]) ** 2)
                        + ((a[2] - b[2]) ** 2)
                    )

                matched_cluster_indices: list[int] = []
                for idx, point in enumerate(data):
                    neighbors = [
                        j
                        for j, other in enumerate(data)
                        if _distance(point, other) <= eps
                    ]
                    if len(neighbors) >= min_samples and _distance(claim_point, point) <= eps:
                        matched_cluster_indices = neighbors
                        break

                if matched_cluster_indices:
                    cluster_risk = 0.90
                    flags.append("cluster_density_fallback_match")
                    flags.append("mass_claim_zone_spike")

                    cluster_times = [
                        data[idx][2] / 0.001 for idx in matched_cluster_indices
                    ]
                    if len(cluster_times) >= 2:
                        batch_timing_similarity = float(
                            statistics.pstdev(cluster_times)
                        )
            except Exception as e:
                logger.warning(f"Cluster intelligence check failed: {e}")

    # Fallback to volume proxy if DBSCAN didn't flag
    if cluster_risk == 0.0:
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

    unique_flags = sorted(set(flags))
    flag_count = len(unique_flags)

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
        (
            "cluster_intelligence",
            cluster_score,
            SIGNAL_WEIGHTS["cluster_intelligence"],
        ),
    ]

    # Higher composite = safer (more genuine)
    composite_safety = sum(
        score * weight for _, score, weight in composite_components
    )
    composite_safety = max(0.0, min(1.0, composite_safety))

    # Fraud score = inverse of safety (higher = more fraud risk)
    base_fraud_score = 1.0 - composite_safety

    # Stricter bounds for manual claims
    if manual_claim:
        base_fraud_score = min(base_fraud_score * 1.25, 1.0)

    calibration_rules: list[dict] = []
    device_trust_tier = anti_spoof_result.get("device_trust_tier")
    attestation_verdict = anti_spoof_result.get("attestation_verdict")
    signal_confidence = anti_spoof_result.get("signal_confidence")

    emu_checks = anti_spoof_result.get("checks", {}).get("emulator_detection", {})
    context_present = bool(emu_checks.get("context_present"))

    if manual_claim and len(evidence_records) == 0:
        _append_calibration_rule(
            calibration_rules,
            "manual_claim_missing_evidence",
            0.06,
            "evidence",
            "Manual claim submitted without supporting evidence.",
        )

    if manual_claim and not context_present:
        _append_calibration_rule(
            calibration_rules,
            "manual_claim_missing_signed_context",
            0.05,
            "device",
            "Manual claim submitted without signed device context.",
        )

    if anti_spoof_result.get("anti_spoof_verdict") == "fail":
        _append_calibration_rule(
            calibration_rules,
            "anti_spoof_verdict_fail",
            0.12,
            "anti_spoof",
            "Anti-spoofing checks indicate likely manipulation.",
        )

    if device_trust_tier == "high_risk":
        _append_calibration_rule(
            calibration_rules,
            "device_trust_high_risk",
            0.14,
            "device",
            "Device trust posture is high risk.",
        )
    elif device_trust_tier == "low" and context_present:
        _append_calibration_rule(
            calibration_rules,
            "device_trust_low_signed_context",
            0.05,
            "device",
            "Signed device context reports low trust score.",
        )

    if attestation_verdict in {"failed", "invalid", "device_not_trusted"}:
        _append_calibration_rule(
            calibration_rules,
            "attestation_failed",
            0.10,
            "device",
            "Device attestation failed or indicates untrusted device.",
        )

    if (
        manual_claim
        and anti_spoof_result.get("anti_spoof_verdict") == "review"
        and signal_confidence in {None, "low", "missing", "unknown"}
    ):
        _append_calibration_rule(
            calibration_rules,
            "manual_claim_low_signal_confidence",
            0.04,
            "confidence",
            "Manual claim has uncertain anti-spoof outcome and low signal confidence.",
        )

    if manual_claim and has_trigger and route_plausibility_score < 0.25:
        _append_calibration_rule(
            calibration_rules,
            "manual_claim_route_implausible",
            0.06,
            "movement",
            "Route plausibility score is critically low for the submitted claim context.",
        )

    if (
        ("low_zone_affinity" in unique_flags)
        and ("no_pre_trigger_presence" in unique_flags)
        and manual_claim
    ):
        _append_calibration_rule(
            calibration_rules,
            "identity_context_mismatch",
            0.08,
            "behavior",
            "Worker lacks historical zone affinity and pre-trigger presence.",
        )

    if (not has_trigger) and (
        ("impossible_travel" in unique_flags)
        or ("route_implausible" in unique_flags)
    ):
        _append_calibration_rule(
            calibration_rules,
            "unverified_event_with_implausible_route",
            0.10,
            "event",
            "No verified trigger combined with implausible movement signal.",
        )

    if cluster_risk >= 0.90:
        _append_calibration_rule(
            calibration_rules,
            "cluster_risk_critical",
            0.12,
            "cluster",
            "Claim appears inside a high-risk temporal/spatial claim cluster.",
        )
    elif cluster_risk >= 0.50:
        _append_calibration_rule(
            calibration_rules,
            "cluster_risk_elevated",
            0.05,
            "cluster",
            "Zone exhibits elevated coordinated-claim behavior.",
        )

    if prior_claim_rate >= 0.70:
        _append_calibration_rule(
            calibration_rules,
            "high_prior_claim_rate",
            0.08,
            "behavior",
            "Historical claim frequency is significantly elevated.",
        )
    elif prior_claim_rate >= 0.45:
        _append_calibration_rule(
            calibration_rules,
            "moderate_prior_claim_rate",
            0.04,
            "behavior",
            "Historical claim frequency is moderately elevated.",
        )

    if (
        has_trigger
        and not manual_claim
        and flag_count == 0
        and signal_confidence == "high"
        and attestation_verdict == "passed"
    ):
        _append_calibration_rule(
            calibration_rules,
            "trusted_auto_signal_stack",
            -0.05,
            "confidence",
            "High-confidence trigger and trusted device context reduce risk.",
        )

    adjustment_total = sum(rule["delta"] for rule in calibration_rules)
    fraud_score = max(0.0, min(1.0, base_fraud_score + adjustment_total))

    fraud_score = round(fraud_score, 4)
    fraud_confidence = _compute_fraud_confidence(
        has_trigger=has_trigger,
        evidence_count=len(evidence_records),
        context_present=context_present,
        route_result=route_result,
        signal_confidence=signal_confidence,
    )

    # ════════════════════════════════════════════════════════════════════
    # DECISION BAND DETERMINATION
    # ════════════════════════════════════════════════════════════════════
    # Mass cluster override → batch_hold
    if zone_claims_last_hour > 50 and flag_count >= 2:
        band = "cluster"
        decision = "batch_hold"
    # Device-compromised unverified manual claims are high-confidence spoof risk.
    elif (
        not has_trigger
        and anti_spoof_result["anti_spoof_verdict"] == "fail"
        and (
            "emulator_detected" in unique_flags
            or "attestation_failed" in unique_flags
            or "integrity_verdict_high_risk" in unique_flags
        )
    ):
        band = "ring_match"
        decision = "reject_spoof_risk"
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

    if (
        decision == "needs_review"
        and fraud_score >= 0.48
        and (
            anti_spoof_result["anti_spoof_verdict"] == "fail"
            or "attestation_failed" in unique_flags
            or "high_risk_device_trust" in unique_flags
        )
    ):
        band = "suspicious"
        decision = "hold_for_fraud"

    # ── Claim-mode-aware override for zero-touch auto-claims ──────────
    # Auto-triggered parametric claims have NO evidence photos and NO
    # device context by design — the anti-spoof layer will always return
    # "review" because it scores missing data as "uncertain" (0.5).
    # For API-verified trigger events with clean fraud signals, we allow
    # auto-approval since there is nothing to spoof (no human filed claim).
    if (
        claim_mode == "trigger_auto"
        and has_trigger
        and reliability >= 0.80
        and fraud_score < 0.25
        and flag_count == 0
        and decision == "needs_review"
        and anti_spoof_result["anti_spoof_verdict"] != "fail"
    ):
        band = "low"
        decision = "auto_approve"
        logger.info(
            "Auto-claim override: trigger_auto + verified event + "
            f"clean fraud ({fraud_score}) → auto_approve"
        )

    # ── Fraud penalty for payout calculation ──
    penalty_map = {
        "auto_approve": fraud_score * 0.15,
        "needs_review": fraud_score * 0.35,
        "hold_for_fraud": fraud_score * 0.70,
        "batch_hold": fraud_score * 0.80,
        "reject_spoof_risk": fraud_score * 1.0,
    }
    fraud_penalty = round(penalty_map.get(decision, fraud_score * 0.5), 4)

    risk_action_pack = _build_risk_action_pack(
        decision=decision,
        fraud_score=fraud_score,
        cluster_risk=cluster_risk,
        has_trigger=has_trigger,
        manual_claim=manual_claim,
        anti_spoof_verdict=anti_spoof_result["anti_spoof_verdict"],
        flags=unique_flags,
        requires_liveness_check=anti_spoof_result.get(
            "requires_liveness_check", False
        ),
        throttle_strategy=region_result.get("throttle_strategy", {}),
    )

    decision_explainability = {
        "decision_reason_codes": _decision_reason_codes(
            decision,
            has_trigger=has_trigger,
            manual_claim=manual_claim,
            anti_spoof_verdict=anti_spoof_result["anti_spoof_verdict"],
            context_present=context_present,
            fraud_score=fraud_score,
            cluster_risk=cluster_risk,
            flags=unique_flags,
        ),
        "top_signal_contributors": _top_signal_contributors(composite_components),
        "top_calibration_impacts": sorted(
            calibration_rules,
            key=lambda rule: abs(rule.get("delta", 0.0)),
            reverse=True,
        )[:3],
        "risk_action_pack": risk_action_pack,
    }

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
        "batch_timing_similarity": batch_timing_similarity,
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
        "device_trust_score": anti_spoof_result.get("device_trust_score"),
        "device_context_present": (
            1
            if anti_spoof_result.get("checks", {})
            .get("emulator_detection", {})
            .get("context_present")
            else 0
        ),
        "device_signature_verified": (
            1
            if anti_spoof_result.get("checks", {})
            .get("emulator_detection", {})
            .get("signature_verified")
            else 0
        ),
        "attestation_failed_flag": (
            1 if "attestation_failed" in unique_flags else 0
        ),
    }

    device_trust = {
        "device_trust_score": anti_spoof_result.get("device_trust_score"),
        "device_trust_tier": anti_spoof_result.get("device_trust_tier"),
        "signal_confidence": anti_spoof_result.get("signal_confidence"),
        "attestation_verdict": anti_spoof_result.get("attestation_verdict"),
        "risk_signals": anti_spoof_result.get("flags_fired", []),
    }

    return {
        "fraud_score": fraud_score,
        "base_fraud_score": round(base_fraud_score, 4),
        "fraud_confidence": fraud_confidence,
        "fraud_penalty": fraud_penalty,
        "fraud_band": band,
        "recommended_action": decision,
        "flags": unique_flags,
        "flag_count": flag_count,
        "risk_action_pack": risk_action_pack,
        "decision_explainability": decision_explainability,
        "calibration": {
            "adjustment_total": round(adjustment_total, 4),
            "applied_rules": sorted(
                calibration_rules,
                key=lambda rule: abs(rule.get("delta", 0.0)),
                reverse=True,
            ),
        },
        "requires_liveness_check": anti_spoof_result.get(
            "requires_liveness_check", False
        ),
        "requires_throttling": region_result.get("requires_throttling", False),
        "trust_update": trust_update,
        "device_trust": device_trust,
        "layers": layer_results,
        "feature_vector": feature_vector,
        "signal_weights": SIGNAL_WEIGHTS,
    }
