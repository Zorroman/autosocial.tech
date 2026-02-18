import json
from datetime import datetime
from typing import Optional

import stripe

from database import SessionLocal
from saas_models import AppUser, PaymentEvent, Plan
from saas_services import CREDIT_PACKS, add_credits, reset_monthly_credits
from saas_settings import settings


if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


PLAN_TO_PRICE = {
    "light": settings.STRIPE_PRICE_LIGHT,
    "pro": settings.STRIPE_PRICE_PRO,
    "agency": settings.STRIPE_PRICE_AGENCY,
}

PACK_TO_PRICE = {
    "pack_s": settings.STRIPE_PACK_S_PRICE,
    "pack_m": settings.STRIPE_PACK_M_PRICE,
    "pack_l": settings.STRIPE_PACK_L_PRICE,
}


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


def create_subscription_checkout(user: AppUser, plan_name: str) -> str:
    price_id = PLAN_TO_PRICE.get(plan_name)
    if not price_id:
        raise RuntimeError("Stripe price id for selected plan is not configured")

    customer_id = ensure_customer(user)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        metadata={"user_id": str(user.id), "plan_name": plan_name},
    )
    return session.url


def create_credit_pack_checkout(user: AppUser, pack_code: str) -> str:
    price_id = PACK_TO_PRICE.get(pack_code)
    if not price_id:
        raise RuntimeError("Stripe price id for selected credit pack is not configured")

    customer_id = ensure_customer(user)
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        metadata={"user_id": str(user.id), "pack_code": pack_code},
    )
    return session.url


def create_portal_link(user: AppUser) -> str:
    if not user.stripe_customer_id:
        raise RuntimeError("Stripe customer is not linked")
    session = stripe.billing_portal.Session.create(customer=user.stripe_customer_id, return_url=settings.STRIPE_PORTAL_RETURN_URL)
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
        plan_name = sub.get("metadata", {}).get("plan_name")
        if not plan_name:
            price_id = (sub.get("items", {}).get("data", [{}])[0].get("price", {}) or {}).get("id")
            for name, pid in PLAN_TO_PRICE.items():
                if pid and pid == price_id:
                    plan_name = name
                    break
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

    if event_type == "invoice.paid":
        db = SessionLocal()
        try:
            refreshed = db.query(AppUser).filter_by(id=user.id).first()
            if refreshed:
                plan_name = refreshed.plan or "free"
                reset_monthly_credits(refreshed.id, plan_name)
        finally:
            db.close()

    if event_type == "checkout.session.completed":
        metadata = data_object.get("metadata", {}) or {}
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
