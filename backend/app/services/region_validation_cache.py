"""
Covara One — Region Validation Cache Service (Gap §4.3)

Provides fast-lane approval for claims in zones with validated
regional incidents. Reduces repeated manual review but NEVER
bypasses individual anti-fraud checks.

Liquidity protection: if an extreme spike of same-zone claims
appears in a short window, the platform switches from individual
auto-release to cluster-level validation.
"""

from datetime import datetime, timedelta

# ── Thresholds ────────────────────────────────────────────────────────
# Number of trusted workers needed to auto-validate an incident
TRUSTED_WORKER_THRESHOLD = 3

# Maximum claims per zone per hour before triggering cluster spike
CLUSTER_SPIKE_THRESHOLD = 50

# Time window for matching incidents to claims
INCIDENT_MATCH_WINDOW_HOURS = 6


def check_regional_incident(
    zone_id: str,
    trigger_family: str,
    claim_timestamp: str,
    validated_incidents: list[dict],
) -> dict | None:
    """
    Check if a validated regional incident exists for the given
    zone, trigger family, and time window.

    Returns the matching incident dict if found, else None.

    IMPORTANT: Even when a fast-lane match is found, the caller
    must still run individual anti-fraud checks (identity continuity,
    evidence mismatch, spoof-risk markers, device continuity).
    """
    try:
        claim_dt = datetime.fromisoformat(claim_timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None

    for incident in validated_incidents:
        if (
            incident.get("zone_id") == zone_id
            and incident.get("trigger_family") == trigger_family
        ):
            try:
                inc_start = datetime.fromisoformat(
                    incident["incident_start"].replace("Z", "+00:00")
                )
                inc_end = incident.get("incident_end")
                if inc_end:
                    inc_end = datetime.fromisoformat(
                        inc_end.replace("Z", "+00:00")
                    )
                else:
                    # Default: incident window extends INCIDENT_MATCH_WINDOW_HOURS
                    inc_end = inc_start + timedelta(
                        hours=INCIDENT_MATCH_WINDOW_HOURS
                    )

                if inc_start <= claim_dt <= inc_end:
                    return incident
            except (ValueError, KeyError):
                continue

    return None


def is_cluster_spike(
    zone_claims_last_hour: int,
    threshold: int = CLUSTER_SPIKE_THRESHOLD,
) -> bool:
    """
    Determine if the current claim volume represents a cluster spike.

    If True, fast-lane auto-release should be paused and claims
    should be batched for cluster-level validation to protect the
    liquidity pool.
    """
    return zone_claims_last_hour >= threshold


def should_fast_lane(
    zone_id: str,
    trigger_family: str,
    claim_timestamp: str,
    validated_incidents: list[dict],
    zone_claims_last_hour: int = 0,
) -> dict:
    """
    Determine if a claim is eligible for fast-lane processing.

    Returns:
        {
            "eligible": bool,
            "reason": str,
            "incident": dict | None,
            "cluster_spike": bool,
        }
    """
    # Check for cluster spike first — overrides fast-lane
    cluster_spike = is_cluster_spike(zone_claims_last_hour)
    if cluster_spike:
        return {
            "eligible": False,
            "reason": (
                f"Cluster spike detected: {zone_claims_last_hour} claims/hour "
                f"in zone. Switched to cluster-level validation to protect "
                f"liquidity pool."
            ),
            "incident": None,
            "cluster_spike": True,
        }

    # Check for matching validated incident
    incident = check_regional_incident(
        zone_id, trigger_family, claim_timestamp, validated_incidents
    )

    if incident:
        if incident.get("cluster_spike_detected"):
            return {
                "eligible": False,
                "reason": (
                    "Regional incident found but cluster spike flag is active. "
                    "Claims require cluster-level validation."
                ),
                "incident": incident,
                "cluster_spike": True,
            }

        return {
            "eligible": True,
            "reason": (
                f"Regional incident validated via "
                f"{incident.get('validation_source', 'unknown')}. "
                f"Fast-lane: skipping repeated manual review. "
                f"Individual fraud checks still apply."
            ),
            "incident": incident,
            "cluster_spike": False,
        }

    return {
        "eligible": False,
        "reason": "No validated regional incident found for this zone/trigger/time.",
        "incident": None,
        "cluster_spike": False,
    }


def apply_post_approval_penalty(
    worker_trust_score: float,
    fraud_severity: str = "minor",
) -> dict:
    """
    Calculate trust score penalty for post-approval fraud detection (Gap §4.4).

    Severity levels:
        - minor:  -0.05 trust score (e.g. evidence quality issue)
        - moderate: -0.15 trust score (e.g. timing inconsistency)
        - severe: -0.30 trust score + legal escalation flag
        - critical: -0.50 trust score + immediate account review

    Returns:
        {
            "new_trust_score": float,
            "penalty_applied": float,
            "legal_escalation": bool,
            "account_review": bool,
        }
    """
    PENALTY_MAP = {
        "minor": 0.05,
        "moderate": 0.15,
        "severe": 0.30,
        "critical": 0.50,
    }

    penalty = PENALTY_MAP.get(fraud_severity, 0.10)
    new_score = max(0.0, round(worker_trust_score - penalty, 2))

    return {
        "new_trust_score": new_score,
        "penalty_applied": penalty,
        "legal_escalation": fraud_severity in ("severe", "critical"),
        "account_review": fraud_severity == "critical",
    }
