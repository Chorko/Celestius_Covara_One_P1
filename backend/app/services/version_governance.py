"""Rule/model version governance helpers.

Provides deterministic rollout selection (full/canary/cohort) so every
claim decision can carry replayable version context.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from backend.app.config import settings

logger = logging.getLogger("covara.version_governance")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _table_name(kind: str) -> str:
    normalized = (kind or "").strip().lower()
    if normalized == "rule":
        return "rule_versions"
    if normalized == "model":
        return "model_versions"
    raise ValueError("kind must be 'rule' or 'model'")


def _normalized_mode(value: Any) -> str:
    mode = str(value or "full").strip().lower()
    if mode not in {"full", "canary", "cohort"}:
        return "full"
    return mode


def _coerce_percentage(value: Any, default: int = 100) -> int:
    try:
        raw = int(value)
    except (TypeError, ValueError):
        raw = default
    return max(0, min(100, raw))


def _chain(query: Any, method_name: str, *args, **kwargs) -> Any:
    method = getattr(query, method_name, None)
    if not callable(method):
        return query
    try:
        return method(*args, **kwargs)
    except Exception:
        return query


def _query_version_rows(sb, table_name: str, active_only: bool) -> list[dict[str, Any]]:
    try:
        query = sb.table(table_name).select(
            "id,version_key,status,rollout_mode,rollout_percentage,"
            "cohort_key,cohort_salt,priority,is_active,metadata,activated_at,created_at,updated_at"
        )
        if active_only:
            query = _chain(query, "eq", "is_active", True)
            query = _chain(query, "in_", "status", ["active", "canary"])

        query = _chain(query, "order", "priority", desc=True)
        query = _chain(query, "order", "activated_at", desc=True)
        query = _chain(query, "order", "created_at", desc=True)

        response = query.execute()
        rows = getattr(response, "data", None) or []
        return [row for row in rows if isinstance(row, dict)]
    except Exception as exc:
        logger.warning("version-governance query failed for %s: %s", table_name, exc)
        return []


def _deterministic_bucket(subject_key: str, salt: str) -> int:
    digest = hashlib.sha256(f"{subject_key}:{salt}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _pick_rollout_row(
    rows: list[dict[str, Any]],
    subject_key: str,
    cohort_key: str | None,
) -> dict[str, Any] | None:
    if not rows:
        return None

    full_rows = [
        row
        for row in rows
        if _normalized_mode(row.get("rollout_mode")) == "full"
        and str(row.get("status") or "").strip().lower() == "active"
    ]
    default_row = full_rows[0] if full_rows else rows[0]

    requested_cohort = str(cohort_key or "").strip().lower()

    for row in rows:
        mode = _normalized_mode(row.get("rollout_mode"))
        if mode == "cohort":
            expected = str(row.get("cohort_key") or "").strip().lower()
            if expected and requested_cohort and expected == requested_cohort:
                return row
            continue

        if mode == "canary":
            percentage = _coerce_percentage(row.get("rollout_percentage"), default=0)
            salt = str(row.get("cohort_salt") or settings.version_rollout_subject_salt)
            if _deterministic_bucket(subject_key, salt) < percentage:
                return row

    return default_row


def _version_payload(
    row: dict[str, Any] | None,
    fallback_key: str,
) -> dict[str, Any]:
    if not row:
        return {
            "id": None,
            "key": fallback_key,
            "status": "fallback",
            "rollout_mode": "full",
            "rollout_percentage": 100,
            "cohort_key": None,
            "selection_source": "fallback",
        }

    return {
        "id": row.get("id"),
        "key": row.get("version_key") or fallback_key,
        "status": str(row.get("status") or "active"),
        "rollout_mode": _normalized_mode(row.get("rollout_mode")),
        "rollout_percentage": _coerce_percentage(row.get("rollout_percentage"), default=100),
        "cohort_key": row.get("cohort_key"),
        "selection_source": "registry",
    }


def resolve_decision_versions(
    sb,
    worker_profile_id: str | None,
    cohort_key: str | None = None,
) -> dict[str, Any]:
    """Resolve active rule/model versions for a worker request context."""
    subject_key = str(worker_profile_id or "anonymous")

    rule_rows = _query_version_rows(sb, "rule_versions", active_only=True)
    model_rows = _query_version_rows(sb, "model_versions", active_only=True)

    selected_rule = _pick_rollout_row(rule_rows, subject_key, cohort_key)
    selected_model = _pick_rollout_row(model_rows, subject_key, cohort_key)

    return {
        "rule_version": _version_payload(
            selected_rule,
            fallback_key=settings.default_rule_version_key,
        ),
        "model_version": _version_payload(
            selected_model,
            fallback_key=settings.default_model_version_key,
        ),
    }


def attach_version_context(pipeline_result: dict[str, Any], versions: dict[str, Any]) -> None:
    """Attach version-governance context onto pipeline explanation payload."""
    decision_context = pipeline_result.setdefault("decision_context", {})
    decision_context["version_governance"] = versions


def get_version_registry_snapshot(sb) -> dict[str, Any]:
    """Return governance registry state and currently selected defaults."""
    return {
        "active_selection": resolve_decision_versions(sb, worker_profile_id=None),
        "rule_versions": _query_version_rows(sb, "rule_versions", active_only=False),
        "model_versions": _query_version_rows(sb, "model_versions", active_only=False),
    }


def apply_version_rollout(
    sb,
    *,
    kind: str,
    version_id: str,
    mode: str = "full",
    rollout_percentage: int | None = None,
    cohort_key: str | None = None,
) -> dict[str, Any]:
    """Activate a rule/model version with full/canary/cohort rollout controls."""
    table_name = _table_name(kind)
    rollout_mode = _normalized_mode(mode)

    if rollout_mode == "cohort" and not str(cohort_key or "").strip():
        raise ValueError("cohort_key is required when mode='cohort'")

    default_percentage = 100 if rollout_mode == "full" else 10
    percentage = _coerce_percentage(rollout_percentage, default=default_percentage)

    target = (
        sb.table(table_name)
        .select("id,version_key,status,rollout_mode,rollout_percentage,cohort_key,is_active")
        .eq("id", version_id)
        .maybe_single()
        .execute()
        .data
    )
    if not target:
        raise ValueError(f"{kind} version '{version_id}' not found")

    sb.table(table_name).update({"is_active": False}).eq("is_active", True).execute()

    update_payload = {
        "is_active": True,
        "status": "active" if rollout_mode == "full" else "canary",
        "rollout_mode": rollout_mode,
        "rollout_percentage": percentage,
        "cohort_key": str(cohort_key).strip() if rollout_mode == "cohort" else None,
        "activated_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }
    updated_rows = (
        sb.table(table_name)
        .update(update_payload)
        .eq("id", version_id)
        .execute()
        .data
        or []
    )
    updated = updated_rows[0] if updated_rows else {**target, **update_payload}

    return {
        "kind": kind,
        "version_id": updated.get("id") or version_id,
        "version_key": updated.get("version_key"),
        "status": updated.get("status"),
        "rollout_mode": updated.get("rollout_mode"),
        "rollout_percentage": updated.get("rollout_percentage"),
        "cohort_key": updated.get("cohort_key"),
        "is_active": bool(updated.get("is_active")),
    }
