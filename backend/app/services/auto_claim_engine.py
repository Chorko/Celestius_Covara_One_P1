"""
Covara One — Zero-Touch Auto-Claim Engine

The parametric insurance core: when a trigger event is created,
this engine automatically finds every eligible worker and processes
their claim WITHOUT any manual filing by the worker.

Flow:
  1. Triggered by: POST /claims/auto-process (admin/cron)
  2. Query recent trigger_events (last N hours, severity: claim/escalation)
  3. For each trigger event:
     a. Find workers with active policies in the affected zone
     b. Verify shift overlap (were they working during disruption?)
     c. Run the full claim pipeline (fraud check, payout calc)
     d. Insert claim into manual_claims with claim_mode='trigger_auto'
     e. Insert payout_recommendation
      f. Emit claim.auto_processed event for async consumers
  4. Return processing summary

This is the feature that separates parametric insurance from
traditional insurance. Workers get paid automatically.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from backend.app.config import settings
from backend.app.services.event_bus.outbox import enqueue_domain_event, persist_claim_with_outbox
from backend.app.services.version_governance import (
    attach_version_context,
    resolve_decision_versions,
)

logger = logging.getLogger("covara.auto_claim_engine")

# How far back to look for unprocessed trigger events
TRIGGER_LOOKBACK_HOURS = 6

# Minimum severity to auto-process (watch = alert only, claim/escalation = pay)
AUTO_PROCESS_SEVERITIES = {"claim", "escalation"}


async def run_auto_claim_engine(sb, lookback_hours: int = TRIGGER_LOOKBACK_HOURS) -> dict:
    """
    Main entry point for the zero-touch auto-claim engine.

    Args:
        sb: Supabase admin client
        lookback_hours: How far back to scan for unprocessed triggers

    Returns:
        Summary dict with counts and per-claim results
    """
    summary = {
        "triggers_scanned": 0,
        "workers_eligible": 0,
        "claims_auto_approved": 0,
        "claims_needs_review": 0,
        "claims_held": 0,
        "claims_rejected": 0,
        "duplicates_skipped": 0,
        "errors": [],
        "results": [],
    }

    # ── Step 1: Fetch recent trigger events ──────────────────────────
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()

    try:
        triggers_resp = (
            sb.table("trigger_events")
            .select("*")
            .in_("severity_band", list(AUTO_PROCESS_SEVERITIES))
            .gte("started_at", cutoff)
            .execute()
        )
        trigger_events = triggers_resp.data or []
    except Exception as e:
        summary["errors"].append(f"Failed to fetch trigger events: {e}")
        return summary

    summary["triggers_scanned"] = len(trigger_events)
    logger.info(f"Auto-claim engine: {len(trigger_events)} trigger events to process")

    if not trigger_events:
        logger.info("No trigger events in window — nothing to process")
        return summary

    # ── Step 2: Process each trigger event ──────────────────────────
    for trigger in trigger_events:
        zone_id = trigger.get("zone_id")
        trigger_id = trigger.get("id")
        trigger_family = trigger.get("trigger_family")
        trigger_code = trigger.get("trigger_code")
        severity_band = trigger.get("severity_band")
        city = trigger.get("city", "")
        started_at = trigger.get("started_at")
        observed_value = trigger.get("observed_value")
        threshold_label = trigger.get("official_threshold_label", "")

        if not zone_id or not trigger_id:
            continue

        logger.info(f"Processing trigger {trigger_code} in zone {zone_id} ({city})")

        try:
            await enqueue_domain_event(
                sb=sb,
                event_type="trigger.processing_started",
                key=str(zone_id),
                source="auto_claim_engine.run_auto_claim_engine",
                payload={
                    "trigger_id": trigger_id,
                    "zone_id": zone_id,
                    "trigger_code": trigger_code,
                    "trigger_family": trigger_family,
                    "severity_band": severity_band,
                    "city": city,
                },
            )
        except Exception as e:
            logger.warning("Event publish failed for trigger.processing_started: %s", e)

        # ── Step 3: Find eligible workers ────────────────────────────
        eligible_workers = await _find_eligible_workers(
            sb, zone_id=zone_id, trigger_started_at=started_at
        )
        summary["workers_eligible"] += len(eligible_workers)

        # ── Step 4: Process each eligible worker ─────────────────────
        for worker in eligible_workers:
            result = await _process_worker_claim(
                sb,
                worker=worker,
                trigger=trigger,
                trigger_id=trigger_id,
                trigger_code=trigger_code,
                trigger_family=trigger_family,
                severity_band=severity_band,
                city=city,
                observed_value=observed_value,
                threshold_label=threshold_label,
            )

            # Count by decision
            decision = result.get("decision", "error")
            if decision == "auto_approve":
                summary["claims_auto_approved"] += 1
            elif decision == "needs_review":
                summary["claims_needs_review"] += 1
            elif decision in ("hold_for_fraud", "batch_hold"):
                summary["claims_held"] += 1
            elif decision == "reject_spoof_risk":
                summary["claims_rejected"] += 1
            elif decision == "skipped_duplicate":
                summary["duplicates_skipped"] += 1

            if result.get("error"):
                summary["errors"].append(result["error"])
            else:
                summary["results"].append(result)

    logger.info(
        f"Auto-claim engine complete: "
        f"{summary['claims_auto_approved']} approved, "
        f"{summary['claims_needs_review']} review, "
        f"{summary['claims_held']} held, "
        f"{summary['claims_rejected']} rejected, "
        f"{summary['duplicates_skipped']} duplicates skipped"
    )

    try:
        await enqueue_domain_event(
            sb=sb,
            event_type="claims.auto_process.summary",
            key="auto_claim_engine",
            source="auto_claim_engine.run_auto_claim_engine",
            payload=summary,
        )
    except Exception as e:
        logger.warning("Event publish failed for claims.auto_process.summary: %s", e)

    return summary


async def _find_eligible_workers(
    sb, zone_id: str, trigger_started_at: str
) -> list[dict]:
    """
    Find workers who:
    1. Have an active policy in this zone
    2. Have a shift overlapping with the trigger event time
    3. Have NOT already had a claim auto-created for this zone+time
    """
    try:
        # Find workers with active policies
        policies_resp = (
            sb.table("policies")
            .select("worker_profile_id, plan_type, coverage_amount, premium_amount")
            .eq("zone_id", zone_id)
            .eq("status", "active")
            .execute()
        )
        policies = policies_resp.data or []
    except Exception as e:
        logger.warning(f"Could not fetch policies for zone {zone_id}: {e}")
        # Fallback: find all workers in zone from worker_profiles
        try:
            workers_resp = (
                sb.table("worker_profiles")
                .select("profile_id, avg_hourly_income_inr, platform_name, city")
                .eq("preferred_zone_id", zone_id)
                .execute()
            )
            policies = [
                {
                    "worker_profile_id": w["profile_id"],
                    "plan_type": "essential",
                    "coverage_amount": 3000,
                    "premium_amount": 28,
                }
                for w in (workers_resp.data or [])
            ]
        except Exception as e2:
            logger.error(f"Fallback worker fetch failed: {e2}")
            return []

    if not policies:
        return []

    # Filter: check shift overlap with trigger time
    eligible = []
    trigger_dt = _parse_dt(trigger_started_at)

    for policy in policies:
        worker_id = policy["worker_profile_id"]
        shift_overlap = await _check_shift_overlap(sb, worker_id, trigger_dt)

        # Enrich with worker profile data
        try:
            profile_resp = (
                sb.table("worker_profiles")
                .select(
                    "profile_id, avg_hourly_income_inr, platform_name, city, trust_score, "
                    "gps_consent, bank_verified"
                )
                .eq("profile_id", worker_id)
                .maybe_single()
                .execute()
            )
            profile = profile_resp.data or {}
        except Exception:
            profile = {}

        stats_summary = await _get_recent_worker_stats_summary(sb, worker_id)

        # Build context for claim pipeline
        eligible.append({
            "worker_id": worker_id,
            "policy": policy,
            "shift_overlap_ratio": shift_overlap,
            "avg_hourly_income": profile.get("avg_hourly_income_inr", 150),
            "platform": profile.get("platform_name", ""),
            "city": profile.get("city", ""),
            "trust_score": profile.get("trust_score", 0.75),
            "gps_consent": bool(profile.get("gps_consent", True)),
            "bank_verified": bool(profile.get("bank_verified", False)),
            "active_days": stats_summary["active_days"],
            "avg_daily_orders": stats_summary["avg_daily_orders"],
            "gps_consistency_score": stats_summary["gps_consistency_score"],
        })

    return eligible


async def _check_shift_overlap(
    sb, worker_id: str, trigger_time: datetime | None
) -> float:
    """
    Check if worker has a shift overlapping with the trigger event.
    Returns overlap ratio (0.0 to 1.0).
    """
    if not trigger_time:
        return 0.5  # Assume partial overlap if no time data

    try:
        trigger_date = trigger_time.date().isoformat()
        shifts_resp = (
            sb.table("worker_shifts")
            .select("shift_start, shift_end")
            .eq("worker_profile_id", worker_id)
            .eq("shift_date", trigger_date)
            .execute()
        )
        shifts = shifts_resp.data or []
    except Exception:
        return 0.5  # Default to moderate overlap on DB error

    if not shifts:
        # Check platform stats as proxy for activity
        return 0.3  # Worker likely active but no shift record

    for shift in shifts:
        start = _parse_dt(shift.get("shift_start"))
        end = _parse_dt(shift.get("shift_end"))
        if start and end and start <= trigger_time <= end:
            return 1.0  # Full overlap — trigger happened during shift

    return 0.2  # Had shifts today but not during trigger window


async def _get_recent_zone_activity_context(
    sb,
    worker_id: str,
    days_lookback: int = 30,
) -> tuple[dict[str, int], str | None, str | None]:
    """
    Build behavioral context for region controls from recent worker shifts:
      - zone_delivery_counts
      - last_zone_activity_timestamp
      - last_zone_activity_zone_id
    """
    lookback_date = (datetime.now(timezone.utc) - timedelta(days=days_lookback)).date().isoformat()

    try:
        shifts_resp = (
            sb.table("worker_shifts")
            .select("zone_id,shift_start,shift_end")
            .eq("worker_profile_id", worker_id)
            .gte("shift_date", lookback_date)
            .order("shift_end", desc=True)
            .limit(400)
            .execute()
        )
        shifts = shifts_resp.data or []
    except Exception:
        shifts = []

    zone_delivery_counts: dict[str, int] = {}
    for shift in shifts:
        zone_id = shift.get("zone_id")
        if not zone_id:
            continue
        zone_delivery_counts[str(zone_id)] = zone_delivery_counts.get(str(zone_id), 0) + 1

    last_zone_activity_timestamp: str | None = None
    last_zone_activity_zone_id: str | None = None
    if shifts:
        latest = shifts[0]
        last_zone_activity_timestamp = latest.get("shift_end") or latest.get("shift_start")
        last_zone_activity_zone_id = latest.get("zone_id")

    return zone_delivery_counts, last_zone_activity_timestamp, last_zone_activity_zone_id


async def _get_recent_worker_stats_summary(
    sb,
    worker_id: str,
    days_lookback: int = 14,
) -> dict[str, float | int]:
    """
    Build a lightweight behavioral summary from daily stats for fraud/scoring realism.
    """
    lookback_date = (datetime.now(timezone.utc) - timedelta(days=days_lookback)).date().isoformat()

    try:
        stats_resp = (
            sb.table("platform_worker_daily_stats")
            .select("stat_date,completed_orders,gps_consistency_score")
            .eq("worker_profile_id", worker_id)
            .gte("stat_date", lookback_date)
            .order("stat_date", desc=True)
            .limit(days_lookback)
            .execute()
        )
        stats = stats_resp.data or []
    except Exception:
        stats = []

    if not stats:
        return {
            "active_days": 4,
            "avg_daily_orders": 3,
            "gps_consistency_score": 0.78,
        }

    active_days = sum(1 for row in stats if int(row.get("completed_orders") or 0) > 0)
    if active_days <= 0:
        active_days = min(len(stats), 3)

    completed_orders = [int(row.get("completed_orders") or 0) for row in stats]
    avg_daily_orders = round(sum(completed_orders) / max(1, len(completed_orders)))
    if avg_daily_orders <= 0:
        avg_daily_orders = 1

    gps_scores = [
        float(row.get("gps_consistency_score"))
        for row in stats
        if row.get("gps_consistency_score") is not None
    ]
    gps_consistency_score = round(sum(gps_scores) / len(gps_scores), 4) if gps_scores else 0.75

    return {
        "active_days": int(active_days),
        "avg_daily_orders": int(avg_daily_orders),
        "gps_consistency_score": float(gps_consistency_score),
    }


async def _process_worker_claim(
    sb,
    worker: dict,
    trigger: dict,
    trigger_id: str,
    trigger_code: str,
    trigger_family: str,
    severity_band: str,
    city: str,
    observed_value: float,
    threshold_label: str,
) -> dict:
    """
    Run the full claim pipeline for a single worker against a trigger event
    and persist the result to the database.
    """
    worker_id = worker["worker_id"]
    policy = worker["policy"]

    try:
        # ── Build context objects for claim pipeline ──────────────────
        plan = policy.get("plan_type", "essential")
        if plan not in ("essential", "plus"):
            plan = "essential"

        claim_zone_id = trigger.get("zone_id")
        (
            zone_delivery_counts,
            last_zone_activity_timestamp,
            last_zone_activity_zone_id,
        ) = await _get_recent_zone_activity_context(sb, worker_id)

        worker_context = {
            "worker_id": worker_id,
            "active_days": max(1, int(worker.get("active_days", 4))),
            "shift_overlap_ratio": worker.get("shift_overlap_ratio", 0.8),
            "orders_before_disruption": max(1, int(worker.get("avg_daily_orders", 3))),
            "prior_claim_rate": 0.0,
            "gps_consistency_score": float(
                worker.get(
                    "gps_consistency_score",
                    0.88 if worker.get("gps_consent", True) else 0.45,
                )
            ),
            "avg_hourly_income_inr": worker.get("avg_hourly_income", 150),
            "trust_score": worker.get("trust_score", 0.75),
            "bank_verified": bool(worker.get("bank_verified", False)),
            "accessibility_score": 1.0 if worker.get("gps_consent", True) else 0.78,
            "zone_id": claim_zone_id,
            "zone_delivery_counts": zone_delivery_counts,
            "last_zone_activity_timestamp": last_zone_activity_timestamp,
            "last_zone_activity_zone_id": last_zone_activity_zone_id,
        }

        # If there is no historical activity but we know the worker had overlap
        # in the current trigger zone, provide a minimal continuity signal so
        # trigger-auto claims are not unfairly penalized as first-time spoofing.
        if claim_zone_id and not worker_context["zone_delivery_counts"]:
            worker_context["zone_delivery_counts"] = {str(claim_zone_id): 1}
            worker_context["last_zone_activity_zone_id"] = str(claim_zone_id)
            worker_context["last_zone_activity_timestamp"] = (
                trigger.get("started_at") or datetime.now(timezone.utc).isoformat()
            )

        trigger_context = {
            "trigger_id": trigger_id,
            "trigger_family": trigger_family,
            "trigger_code": trigger_code,
            "raw_value": observed_value,
            "observed_value": observed_value,
            "band": severity_band,
            "severity_band": severity_band,
            "source_reliability": 0.90,  # Live API data = high reliability
            "source_type": "public_source",
            "started_at": trigger.get("started_at"),
        }

        # ── Query recent claims for DBSCAN clustering (Layer 4) ─────────
        recent_claims_batch = []
        zone_claims_count = 0
        try:
            one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            recent_resp = (
                sb.table("manual_claims")
                .select("id, worker_profile_id, claimed_at")
                .eq("trigger_event_id", trigger_id)
                .gte("claimed_at", one_hour_ago)
                .execute()
            )
            recent_claims_batch = recent_resp.data or []
            zone_claims_count = len(recent_claims_batch)
        except Exception as e:
            logger.warning(f"Could not fetch recent claims for DBSCAN: {e}")

        # ── Run the claim pipeline ────────────────────────────────────
        from backend.app.services.claim_pipeline import run_claim_pipeline

        pipeline_result = run_claim_pipeline(
            claim_id=str(uuid4()),
            worker_context=worker_context,
            trigger_context=trigger_context,
            claim_mode="trigger_auto",  # This is a ZERO-TOUCH auto-claim
            evidence_records=[],
            claim_record={
                "zone_id": claim_zone_id,
                "city": city,
                "claim_mode": "trigger_auto",
            },
            zone_claims_last_hour=zone_claims_count,
            plan=plan,
        )

        review = pipeline_result.get("review", {})
        decision = review.get("decision_action", "needs_review")
        claim_status = review.get("decision", "soft_hold_verification")
        payout_amount = (
            pipeline_result.get("parametric_payout", {}).get("parametric_payout", 0)
        )
        fraud_score = pipeline_result.get("fraud_analysis", {}).get("fraud_score", 0)
        cal = pipeline_result.get("internal_calibration", {})
        version_context = resolve_decision_versions(
            sb=sb,
            worker_profile_id=str(worker_id),
            cohort_key=str(city or ""),
        )
        attach_version_context(pipeline_result, version_context)

        # ── Persist claim + payout + outbox event transactionally ─────
        now_iso = datetime.now(timezone.utc).isoformat()
        needs_manual_review = claim_status in {
            "submitted",
            "soft_hold_verification",
            "fraud_escalated_review",
        }
        review_due_at = (
            datetime.now(timezone.utc) + timedelta(hours=max(1, settings.review_sla_hours))
        ).isoformat()
        claim_row = {
            "worker_profile_id": worker_id,
            "trigger_event_id": trigger_id,
            "claim_mode": "trigger_auto",
            "claim_reason": (
                f"Auto-initiated: {trigger_code} — {threshold_label}. "
                f"Observed: {observed_value}. Severity: {severity_band}."
            ),
            "claim_status": claim_status,
            "claimed_at": now_iso,
            "assignment_state": "unassigned" if needs_manual_review else "resolved",
            "review_due_at": review_due_at if needs_manual_review else None,
            "rule_version_id": version_context["rule_version"].get("id"),
            "model_version_id": version_context["model_version"].get("id"),
        }

        payout_row = {
            "covered_weekly_income_b": cal.get("covered_weekly_income_b", 0),
            "claim_probability_p": 0.15,
            "severity_score_s": cal.get("severity_score_s", 0),
            "exposure_score_e": cal.get("exposure_score_e", 0),
            "confidence_score_c": cal.get("confidence_score_c", 0),
            "fraud_holdback_fh": cal.get("fraud_holdback_fh", 0),
            "outlier_uplift_u": cal.get("outlier_uplift_u", 1.0),
            "payout_cap": cal.get("payout_cap", payout_amount),
            "expected_payout": cal.get("expected_payout", payout_amount),
            "gross_premium": cal.get("gross_premium", 0),
            "recommended_payout": cal.get(
                "recommended_payout_internal", payout_amount
            ),
            "explanation_json": pipeline_result,
            "created_at": now_iso,
        }

        auto_processed_event_payload = {
            "trigger_id": trigger_id,
            "trigger_code": trigger_code,
            "worker_id": worker_id,
            "decision": decision,
            "claim_status": claim_status,
            "payout_amount": payout_amount,
            "fraud_score": fraud_score,
            "rule_version_id": version_context["rule_version"].get("id"),
            "model_version_id": version_context["model_version"].get("id"),
            "rule_version_key": version_context["rule_version"].get("key"),
            "model_version_key": version_context["model_version"].get("key"),
        }

        persist_result = await persist_claim_with_outbox(
            sb=sb,
            claim_row=claim_row,
            payout_row=payout_row,
            event_type="claim.auto_processed",
            event_key=str(worker_id),
            event_source="auto_claim_engine._process_worker_claim",
            event_payload=auto_processed_event_payload,
            publish_immediately=False,
        )

        if persist_result.get("duplicate_skipped"):
            logger.info(
                "Skipping duplicate approved worker-event claim for worker %s and trigger %s",
                worker_id,
                trigger_id,
            )
            return {
                "worker_id": worker_id,
                "trigger_id": trigger_id,
                "decision": "skipped_duplicate",
                "claim_status": claim_status,
            }

        claim_id = persist_result.get("claim_id")
        if not claim_id:
            raise RuntimeError(
                f"Failed to persist claim transaction for worker {worker_id}"
            )

        logger.info(
            f"Claim processed for worker {worker_id}: "
            f"{decision} → {claim_status} | ₹{payout_amount}"
        )

        return {
            "worker_id": worker_id,
            "claim_id": claim_id,
            "claim_status": claim_status,
            "decision": decision,
            "payout_amount": payout_amount,
            "fraud_score": fraud_score,
            "trigger_code": trigger_code,
        }

    except Exception as e:
        logger.error(f"Auto-claim processing failed for worker {worker_id}: {e}")
        return {
            "worker_id": worker_id,
            "decision": "error",
            "error": f"Auto-claim failed for {worker_id}: {e}",
        }


async def _get_worker_phone(sb, worker_id: str) -> str | None:
    """Fetch worker's phone number from profiles table."""
    try:
        resp = (
            sb.table("profiles")
            .select("phone")
            .eq("id", worker_id)
            .maybe_single()
            .execute()
        )
        return resp.data.get("phone") if resp.data else None
    except Exception:
        return None


def _parse_dt(dt_str: str | None) -> datetime | None:
    """Parse ISO datetime string to timezone-aware datetime."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None
