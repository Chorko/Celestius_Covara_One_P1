"""Stripe checkout orchestration for weekly policy purchases."""

from __future__ import annotations

import logging
import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.dependencies import get_current_user, require_worker
from backend.app.services.policy_service import (
    VALID_PLANS,
    quote_policy_for_worker,
    upsert_weekly_policy,
)
from backend.app.services.rewards_engine import award_coins
from backend.app.supabase_client import get_supabase_admin

router = APIRouter(prefix="/payments", tags=["Payments"])
logger = logging.getLogger("covara.payments")

_STRIPE_MINIMUM_MINOR_BY_CURRENCY = {
    "usd": 50,
    "eur": 50,
    "gbp": 50,
    "inr": 5000,
}


class CheckoutSessionRequest(BaseModel):
    plan: str = "essential"


class FinalizeCheckoutRequest(BaseModel):
    session_id: str


def _stripe_module():
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=503,
            detail="Stripe checkout is not configured. Missing STRIPE_SECRET_KEY.",
        )

    try:
        import stripe  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency issue
        raise HTTPException(
            status_code=500,
            detail="Stripe SDK is not installed on the backend runtime.",
        ) from exc

    stripe.api_key = settings.stripe_secret_key
    return stripe


def _with_session_placeholder(url: str) -> str:
    trimmed = (url or "").strip()
    if not trimmed:
        trimmed = "http://localhost:3000/worker/pricing?checkout=success"

    if "{CHECKOUT_SESSION_ID}" in trimmed:
        return trimmed

    separator = "&" if "?" in trimmed else "?"
    return f"{trimmed}{separator}session_id={{CHECKOUT_SESSION_ID}}"


def _session_field(session: Any, key: str, default: Any = None) -> Any:
    if hasattr(session, key):
        return getattr(session, key)

    if isinstance(session, dict):
        return session.get(key, default)

    getter = getattr(session, "get", None)
    if callable(getter):
        return getter(key, default)

    return default


def _session_metadata(session: Any) -> dict[str, Any]:
    meta = _session_field(session, "metadata", {}) or {}
    if isinstance(meta, dict):
        return meta
    return {}


def _stripe_object_id(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None

    if isinstance(value, dict):
        ident = value.get("id")
        return str(ident).strip() if ident else None

    ident = getattr(value, "id", None)
    if ident:
        return str(ident).strip()

    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            ident = getter("id")
        except Exception:
            ident = None
        if ident:
            return str(ident).strip()

    return None


def _extract_worker_id(session: Any) -> str:
    metadata = _session_metadata(session)
    worker_id = str(
        metadata.get("worker_profile_id")
        or _session_field(session, "client_reference_id", "")
        or ""
    ).strip()
    return worker_id


async def _finalize_paid_checkout(
    sb,
    *,
    session: Any,
    actor_profile_id: str | None,
    source: str,
) -> dict[str, Any]:
    session_id = str(_session_field(session, "id", "") or "")
    if not session_id:
        raise ValueError("Checkout session id is missing")

    payment_status = str(_session_field(session, "payment_status", "") or "")
    if payment_status != "paid":
        raise ValueError("Checkout session is not paid yet")

    worker_profile_id = _extract_worker_id(session)
    if not worker_profile_id:
        raise ValueError("Unable to resolve worker id from checkout metadata")

    metadata = _session_metadata(session)
    plan = str(metadata.get("plan") or "essential").strip().lower()
    if plan not in VALID_PLANS:
        plan = "essential"

    existing = (
        sb.table("audit_events")
        .select("id, event_payload")
        .eq("entity_type", "stripe_checkout")
        .eq("entity_id", session_id)
        .eq("action_type", "stripe_checkout_completed")
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        payload = existing[0].get("event_payload") or {}
        return {
            "status": "already_finalized",
            "session_id": session_id,
            "policy": payload.get("policy"),
            "reward": payload.get("reward"),
        }

    amount_total = _session_field(session, "amount_total", 0) or 0
    amount_inr = round(float(amount_total) / 100.0, 2) if amount_total else None
    quoted_weekly_premium = metadata.get("quoted_weekly_premium_inr")
    billing_weeks_meta = metadata.get("billing_weeks")
    try:
        weekly_premium_inr = float(str(quoted_weekly_premium))
    except (TypeError, ValueError):
        weekly_premium_inr = amount_inr

    try:
        billing_weeks = int(str(billing_weeks_meta))
    except (TypeError, ValueError):
        billing_weeks = 1
    billing_weeks = max(1, billing_weeks)

    policy_result = upsert_weekly_policy(
        sb,
        worker_profile_id=worker_profile_id,
        plan=plan,
        weekly_premium_inr=weekly_premium_inr,
    )

    reward_result = await award_coins(
        sb,
        profile_id=worker_profile_id,
        activity="policy_purchase",
        coins=12,
        description=f"Weekly {plan} coverage purchased via Stripe",
        reference_id=session_id,
    )

    payment_intent_id = _stripe_object_id(_session_field(session, "payment_intent", None))

    event_payload = {
        "source": source,
        "session_id": session_id,
        "payment_status": payment_status,
        "plan": plan,
        "worker_profile_id": worker_profile_id,
        "amount_total_minor": amount_total,
        "amount_inr": amount_inr,
        "quoted_weekly_premium_inr": weekly_premium_inr,
        "billing_weeks": billing_weeks,
        "currency": _session_field(session, "currency", settings.stripe_currency),
        "payment_intent": payment_intent_id,
        "policy": policy_result,
        "reward": reward_result,
    }

    sb.table("audit_events").insert(
        {
            "entity_type": "stripe_checkout",
            "entity_id": session_id,
            "action_type": "stripe_checkout_completed",
            "actor_profile_id": actor_profile_id,
            "event_payload": event_payload,
        }
    ).execute()

    return {
        "status": "finalized",
        "session_id": session_id,
        "policy": policy_result,
        "reward": reward_result,
    }


@router.post("/checkout-session", summary="Create Stripe Checkout session for weekly plan purchase")
async def create_checkout_session(
    body: CheckoutSessionRequest,
    user: dict = Depends(require_worker),
):
    plan = (body.plan or "essential").strip().lower()
    if plan not in VALID_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan '{body.plan}'. Must be 'essential' or 'plus'.",
        )

    stripe = _stripe_module()
    sb = get_supabase_admin()

    quote = quote_policy_for_worker(sb, user["id"], plan)
    amount_inr = float(quote["weekly_premium_inr"])
    amount_minor = int(round(amount_inr * 100))
    if amount_minor <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid quote amount returned for checkout.",
        )

    currency = (settings.stripe_currency or "inr").lower()
    minimum_minor = _STRIPE_MINIMUM_MINOR_BY_CURRENCY.get(currency, 50)
    billing_weeks = max(1, int(math.ceil(minimum_minor / amount_minor)))
    charge_total_minor = amount_minor * billing_weeks
    charge_total_inr = round(charge_total_minor / 100.0, 2)

    success_url = _with_session_placeholder(settings.stripe_checkout_success_url)
    cancel_url = (settings.stripe_checkout_cancel_url or "").strip() or "http://localhost:3000/worker/pricing?checkout=cancelled"

    metadata = {
        "worker_profile_id": user["id"],
        "plan": plan,
        "quoted_weekly_premium_inr": f"{amount_inr:.2f}",
        "billing_weeks": str(billing_weeks),
    }

    session_kwargs: dict[str, Any] = {
        "mode": "payment",
        "payment_method_types": ["card"],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": user["id"],
        "metadata": metadata,
        "line_items": [
            {
                "quantity": billing_weeks,
                "price_data": {
                    "currency": currency,
                    "unit_amount": amount_minor,
                    "product_data": {
                        "name": f"Covara One {plan.capitalize()} Weekly Cover",
                        "description": f"Parametric income protection for {billing_weeks} week(s).",
                    },
                },
            }
        ],
    }

    customer_email = user.get("email")
    if isinstance(customer_email, str) and customer_email.strip():
        session_kwargs["customer_email"] = customer_email.strip()

    try:
        session = stripe.checkout.Session.create(**session_kwargs)
    except Exception as exc:
        logger.exception("Stripe checkout session creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe session creation failed: {exc}") from exc

    session_id = str(_session_field(session, "id", ""))
    checkout_url = str(_session_field(session, "url", ""))
    if not session_id or not checkout_url:
        raise HTTPException(status_code=502, detail="Stripe session creation returned invalid response")

    sb.table("audit_events").insert(
        {
            "entity_type": "stripe_checkout",
            "entity_id": session_id,
            "action_type": "stripe_checkout_created",
            "actor_profile_id": user["id"],
            "event_payload": {
                "plan": plan,
                "amount_inr": amount_inr,
                "currency": currency,
                "worker_profile_id": user["id"],
                "quoted_weekly_premium_inr": amount_inr,
                "billing_weeks": billing_weeks,
                "charge_total_inr": charge_total_inr,
            },
        }
    ).execute()

    return {
        "session_id": session_id,
        "checkout_url": checkout_url,
        "plan": plan,
        "amount_inr": amount_inr,
        "currency": currency,
        "billing_weeks": billing_weeks,
        "charge_total_inr": charge_total_inr,
        "quote": quote,
    }


@router.get("/checkout-session/{session_id}", summary="Get Stripe Checkout session status")
async def get_checkout_session_status(
    session_id: str,
    auto_finalize: bool = True,
    user: dict = Depends(require_worker),
):
    stripe = _stripe_module()
    sb = get_supabase_admin()

    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Stripe session: {exc}") from exc

    worker_profile_id = _extract_worker_id(session)
    if worker_profile_id and worker_profile_id != user["id"]:
        raise HTTPException(status_code=403, detail="Checkout session does not belong to this worker.")

    finalization = None
    payment_status = str(_session_field(session, "payment_status", "") or "")
    if auto_finalize and payment_status == "paid":
        try:
            finalization = await _finalize_paid_checkout(
                sb,
                session=session,
                actor_profile_id=user["id"],
                source="payments.get_checkout_session_status",
            )
        except ValueError:
            finalization = None

    return {
        "session_id": str(_session_field(session, "id", "")),
        "status": str(_session_field(session, "status", "")),
        "payment_status": payment_status,
        "amount_total": _session_field(session, "amount_total", None),
        "currency": _session_field(session, "currency", None),
        "finalization": finalization,
    }


@router.post("/checkout/finalize", summary="Finalize paid Stripe checkout and activate policy")
async def finalize_checkout(
    body: FinalizeCheckoutRequest,
    user: dict = Depends(require_worker),
):
    stripe = _stripe_module()
    sb = get_supabase_admin()

    try:
        session = stripe.checkout.Session.retrieve(body.session_id, expand=["payment_intent"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Stripe session: {exc}") from exc

    worker_profile_id = _extract_worker_id(session)
    if worker_profile_id and worker_profile_id != user["id"]:
        raise HTTPException(status_code=403, detail="Checkout session does not belong to this worker.")

    try:
        return await _finalize_paid_checkout(
            sb,
            session=session,
            actor_profile_id=user["id"],
            source="payments.finalize_checkout",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhooks/stripe", summary="Stripe checkout webhook")
async def stripe_checkout_webhook(request: Request):
    stripe = _stripe_module()
    sb = get_supabase_admin()

    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")

    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=503,
            detail="Stripe webhook endpoint is not configured. Missing STRIPE_WEBHOOK_SECRET.",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            settings.stripe_webhook_secret,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe webhook signature: {exc}") from exc

    to_dict_recursive = getattr(event, "to_dict_recursive", None)
    raw_event: Any
    if callable(to_dict_recursive):
        raw_event = to_dict_recursive()
    elif isinstance(event, dict):
        raw_event = event
    else:
        raw_event = {}

    event_data = raw_event if isinstance(raw_event, dict) else {}

    event_type = str(event_data.get("type") or "")
    if event_type == "checkout.session.completed":
        session = (event_data.get("data") or {}).get("object", {})
        try:
            await _finalize_paid_checkout(
                sb,
                session=session,
                actor_profile_id=None,
                source="payments.stripe_checkout_webhook",
            )
        except ValueError as exc:
            logger.warning("Stripe webhook checkout finalize skipped: %s", exc)

    return {"received": True, "event_type": event_type}
