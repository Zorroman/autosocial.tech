import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from plans_catalog import PUBLIC_PLAN_ORDER, get_plan_spec, next_public_plan, normalize_plan_code
from saas_models import AppUser, Project, SocialAccount, Subscription, UsageCounter, UsageEvent
from saas_settings import settings

ACTION_POST_GENERATE = "POST_GENERATE"
ACTION_POST_PUBLISH = "POST_PUBLISH"
ACTION_VIDEO_GENERATE = "VIDEO_GENERATE"
ACTION_VIDEO_PUBLISH = "VIDEO_PUBLISH"
ACTION_PROJECT_CREATE = "PROJECT_CREATE"
ACTION_ACCOUNT_CONNECT = "ACCOUNT_CONNECT"
ACTION_SCHEDULE_CREATE = "SCHEDULE_CREATE"
ACTION_ANALYTICS_ADVANCED = "ANALYTICS_ADVANCED"

PAYWALL_LIMIT = "PAYWALL_LIMIT"
PAYWALL_FEATURE = "PAYWALL_FEATURE"

PLAN_FREE = "free"
PLAN_ADMIN = "admin"
PLAN_STARTER = "starter"
PLAN_GROWTH = "growth"
PLAN_AGENCY = "agency"

PLAN_ORDER = list(PUBLIC_PLAN_ORDER)
COUNTER_FIELDS = {
    "POSTS_GENERATED": "posts_generated",
    "POSTS_PUBLISHED": "posts_published",
    "VIDEOS_GENERATED": "videos_generated",
    "VIDEOS_PUBLISHED": "videos_published",
}
ACTION_LIMIT_FIELD = {
    ACTION_POST_GENERATE: "posts_generated",
    ACTION_VIDEO_GENERATE: "videos_generated",
    ACTION_POST_PUBLISH: "posts_published",
    ACTION_VIDEO_PUBLISH: "videos_published",
    ACTION_PROJECT_CREATE: "projects",
    ACTION_ACCOUNT_CONNECT: "accounts_connected",
}


@dataclass
class PeriodWindow:
    start: datetime
    end: datetime


def _utc_now() -> datetime:
    return datetime.utcnow()


def _frontend_base_url() -> str:
    return (settings.FRONTEND_BASE_URL or "http://localhost:3000").rstrip("/")


def _upgrade_url(plan: str) -> str:
    return f"{_frontend_base_url()}/billing/?plan={plan}"


def _normalize_plan(plan: str | None) -> str:
    return normalize_plan_code(plan)


def _is_admin_user(user: AppUser | None) -> bool:
    return str(getattr(user, "role", "") or "").strip().lower() == "admin"


def _next_plan(plan: str) -> str:
    return next_public_plan(plan)


def _ensure_subscription_row(db, user: AppUser) -> Subscription:
    row = db.query(Subscription).filter_by(user_id=user.id).first()
    if row:
        row.plan = _normalize_plan(row.plan)
        return row

    created_at = user.created_at or _utc_now()
    trial_ends_at = created_at + timedelta(days=7)
    normalized_user_plan = _normalize_plan(getattr(user, "plan", None))
    row = Subscription(
        user_id=user.id,
        plan=normalized_user_plan,
        status="active" if str(getattr(user, "billing_status", "")).lower() in {"active", "trialing"} and normalized_user_plan != PLAN_FREE else "trialing",
        current_period_start=created_at,
        current_period_end=getattr(user, "current_period_end", None),
        trial_ends_at=trial_ends_at,
        stripe_customer_id=getattr(user, "stripe_customer_id", None),
        stripe_subscription_id=getattr(user, "stripe_subscription_id", None),
        updated_at=_utc_now(),
    )
    if row.plan == PLAN_FREE:
        row.status = "trialing" if trial_ends_at > _utc_now() else "canceled"
        row.current_period_start = created_at
        row.current_period_end = trial_ends_at
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def sync_subscription_state(
    user_id: int,
    *,
    plan: str | None = None,
    status: str | None = None,
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
    trial_ends_at: datetime | None = None,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=user_id).first()
        if not user:
            return
        row = _ensure_subscription_row(db, user)
        if plan is not None:
            row.plan = _normalize_plan(plan)
        if status is not None:
            row.status = str(status).strip().lower()
        if current_period_start is not None:
            row.current_period_start = current_period_start
        if current_period_end is not None:
            row.current_period_end = current_period_end
        if trial_ends_at is not None:
            row.trial_ends_at = trial_ends_at
        if stripe_customer_id is not None:
            row.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id is not None:
            row.stripe_subscription_id = stripe_subscription_id
        row.updated_at = _utc_now()
        db.commit()
    finally:
        db.close()


def getPlanForUser(user: AppUser) -> dict[str, Any]:
    if _is_admin_user(user):
        return {
            "plan": PLAN_ADMIN,
            "status": "active",
            "current_period_start": None,
            "current_period_end": None,
            "trial_ends_at": None,
            "stripe_customer_id": getattr(user, "stripe_customer_id", None),
            "stripe_subscription_id": getattr(user, "stripe_subscription_id", None),
        }
    db = SessionLocal()
    try:
        db_user = db.query(AppUser).filter_by(id=user.id).first()
        if not db_user:
            return {
                "plan": PLAN_FREE,
                "status": "trialing",
                "current_period_start": None,
                "current_period_end": None,
                "trial_ends_at": None,
                "stripe_customer_id": None,
                "stripe_subscription_id": None,
            }
        sub = _ensure_subscription_row(db, db_user)
        plan = _normalize_plan(sub.plan)
        now = _utc_now()
        status = str(sub.status or "trialing").strip().lower()
        if plan == PLAN_FREE and sub.trial_ends_at and sub.trial_ends_at < now and status == "trialing":
            status = "canceled"
            sub.status = status
            sub.updated_at = now
            db.commit()
        return {
            "plan": plan,
            "status": status,
            "current_period_start": sub.current_period_start,
            "current_period_end": sub.current_period_end,
            "trial_ends_at": sub.trial_ends_at,
            "stripe_customer_id": sub.stripe_customer_id,
            "stripe_subscription_id": sub.stripe_subscription_id,
        }
    finally:
        db.close()


def getCurrentPeriod(user: AppUser) -> dict[str, datetime | None]:
    plan_data = getPlanForUser(user)
    now = _utc_now()
    plan = plan_data["plan"]
    start = plan_data.get("current_period_start")
    end = plan_data.get("current_period_end")
    trial_ends_at = plan_data.get("trial_ends_at")
    if plan == PLAN_FREE:
        start = start or (getattr(user, "created_at", None) or now)
        end = trial_ends_at or end or (start + timedelta(days=7))
    else:
        if not end:
            end = now + timedelta(days=30)
        if not start:
            start = end - timedelta(days=30)
    return {"start": start, "end": end}


def getLimits(plan: str) -> dict[str, Any]:
    spec = get_plan_spec(plan)
    return {
        "posts_per_month": int(spec.max_posts_month),
        "videos_per_month": int(spec.max_videos_period),
        "projects": int(spec.max_projects),
        "accounts_connected": int(spec.accounts_connected),
        "youtube_connect": bool(spec.youtube_connect),
        "schedule_enabled": bool(spec.can_schedule),
        "autopost_enabled": bool(spec.can_autopublish),
        "posts_generated": int(spec.max_posts_month),
        "videos_generated": int(spec.max_videos_period),
        "posts_published": int(spec.max_posts_month),
        "videos_published": int(spec.max_videos_period),
    }


def _ensure_counter_row(db, user_id: int, period: PeriodWindow) -> UsageCounter:
    row = (
        db.query(UsageCounter)
        .filter(
            UsageCounter.user_id == user_id,
            UsageCounter.period_start == period.start,
            UsageCounter.period_end == period.end,
        )
        .first()
    )
    if row:
        return row
    row = UsageCounter(
        user_id=user_id,
        period_start=period.start,
        period_end=period.end,
        posts_generated=0,
        posts_published=0,
        videos_generated=0,
        videos_published=0,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def getUsage(user: AppUser, period: dict[str, datetime | None]) -> dict[str, int]:
    start = period.get("start")
    end = period.get("end")
    if not start or not end:
        return {"posts_generated": 0, "posts_published": 0, "videos_generated": 0, "videos_published": 0}
    window = PeriodWindow(start=start, end=end)
    db = SessionLocal()
    try:
        row = _ensure_counter_row(db, user.id, window)
        return {
            "posts_generated": int(row.posts_generated or 0),
            "posts_published": int(row.posts_published or 0),
            "videos_generated": int(row.videos_generated or 0),
            "videos_published": int(row.videos_published or 0),
        }
    finally:
        db.close()


def _count_projects(user_id: int) -> int:
    db = SessionLocal()
    try:
        return int(db.query(Project).filter(Project.user_id == user_id).count())
    finally:
        db.close()


def _count_connected_accounts(user_id: int) -> int:
    db = SessionLocal()
    try:
        rows = (
            db.query(SocialAccount.provider, SocialAccount.page_id)
            .filter(
                SocialAccount.user_id == user_id,
                SocialAccount.status.in_(["connected_ready", "connected", "connected_need_page"]),
            )
            .all()
        )
        uniq = set()
        for provider, page_id in rows:
            key = (str(provider or "").strip().lower(), str(page_id or "").strip().lower())
            uniq.add(key)
        return len(uniq)
    finally:
        db.close()


def _paywall_payload(
    *,
    code: str,
    action: str,
    required_plan: str,
    current_plan: str,
    limit: int | None = None,
    used: int | None = None,
    remaining: int | None = None,
    period_end: datetime | None = None,
    message: str = "",
) -> dict[str, Any]:
    payload = {
        "error": code,
        "action": action,
        "required_plan": required_plan,
        "current_plan": current_plan,
        "limit": limit if limit is not None else 0,
        "used": used if used is not None else 0,
        "remaining": remaining if remaining is not None else 0,
        "period_end": period_end.isoformat() if period_end else None,
        "upgrade_url": _upgrade_url(required_plan),
        "message": message,
    }
    return payload


def authorizeAction(user: AppUser, action: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    if _is_admin_user(user):
        return {"allowed": True, "plan": PLAN_ADMIN, "status": "active", "limits": getLimits(PLAN_ADMIN), "usage": {}}

    plan_data = getPlanForUser(user)
    current_plan = plan_data["plan"]
    status = plan_data["status"]
    limits = getLimits(current_plan)
    period = getCurrentPeriod(user)
    usage = getUsage(user, period)
    period_end = period.get("end")

    if current_plan == PLAN_FREE and status == "canceled":
        required = PLAN_STARTER
        return {
            "allowed": False,
            "http_status": 402,
            "error_payload": _paywall_payload(
                code=PAYWALL_FEATURE,
                action=action,
                required_plan=required,
                current_plan=current_plan,
                period_end=period_end,
                message="Пробный период завершён. Выберите платный тариф, чтобы продолжить работу.",
            ),
        }

    if action in {ACTION_SCHEDULE_CREATE, ACTION_POST_PUBLISH, ACTION_VIDEO_PUBLISH} and not limits.get("autopost_enabled", False):
        required = PLAN_GROWTH
        return {
            "allowed": False,
            "http_status": 403,
            "error_payload": _paywall_payload(
                code=PAYWALL_FEATURE,
                action=action,
                required_plan=required,
                current_plan=current_plan,
                period_end=period_end,
                message="Автопостинг доступен на тарифе Growth (€79) и выше.",
            ),
        }

    if action == ACTION_ANALYTICS_ADVANCED and current_plan not in {PLAN_GROWTH, PLAN_AGENCY}:
        required = PLAN_GROWTH
        return {
            "allowed": False,
            "http_status": 403,
            "error_payload": _paywall_payload(
                code=PAYWALL_FEATURE,
                action=action,
                required_plan=required,
                current_plan=current_plan,
                period_end=period_end,
                message="Расширенная аналитика доступна на тарифе Growth (€79) и выше.",
            ),
        }

    if action == ACTION_ACCOUNT_CONNECT:
        provider = str(context.get("provider") or "").strip().lower()
        if provider == "youtube" and not limits.get("youtube_connect", False):
            required = PLAN_STARTER
            return {
                "allowed": False,
                "http_status": 402,
                "error_payload": _paywall_payload(
                    code=PAYWALL_FEATURE,
                    action=action,
                    required_plan=required,
                    current_plan=current_plan,
                    period_end=period_end,
                    message="Подключение YouTube недоступно на текущем тарифе.",
                ),
            }

    field = ACTION_LIMIT_FIELD.get(action)
    if action == ACTION_SCHEDULE_CREATE:
        content_kind = str(context.get("content_kind") or "").strip().lower()
        field = "videos_published" if content_kind == "video" else "posts_published"

    if field:
        limit = int(limits.get(field, 0))
        if action == ACTION_PROJECT_CREATE:
            used = int(context.get("projects_count")) if context.get("projects_count") is not None else _count_projects(user.id)
        elif action == ACTION_ACCOUNT_CONNECT:
            used = int(context.get("accounts_count")) if context.get("accounts_count") is not None else _count_connected_accounts(user.id)
        else:
            used = int(usage.get(field, 0))

        remaining = max(limit - used, 0)
        if used >= limit:
            required = _next_plan(current_plan)
            return {
                "allowed": False,
                "http_status": 402,
                "error_payload": _paywall_payload(
                    code=PAYWALL_LIMIT,
                    action=action,
                    required_plan=required,
                    current_plan=current_plan,
                    limit=limit,
                    used=used,
                    remaining=remaining,
                    period_end=period_end,
                    message="Достигнут лимит текущего тарифа.",
                ),
            }

    return {
        "allowed": True,
        "plan": current_plan,
        "status": status,
        "period": period,
        "limits": limits,
        "usage": usage,
    }


def recordUsageEvent(user: AppUser, type: str, delta: int, meta: dict[str, Any] | None = None) -> None:
    event_type = str(type or "").strip().upper()
    if event_type not in COUNTER_FIELDS:
        return
    if int(delta or 0) <= 0:
        return

    period = getCurrentPeriod(user)
    start = period.get("start")
    end = period.get("end")
    if not start or not end:
        return

    for _ in range(2):
        db = SessionLocal()
        try:
            row = _ensure_counter_row(db, user.id, PeriodWindow(start=start, end=end))
            field = COUNTER_FIELDS[event_type]
            current_value = int(getattr(row, field) or 0)
            setattr(row, field, current_value + int(delta))
            row.updated_at = _utc_now()
            db.add(
                UsageEvent(
                    user_id=user.id,
                    type=event_type,
                    delta=int(delta),
                    meta_json=json.dumps(meta or {}, ensure_ascii=False),
                    created_at=_utc_now(),
                )
            )
            db.commit()
            return
        except IntegrityError:
            db.rollback()
        finally:
            db.close()


def getEntitlementsPayload(user: AppUser) -> dict[str, Any]:
    plan_data = getPlanForUser(user)
    plan = plan_data["plan"]
    limits = getLimits(plan)
    if plan == PLAN_ADMIN:
        usage_payload = {
            "posts_generated": 0,
            "posts_published": 0,
            "videos_generated": 0,
            "videos_published": 0,
            "posts_per_month": 0,
            "videos_per_month": 0,
            "projects": _count_projects(user.id),
            "accounts_connected": _count_connected_accounts(user.id),
        }
        unlimited_remaining = {
            "posts_generated": limits["posts_generated"],
            "videos_generated": limits["videos_generated"],
            "posts_published": limits["posts_published"],
            "videos_published": limits["videos_published"],
            "projects": limits["projects"],
            "accounts_connected": limits["accounts_connected"],
        }
        return {
            "plan": plan,
            "status": "active",
            "trial_days_left": 0,
            "trial_ends_at": None,
            "period_end": None,
            "limits": {
                **limits,
                "posts_per_month": limits.get("posts_per_month", 0),
                "videos_per_month": limits.get("videos_per_month", 0),
            },
            "usage": usage_payload,
            "remaining": unlimited_remaining,
            "percent_used": {k: 0 for k in unlimited_remaining.keys()},
            "upgrade_url": _frontend_base_url() + "/billing",
        }
    period = getCurrentPeriod(user)
    usage = getUsage(user, period)
    now = _utc_now()
    period_end = period.get("end")

    trial_days_left = 0
    if plan == PLAN_FREE and period_end:
        trial_days_left = max(0, int((period_end - now).total_seconds() // 86400))

    remaining = {}
    percent_used = {}
    for key in ["posts_generated", "videos_generated", "posts_published", "videos_published"]:
        limit = int(limits.get(key, 0))
        used = int(usage.get(key, 0))
        rem = max(limit - used, 0)
        remaining[key] = rem
        percent_used[key] = 100 if limit <= 0 else min(100, int((used / max(limit, 1)) * 100))

    for key in ["projects", "accounts_connected"]:
        used = _count_projects(user.id) if key == "projects" else _count_connected_accounts(user.id)
        limit = int(limits.get(key, 0))
        rem = max(limit - used, 0)
        remaining[key] = rem
        percent_used[key] = 100 if limit <= 0 else min(100, int((used / max(limit, 1)) * 100))

    usage_payload = {
        **usage,
        "posts_per_month": usage.get("posts_generated", 0),
        "videos_per_month": usage.get("videos_generated", 0),
        "projects": _count_projects(user.id),
        "accounts_connected": _count_connected_accounts(user.id),
    }
    limits_payload = {
        **limits,
        "posts_per_month": limits.get("posts_per_month", 0),
        "videos_per_month": limits.get("videos_per_month", 0),
    }

    return {
        "plan": plan,
        "status": plan_data["status"],
        "trial_days_left": trial_days_left,
        "trial_ends_at": plan_data["trial_ends_at"].isoformat() if plan_data.get("trial_ends_at") else None,
        "period_end": period_end.isoformat() if period_end else None,
        "limits": limits_payload,
        "usage": usage_payload,
        "remaining": remaining,
        "percent_used": percent_used,
        "upgrade_url": _upgrade_url(_next_plan(plan)),
    }
