import json
import re
from datetime import datetime, timedelta
from typing import Optional

import stripe

from database import SessionLocal
from plans_catalog import get_plan_spec, normalize_plan_code
from saas_models import AppUser, PaymentEvent, Plan
from saas_services import CREDIT_PACKS, add_credits, reset_monthly_credits
from saas_settings import settings
from services.entitlements import sync_subscription_state


if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


PLAN_TO_PRICE = {
    "starter": getattr(settings, "STRIPE_PRICE_STARTER", ""),
    "growth": getattr(settings, "STRIPE_PRICE_GROWTH", ""),
    "agency": getattr(settings, "STRIPE_PRICE_AGENCY_V2", "") or getattr(settings, "STRIPE_PRICE_AGENCY", ""),
}

PACK_TO_PRICE = {
    "pack_s": settings.STRIPE_PACK_S_PRICE,
    "pack_m": settings.STRIPE_PACK_M_PRICE,
    "pack_l": settings.STRIPE_PACK_L_PRICE,
}

PLAN_NAME_RE = re.compile(r"^autosocial_([a-z_]+)_eur_month_v(\d+)$")


def _frontend_url() -> str:
    return (settings.FRONTEND_BASE_URL or "").rstrip("/") or "http://localhost:3000"


def _with_frontend_default(url_value: str, suffix: str) -> str:
    raw = (url_value or "").strip()
    frontend = _frontend_url()
    if not raw:
        return f"{frontend}{suffix}"
    if "localhost" in raw and "localhost" not in frontend:
        return f"{frontend}{suffix}"
    return raw


def _success_url() -> str:
    return _with_frontend_default(settings.STRIPE_SUCCESS_URL, "/billing/?success=1")


def _cancel_url() -> str:
    return _with_frontend_default(settings.STRIPE_CANCEL_URL, "/billing/?cancel=1")


def _portal_return_url() -> str:
    return _with_frontend_default(settings.STRIPE_PORTAL_RETURN_URL, "/billing/")


def ensure_customer(user: AppUser) -> str:
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe is not configured")

    db = SessionLocal()
    try:
        db_user = db.query(AppUser).filter_by(id=user.id).first()
        if not db_user:
            raise RuntimeError("User not found")

        if db_user.stripe_customer_id:
            return db_user.stripe_customer_id

        customer = stripe.Customer.create(email=db_user.email, metadata={"user_id": str(db_user.id)})
        db_user.stripe_customer_id = customer.id
        db.commit()
        return customer.id
    finally:
        db.close()


def _plan_price_eur(plan_name: str) -> float:
    db = SessionLocal()
    try:
        plan = db.query(Plan).filter_by(name=plan_name).first()
        if not plan:
            raise RuntimeError(f"Unknown plan: {plan_name}")
        return float(plan.price_eur_month or 0)
    finally:
        db.close()


def _resolve_or_create_subscription_price_id(plan_name: str, prefer_env: bool = True) -> str:
    normalized_plan = normalize_plan_code(plan_name)
    if prefer_env:
        configured = PLAN_TO_PRICE.get(normalized_plan)
        if configured:
            return configured
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe is not configured")

    spec = get_plan_spec(normalized_plan)
    lookup_key = spec.stripe_lookup_key
    try:
        listed = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
        data = (listed or {}).get("data", [])
        if data:
            return data[0]["id"]
    except Exception:
        pass

    amount_eur = _plan_price_eur(normalized_plan)
    if amount_eur <= 0:
        raise RuntimeError("Selected plan has non-positive price")
    price = stripe.Price.create(
        currency="eur",
        unit_amount=int(round(amount_eur * 100)),
        recurring={"interval": "month"},
        nickname=f"AutoSocial {normalized_plan.title()} Monthly",
        lookup_key=lookup_key,
        transfer_lookup_key=True,
        product_data={"name": f"AutoSocial {normalized_plan.title()}"},
        metadata={"plan_name": normalized_plan},
    )
    return price.id


def _resolve_or_create_pack_price_id(pack_code: str, prefer_env: bool = True) -> str:
    if prefer_env:
        configured = PACK_TO_PRICE.get(pack_code)
        if configured:
            return configured
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe is not configured")
    cfg = CREDIT_PACKS.get(pack_code)
    if not cfg:
        raise RuntimeError("Unknown credit pack")

    lookup_key = f"autosocial_{pack_code}_eur_once_v1"
    try:
        listed = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
        data = (listed or {}).get("data", [])
        if data:
            return data[0]["id"]
    except Exception:
        pass

    amount_eur = float(cfg.get("price_eur") or 0)
    if amount_eur <= 0:
        raise RuntimeError("Selected credit pack has non-positive price")
    price = stripe.Price.create(
        currency="eur",
        unit_amount=int(round(amount_eur * 100)),
        nickname=f"AutoSocial {pack_code.upper()} Top-up",
        lookup_key=lookup_key,
        transfer_lookup_key=True,
        product_data={"name": f"AutoSocial Credits {pack_code.upper()}"},
        metadata={"pack_code": pack_code},
    )
    return price.id


def _plan_name_from_price_id(price_id: Optional[str]) -> Optional[str]:
    if not price_id:
        return None

    for name, pid in PLAN_TO_PRICE.items():
        if pid and pid == price_id:
            return normalize_plan_code(name)

    try:
        price = stripe.Price.retrieve(price_id)
    except Exception:
        return None

    lookup_key = (price or {}).get("lookup_key") or ""
    match = PLAN_NAME_RE.match(str(lookup_key))
    if match:
        raw_name = match.group(1)
        version = int(match.group(2))
        if raw_name == "light":
            return "starter"
        if raw_name == "pro" and version <= 1:
            return "growth"
        if raw_name == "agency" and version <= 1:
            return "agency"
        return normalize_plan_code(raw_name)

    metadata = (price or {}).get("metadata", {}) or {}
    from_meta = (metadata.get("plan_name") or "").strip().lower()
    if from_meta:
        return normalize_plan_code(from_meta)
    return None


def create_subscription_checkout(user: AppUser, plan_name: str) -> str:
    normalized_plan = normalize_plan_code(plan_name)
    spec = get_plan_spec(normalized_plan)
    if spec.price_eur_month <= 0:
        raise RuntimeError("Selected plan has non-positive price")

    price_id = _resolve_or_create_subscription_price_id(normalized_plan, prefer_env=True)
    customer_id = ensure_customer(user)
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=_success_url(),
            cancel_url=_cancel_url(),
            metadata={"user_id": str(user.id), "plan_name": normalized_plan},
            subscription_data={"metadata": {"user_id": str(user.id), "plan_name": normalized_plan}},
        )
    except stripe.error.InvalidRequestError as exc:
        if "No such price" not in str(exc):
            raise
        fallback_price = _resolve_or_create_subscription_price_id(normalized_plan, prefer_env=False)
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": fallback_price, "quantity": 1}],
            success_url=_success_url(),
            cancel_url=_cancel_url(),
            metadata={"user_id": str(user.id), "plan_name": normalized_plan},
            subscription_data={"metadata": {"user_id": str(user.id), "plan_name": normalized_plan}},
        )
    return session.url


def create_credit_pack_checkout(user: AppUser, pack_code: str) -> str:
    price_id = _resolve_or_create_pack_price_id(pack_code, prefer_env=True)
    customer_id = ensure_customer(user)
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=_success_url(),
            cancel_url=_cancel_url(),
            metadata={"user_id": str(user.id), "pack_code": pack_code},
        )
    except stripe.error.InvalidRequestError as exc:
        if "No such price" not in str(exc):
            raise
        fallback_price = _resolve_or_create_pack_price_id(pack_code, prefer_env=False)
        session = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": fallback_price, "quantity": 1}],
            success_url=_success_url(),
            cancel_url=_cancel_url(),
            metadata={"user_id": str(user.id), "pack_code": pack_code},
        )
    return session.url


def create_portal_link(user: AppUser) -> str:
    customer_id = ensure_customer(user)
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=_portal_return_url())
    return session.url


def _save_event(event_id: str, event_type: str, customer_id: Optional[str], subscription_id: Optional[str], amount_eur: Optional[float], status: Optional[str], payload: dict) -> None:
    db = SessionLocal()
    try:
        exists = db.query(PaymentEvent).filter_by(stripe_event_id=event_id).first()
        if exists:
            return
        db.add(
            PaymentEvent(
                stripe_event_id=event_id,
                event_type=event_type,
                customer_id=customer_id,
                subscription_id=subscription_id,
                amount_eur=amount_eur,
                status=status,
                payload_json=json.dumps(payload, ensure_ascii=False),
            )
        )
        db.commit()
    finally:
        db.close()


def _get_user_by_customer(customer_id: str) -> Optional[AppUser]:
    db = SessionLocal()
    try:
        return db.query(AppUser).filter_by(stripe_customer_id=customer_id).first()
    finally:
        db.close()


def _set_user_plan(user_id: int, plan_name: str, subscription_id: Optional[str], billing_status: str, period_end_ts: Optional[int]) -> None:
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=user_id).first()
        plan = db.query(Plan).filter_by(name=plan_name).first()
        if not user or not plan:
            return
        user.plan = plan.name
        user.plan_id = plan.id
        user.stripe_subscription_id = subscription_id
        user.billing_status = billing_status
        user.current_period_end = datetime.utcfromtimestamp(period_end_ts) if period_end_ts else user.current_period_end
        db.commit()
        current_period_end = datetime.utcfromtimestamp(period_end_ts) if period_end_ts else user.current_period_end
        current_period_start = (current_period_end - timedelta(days=30)) if current_period_end else None
        sync_subscription_state(
            user_id=user.id,
            plan=plan.name,
            status=billing_status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            stripe_customer_id=user.stripe_customer_id,
            stripe_subscription_id=subscription_id,
        )
    finally:
        db.close()


def process_stripe_event(event: dict) -> None:
    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    customer_id = data_object.get("customer")
    subscription_id = data_object.get("id") if "subscription" in event_type else data_object.get("subscription")
    amount_total = data_object.get("amount_paid") or data_object.get("amount_total")
    amount_eur = (amount_total / 100.0) if amount_total is not None else None

    _save_event(
        event_id=event.get("id", ""),
        event_type=event_type,
        customer_id=customer_id,
        subscription_id=subscription_id,
        amount_eur=amount_eur,
        status=data_object.get("status"),
        payload=event,
    )

    if not customer_id:
        return

    user = _get_user_by_customer(customer_id)
    if not user:
        return

    if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        sub = data_object
        price_id = (sub.get("items", {}).get("data", [{}])[0].get("price", {}) or {}).get("id")
        plan_name = _plan_name_from_price_id(price_id)
        if not plan_name:
            plan_name = normalize_plan_code((sub.get("metadata", {}).get("plan_name") or "").strip().lower())
            if plan_name == "free":
                plan_name = None
        if plan_name:
            _set_user_plan(
                user_id=user.id,
                plan_name=plan_name,
                subscription_id=sub.get("id"),
                billing_status=sub.get("status", "active"),
                period_end_ts=sub.get("current_period_end"),
            )

    if event_type == "customer.subscription.deleted":
        _set_user_plan(user.id, "free", None, "canceled", None)
        sync_subscription_state(
            user_id=user.id,
            plan="trial",
            status="canceled",
            stripe_customer_id=user.stripe_customer_id,
            stripe_subscription_id=None,
        )

    if event_type == "invoice.paid":
        db = SessionLocal()
        try:
            refreshed = db.query(AppUser).filter_by(id=user.id).first()
            if refreshed:
                plan_name = refreshed.plan or "free"
                reset_monthly_credits(refreshed.id, plan_name)
                refreshed.billing_status = "active"
                db.commit()
        finally:
            db.close()

    if event_type == "checkout.session.completed":
        metadata = data_object.get("metadata", {}) or {}
        mode = (data_object.get("mode") or "").strip().lower()

        if mode == "subscription":
            plan_name = normalize_plan_code((metadata.get("plan_name") or "").strip().lower())
            if plan_name == "free":
                plan_name = None
            if plan_name:
                _set_user_plan(
                    user_id=user.id,
                    plan_name=plan_name,
                    subscription_id=data_object.get("subscription"),
                    billing_status="active",
                    period_end_ts=None,
                )

        pack_code = metadata.get("pack_code")
        if pack_code in CREDIT_PACKS:
            credits = CREDIT_PACKS[pack_code]["credits"]
            add_credits(
                user_id=user.id,
                delta=credits,
                ledger_type="topup",
                stripe_payment_intent_id=data_object.get("payment_intent"),
                meta={"pack_code": pack_code},
            )

    if event_type == "invoice.payment_failed":
        db = SessionLocal()
        try:
            refreshed = db.query(AppUser).filter_by(id=user.id).first()
            if refreshed:
                refreshed.billing_status = "past_due"
                db.commit()
        finally:
            db.close()


def verify_and_construct_event(payload: bytes, sig_header: str) -> dict:
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured")
    return stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=settings.STRIPE_WEBHOOK_SECRET)

