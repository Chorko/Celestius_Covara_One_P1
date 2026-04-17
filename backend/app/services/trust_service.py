"""Trust score lifecycle persistence helpers."""

from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clamp_trust_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 2)


def get_worker_trust_score(sb, worker_profile_id: str) -> float:
    """Load the current worker trust score, raising when worker does not exist."""
    row = (
        sb.table("worker_profiles")
        .select("profile_id, trust_score")
        .eq("profile_id", worker_profile_id)
        .maybe_single()
        .execute()
        .data
    )
    if not row:
        raise ValueError("Worker profile not found")

    return _clamp_trust_score(_safe_float(row.get("trust_score"), default=0.75))


def record_trust_history_event(
    sb,
    *,
    worker_profile_id: str,
    previous_trust_score: float,
    delta: float,
    new_trust_score: float,
    event_type: str,
    claim_id: str | None = None,
    severity: str | None = None,
    reason: str | None = None,
    actor_profile_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one trust-history row and return the inserted record."""
    payload = {
        "worker_profile_id": worker_profile_id,
        "claim_id": claim_id,
        "event_type": event_type,
        "severity": severity,
        "previous_trust_score": _clamp_trust_score(previous_trust_score),
        "delta": round(float(delta), 4),
        "new_trust_score": _clamp_trust_score(new_trust_score),
        "reason": reason,
        "actor_profile_id": actor_profile_id,
        "metadata": metadata or {},
    }

    inserted = (
        sb.table("trust_score_history")
        .insert(payload)
        .maybe_single()
        .execute()
        .data
    )
    return inserted or payload


def apply_trust_score_delta(
    sb,
    *,
    worker_profile_id: str,
    delta: float,
    event_type: str,
    claim_id: str | None = None,
    severity: str | None = None,
    reason: str | None = None,
    actor_profile_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a trust-score delta, persist worker score, and append history."""
    previous_score = get_worker_trust_score(sb, worker_profile_id)
    applied_delta = float(delta)
    next_score = _clamp_trust_score(previous_score + applied_delta)

    sb.table("worker_profiles").update({"trust_score": next_score}).eq(
        "profile_id", worker_profile_id
    ).execute()

    history_row = record_trust_history_event(
        sb,
        worker_profile_id=worker_profile_id,
        previous_trust_score=previous_score,
        delta=applied_delta,
        new_trust_score=next_score,
        event_type=event_type,
        claim_id=claim_id,
        severity=severity,
        reason=reason,
        actor_profile_id=actor_profile_id,
        metadata=metadata,
    )

    return {
        "history_id": history_row.get("id"),
        "worker_profile_id": worker_profile_id,
        "previous_trust_score": previous_score,
        "delta": round(applied_delta, 4),
        "new_trust_score": next_score,
        "event_type": event_type,
    }


def list_worker_trust_history(
    sb,
    *,
    worker_profile_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch trust-score history rows, newest first."""
    max_limit = max(1, min(int(limit), 200))
    rows = (
        sb.table("trust_score_history")
        .select("*")
        .eq("worker_profile_id", worker_profile_id)
        .order("created_at", desc=True)
        .limit(max_limit)
        .execute()
        .data
    )
    return rows or []
