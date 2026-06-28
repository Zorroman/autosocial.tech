
import base64
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from cryptography.fernet import Fernet
from sqlalchemy import and_, desc, extract, func

from backend.services.media import (
    PexelsConfigError,
    PexelsEmptyResultError,
    PexelsRateLimitError,
    PexelsRequestError,
    fetch_pixabay_post_image,
    fetch_post_image,
)
from database import SessionLocal
from gpt_generator import (
    generate_post_with_usage,
    generate_structured_text_with_usage,
)
from saas_models import (
    AppUser,
    AuditLog,
    BlogPost,
    ContentPlan,
    CreditLedger,
    PaymentEvent,
    Plan,
    PlatformRule,
    Post,
    Project,
    SystemLog,
    NicheHook,
    Niche,
    Template,
    TopicSuggestion,
)
from saas_settings import settings
from plans_catalog import PLAN_SPECS, get_plan_spec, normalize_plan_code
from services.entitlements import getEntitlementsPayload
from niche_catalog import build_niche_catalog_seed


def _resolve_post_media_url(
    *,
    db,
    project_id: int,
    platform: str,
    topic: str,
    category: str | None,
    language: str,
    generated_text: str,
) -> str | None:
    _ = language
    if platform == "youtube":
        return None
    try:
        image = fetch_post_image(
            niche=category or topic,
            topic=topic,
            platform=platform,
            post_text=generated_text,
            db=db,
            project_id=project_id,
        )
        if image and image.local_url:
            return image.local_url
    except (PexelsConfigError, PexelsRateLimitError, PexelsRequestError, PexelsEmptyResultError):
        pass

    try:
        fallback = fetch_pixabay_post_image(
            niche=category or topic,
            topic=topic,
            platform=platform,
            post_text=generated_text,
            db=db,
            project_id=project_id,
        )
        return fallback.local_url if fallback else None
    except Exception:
        return None

DEFAULT_CATEGORIES = {
    "business": ["Как привлечь первых 100 клиентов", "Ошибки малого бизнеса в рекламе", "Личный бренд основателя"],
    "marketing": ["Контент-план на 7 дней", "3 формата Reels для охватов", "Как повысить CTR в объявлении"],
    "fitness": ["Тренировка дома без инвентаря", "Питание для набора энергии", "Ошибки новичков в зале"],
}

DEFAULT_PLANS = {
    code: {
        "price_eur_month": spec.price_eur_month,
        "monthly_credits": spec.monthly_credits,
        "max_projects": spec.max_projects,
        "max_posts_month": spec.max_posts_month,
        "max_daily_posts": spec.max_daily_posts,
        "can_schedule": spec.can_schedule,
        "can_autopublish": spec.can_autopublish,
        "templates_enabled": spec.templates_enabled,
        "team_seats": spec.team_seats,
    }
    for code, spec in PLAN_SPECS.items()
}

CREDIT_PACKS = {
    "pack_s": {"price_eur": 5, "credits": 200000},
    "pack_m": {"price_eur": 10, "credits": 450000},
    "pack_l": {"price_eur": 20, "credits": 1000000},
}

BLOG_TOPICS = [
    "Instagram growth strategy for small business",
    "Facebook marketing framework for local brands",
    "AI marketing automation for entrepreneurs",
    "Content strategy for service-based businesses",
    "Personal branding on social media in 2026",
    "How to build daily content system with AI",
]

PLATFORM_RULES_DEFAULT = {
    "instagram": {
        "max_chars": 2200,
        "recommended_chars_min": 120,
        "recommended_chars_max": 220,
        "max_hashtags": 5,
        "max_output_tokens_default": 220,
    },
    "facebook": {
        "max_chars": 5000,
        "recommended_chars_min": 200,
        "recommended_chars_max": 400,
        "max_hashtags": 5,
        "max_output_tokens_default": 350,
    },
    "youtube": {
        "max_chars": 5000,
        "recommended_chars_min": 180,
        "recommended_chars_max": 600,
        "max_hashtags": 3,
        "max_output_tokens_default": 500,
    },
}

NICHE_HOOKS_DEFAULT = {
    "beauty": [
        "3 ошибки, из-за которых клиенты не возвращаются в салон",
        "Если у тебя салон красоты — прочитай это",
    ],
    "auto": [
        "5 причин, почему автосервис теряет повторных клиентов",
        "Что влияет на запись в автосервис уже сегодня",
    ],
    "artist": [
        "Как творческому проекту стабильно получать заявки из соцсетей",
        "Почему ручная работа не продается без контент-системы",
    ],
    "coach": [
        "3 шага, чтобы эксперт начал получать входящие заявки",
        "Что публиковать коучу, чтобы продавать без выгорания",
    ],
    "ecommerce": [
        "Почему магазин теряет продажи в Instagram и Facebook",
        "Контент, который увеличивает конверсию в заказ",
    ],
    "fallback": [
        "3 практических шага, чтобы получать больше клиентов из соцсетей",
        "Что публиковать сегодня, чтобы завтра получить заявки",
    ],
}

FILLER_PHRASES = {
    "в современном мире",
    "важно понимать",
    "эта статья",
    "как известно",
    "безусловно",
}


def log_event(message: str, actor_user_id: Optional[int] = None, level: str = "info", context: str = "") -> None:
    db = SessionLocal()
    try:
        db.add(SystemLog(actor_user_id=actor_user_id, level=level, message=message, context=context))
        db.commit()
    finally:
        db.close()


def audit(user_id: Optional[int], action: str, ip: str = "", meta: Optional[dict] = None) -> None:
    db = SessionLocal()
    try:
        db.add(AuditLog(user_id=user_id, action=action, ip=ip or None, meta_json=json.dumps(meta or {}, ensure_ascii=False)))
        db.commit()
    finally:
        db.close()


def seed_plans() -> None:
    db = SessionLocal()
    try:
        for name, cfg in DEFAULT_PLANS.items():
            row = db.query(Plan).filter_by(name=name).first()
            if not row:
                row = Plan(name=name)
                db.add(row)
            row.price_eur_month = cfg["price_eur_month"]
            row.monthly_credits = cfg["monthly_credits"]
            row.max_projects = cfg["max_projects"]
            row.max_posts_month = cfg["max_posts_month"]
            row.max_daily_posts = cfg["max_daily_posts"]
            row.can_schedule = cfg["can_schedule"]
            row.can_autopublish = cfg["can_autopublish"]
            row.templates_enabled = bool(cfg.get("templates_enabled", False))
            row.team_seats = cfg["team_seats"]
        db.commit()
    finally:
        db.close()


def seed_platform_rules() -> None:
    db = SessionLocal()
    try:
        for platform, cfg in PLATFORM_RULES_DEFAULT.items():
            row = db.query(PlatformRule).filter_by(platform=platform).first()
            if not row:
                row = PlatformRule(platform=platform)
                db.add(row)
            row.max_chars = cfg["max_chars"]
            row.recommended_chars_min = cfg["recommended_chars_min"]
            row.recommended_chars_max = cfg["recommended_chars_max"]
            row.max_hashtags = cfg["max_hashtags"]
            row.max_output_tokens_default = cfg["max_output_tokens_default"]
        db.commit()
    finally:
        db.close()


def seed_niche_hooks() -> None:
    db = SessionLocal()
    try:
        for niche, hooks in NICHE_HOOKS_DEFAULT.items():
            existing = {x.hook for x in db.query(NicheHook).filter_by(niche=niche).all()}
            for hook in hooks:
                if hook in existing:
                    continue
                db.add(NicheHook(niche=niche, hook=hook))
        db.commit()
    finally:
        db.close()


def seed_niche_catalog() -> None:
    db = SessionLocal()
    try:
        catalog = build_niche_catalog_seed()
        for niche_data in catalog:
            slug = str(niche_data.get("slug") or "").strip().lower()
            if not slug:
                continue
            row = db.query(Niche).filter(Niche.slug == slug).first()
            if not row:
                row = Niche(
                    slug=slug,
                    title=str(niche_data.get("title") or slug).strip()[:160],
                    description=str(niche_data.get("description") or "").strip(),
                    icon=str(niche_data.get("icon") or "briefcase").strip()[:80],
                    sort_order=int(niche_data.get("sort_order") or 100),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(row)
                db.flush()
            row.title = str(niche_data.get("title") or slug).strip()[:160]
            row.description = str(niche_data.get("description") or "").strip()
            row.icon = str(niche_data.get("icon") or "briefcase").strip()[:80]
            row.sort_order = int(niche_data.get("sort_order") or 100)
            row.updated_at = datetime.utcnow()

            template_specs = niche_data.get("templates") if isinstance(niche_data.get("templates"), list) else []
            expected_slugs = set()
            for spec in template_specs:
                tpl_slug = str(spec.get("slug") or "").strip().lower()
                if not tpl_slug:
                    continue
                expected_slugs.add(tpl_slug)
                tpl = (
                    db.query(Template)
                    .filter(Template.niche_id == row.id, Template.slug == tpl_slug)
                    .first()
                )
                if not tpl:
                    tpl = Template(
                        niche_id=row.id,
                        slug=tpl_slug,
                        created_at=datetime.utcnow(),
                    )
                    db.add(tpl)
                tpl.title = str(spec.get("title") or tpl_slug).strip()[:200]
                tpl.description = str(spec.get("description") or "").strip()
                tpl.type = str(spec.get("type") or "post").strip().lower()[:20]
                tpl.platform = str(spec.get("platform") or "all").strip().lower()[:20]
                tpl.goal = str(spec.get("goal") or "awareness").strip().lower()[:20]
                tpl.tone = str(spec.get("tone") or "local-friendly").strip().lower()[:40]
                tpl.hook_line = str(spec.get("hook_line") or "").strip()[:300]
                tpl.cta = str(spec.get("cta") or "").strip()[:300]
                tpl.prompt_system = str(spec.get("prompt_system") or "").strip()
                tpl.prompt_user = str(spec.get("prompt_user") or "").strip()
                tpl.variables_schema_json = json.dumps(spec.get("variables_schema_json") or {}, ensure_ascii=False)
                tpl.preview_text = str(spec.get("preview_text") or "").strip()
                tpl.sort_order = int(spec.get("sort_order") or 100)
                tpl.updated_at = datetime.utcnow()

            if expected_slugs:
                stale_rows = (
                    db.query(Template)
                    .filter(Template.niche_id == row.id, ~Template.slug.in_(list(expected_slugs)))
                    .all()
                )
                for stale in stale_rows:
                    db.delete(stale)

        db.commit()
    finally:
        db.close()


def get_plan(db, user: AppUser) -> Plan:
    if user.plan_id:
        plan = db.query(Plan).filter_by(id=user.plan_id).first()
        if plan:
            return plan
    plan = db.query(Plan).filter_by(name=normalize_plan_code(user.plan or "free")).first()
    if not plan:
        raise RuntimeError("Plan is missing in DB")
    return plan


def ensure_user_plan_and_credits(user_id: int) -> None:
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=user_id).first()
        if not user:
            return
        plan = get_plan(db, user)
        if not user.plan_id:
            user.plan_id = plan.id
            user.plan = plan.name
        if user.credits_left == 0 and user.posts_used_month == 0 and user.billing_status == "inactive":
            user.credits_left = plan.monthly_credits
            user.billing_status = "active"
            db.add(
                CreditLedger(
                    user_id=user.id,
                    type="monthly_grant",
                    delta_credits=plan.monthly_credits,
                    meta_json=json.dumps({"reason": "initial_grant", "plan": plan.name}, ensure_ascii=False),
                )
            )
        db.commit()
    finally:
        db.close()


def get_or_create_default_project(user_id: int) -> Project:
    db = SessionLocal()
    try:
        project = db.query(Project).filter_by(user_id=user_id).order_by(Project.created_at.asc()).first()
        if not project:
            project = Project(user_id=user_id, name="Project")
            db.add(project)
            db.commit()
            db.refresh(project)
        return project
    finally:
        db.close()


def check_project_limit(user: AppUser) -> Dict[str, int]:
    db = SessionLocal()
    try:
        spec = get_plan_spec(user.plan)
        used = db.query(Project).filter(Project.user_id == user.id).count()
        return {"used": used, "limit": spec.max_projects}
    finally:
        db.close()


def check_post_limits(user: AppUser) -> Dict[str, int]:
    month_now = datetime.now(timezone.utc).month
    year_now = datetime.now(timezone.utc).year
    today = datetime.now(timezone.utc).date()

    db = SessionLocal()
    try:
        plan = get_plan(db, user)
        if user.role == "admin":
            # Admin can manage/test publishing without SaaS quota blocks.
            return {
                "monthly_used": 0,
                "monthly_limit": 10**9,
                "daily_used": 0,
                "daily_limit": 10**9,
            }
        monthly_used = (
            db.query(Post)
            .filter(
                and_(
                    Post.user_id == user.id,
                    extract("month", Post.created_at) == month_now,
                    extract("year", Post.created_at) == year_now,
                )
            )
            .count()
        )
        # Daily cap is about how many posts are actually published today (API/platform-safe).
        # Scheduled drafts should not "consume" the day limit until they are published.
        daily_used = (
            db.query(Post)
            .filter(Post.user_id == user.id, Post.published_at.isnot(None), func.date(Post.published_at) == str(today))
            .count()
        )
        return {
            "monthly_used": monthly_used,
            "monthly_limit": plan.max_posts_month,
            "daily_used": daily_used,
            "daily_limit": plan.max_daily_posts,
        }
    finally:
        db.close()


def get_billing_summary(user: AppUser) -> Dict[str, object]:
    entitlements = getEntitlementsPayload(user)
    spec = get_plan_spec(entitlements.get("plan"))
    approx_posts_left = int(max(user.credits_left, 0) / max(settings.AVG_TOKENS_PER_POST, 1))
    stripe_enabled = bool(settings.STRIPE_SECRET_KEY)
    is_admin_plan = str(entitlements.get("plan") or "").strip().lower() == "admin"
    stripe_price_map = {
        "starter": bool(get_plan_spec("starter").payment_available and stripe_enabled and getattr(settings, "STRIPE_PRICE_STARTER", "")),
        "growth": bool(get_plan_spec("growth").payment_available and stripe_enabled and getattr(settings, "STRIPE_PRICE_GROWTH", "")),
        "agency": bool(get_plan_spec("agency").payment_available and stripe_enabled and (getattr(settings, "STRIPE_PRICE_AGENCY_V2", "") or getattr(settings, "STRIPE_PRICE_AGENCY", ""))),
    }
    return {
        "plan": entitlements.get("plan"),
        "plan_title": spec.title,
        "billing_status": user.billing_status,
        "credits_left": user.credits_left,
        "approx_posts_left": approx_posts_left,
        "trial_days": spec.trial_days,
        "trial_ends_at": entitlements.get("trial_ends_at"),
        "trial_days_left": entitlements.get("trial_days_left"),
        "stripe": {
            "enabled": stripe_enabled,
            "subscriptions_ready": any(stripe_price_map.values()) and not is_admin_plan,
            "portal_ready": any(stripe_price_map.values()) and not is_admin_plan,
            "prices": stripe_price_map,
            "payment_available": bool(any(stripe_price_map.values()) and not is_admin_plan),
        },
        "limits": {
            "posts_per_month": entitlements.get("limits", {}).get("posts_per_month", 0),
            "videos_per_month": entitlements.get("limits", {}).get("videos_per_month", 0),
            "projects": entitlements.get("limits", {}).get("projects", 0),
            "accounts_connected": entitlements.get("limits", {}).get("accounts_connected", 0),
            "daily_posts": spec.max_daily_posts,
            "can_schedule": bool(spec.can_schedule),
            "can_autopublish": bool(spec.can_autopublish),
            "templates_enabled": bool(spec.templates_enabled),
            "niche_templates": spec.niche_templates,
            "analytics_level": spec.analytics_level,
            "youtube_connect": bool(spec.youtube_connect),
        },
        "usage": {
            "posts_per_month": entitlements.get("usage", {}).get("posts_generated", 0),
            "videos_per_month": entitlements.get("usage", {}).get("videos_generated", 0),
            "projects": entitlements.get("usage", {}).get("projects", 0),
            "accounts_connected": entitlements.get("usage", {}).get("accounts_connected", 0),
            "daily_posts": check_post_limits(user).get("daily_used", 0),
        },
        "remaining": {
            "posts_per_month": entitlements.get("remaining", {}).get("posts_generated", 0),
            "videos_per_month": entitlements.get("remaining", {}).get("videos_generated", 0),
            "projects": entitlements.get("remaining", {}).get("projects", 0),
            "accounts_connected": entitlements.get("remaining", {}).get("accounts_connected", 0),
        },
    }


def can_access_project(user: AppUser, project_id: int) -> bool:
    db = SessionLocal()
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            return False
        return user.role == "admin" or project.user_id == user.id
    finally:
        db.close()


def _normalize_niche(raw: Optional[str]) -> str:
    text = (raw or "").strip().lower()
    if any(x in text for x in ["beauty", "salon", "космет", "бьюти"]):
        return "beauty"
    if any(x in text for x in ["auto", "car", "авто", "сервис"]):
        return "auto"
    if any(x in text for x in ["artist", "creative", "handmade", "творч", "арт"]):
        return "artist"
    if any(x in text for x in ["coach", "psycholog", "expert", "коуч", "психол", "эксперт"]):
        return "coach"
    if any(x in text for x in ["shop", "store", "ecommerce", "магазин", "бизнес"]):
        return "ecommerce"
    return "fallback"


def _pick_hook(niche: Optional[str]) -> str:
    normalized = _normalize_niche(niche)
    db = SessionLocal()
    try:
        rows = db.query(NicheHook).filter_by(niche=normalized).all()
        if not rows:
            rows = db.query(NicheHook).filter_by(niche="fallback").all()
        if not rows:
            return NICHE_HOOKS_DEFAULT["fallback"][0]
        idx = int(datetime.utcnow().timestamp()) % len(rows)
        return rows[idx].hook
    finally:
        db.close()


def _sanitize_hashtags(text: str, max_hashtags: int) -> str:
    tags = []
    for token in re.findall(r"#\\w+", text):
        t = token.lower()
        if t not in tags:
            tags.append(t)
    return " ".join(tags[:max_hashtags])


def _split_sentences(text: str) -> List[str]:
    return [x.strip() for x in re.split(r"[\\n\\.\\!\\?]+", text) if x.strip()]


def _sentence_has_value(sentence: str) -> bool:
    s = sentence.lower()
    has_number = bool(re.search(r"\\d", s))
    has_benefit = any(k in s for k in ["выгода", "рост", "клиент", "продаж", "результат", "конверс", "заявк"])
    has_action = any(k in s for k in ["сделай", "используй", "добавь", "проверь", "запусти", "протестируй"])
    return has_number or has_benefit or has_action


def _contains_filler(text: str) -> bool:
    lower = text.lower()
    return any(f in lower for f in FILLER_PHRASES)


def _platform_rule(platform: str) -> Dict[str, int]:
    db = SessionLocal()
    try:
        row = db.query(PlatformRule).filter_by(platform=platform.lower()).first()
        if not row:
            return PLATFORM_RULES_DEFAULT.get(platform.lower(), PLATFORM_RULES_DEFAULT["instagram"])
        return {
            "max_chars": row.max_chars,
            "recommended_chars_min": row.recommended_chars_min,
            "recommended_chars_max": row.recommended_chars_max,
            "max_hashtags": row.max_hashtags,
            "max_output_tokens_default": row.max_output_tokens_default,
        }
    finally:
        db.close()


def _structured_post_text(hook: str, value_lines: List[str], cta: str, hashtags: str, max_chars: int) -> str:
    text = hook.strip() + "\\n\\n" + "\\n".join(value_lines) + "\\n\\n" + cta.strip()
    if hashtags:
        text += "\\n\\n" + hashtags.strip()
    return text[:max_chars]


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
    return t.strip()


def _trim_text_to_limit(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    candidates = [t.rfind("\n", 0, max_chars), t.rfind(". ", 0, max_chars), t.rfind("! ", 0, max_chars), t.rfind("? ", 0, max_chars)]
    cut = max(candidates)
    if cut < int(max_chars * 0.6):
        cut = max_chars
    trimmed = t[:cut].rstrip(" \n.,;:-")
    return f"{trimmed}…"


def _platform_preview_limits(platforms: Optional[List[str]]) -> Dict[str, int]:
    normalized = []
    for item in (platforms or ["instagram"]):
        key = (item or "").strip().lower()
        if key in {"instagram", "facebook", "youtube"} and key not in normalized:
            normalized.append(key)
    if not normalized:
        normalized = ["instagram"]
    cfgs = [_platform_rule(p) for p in normalized]
    max_chars = min(int(c["max_chars"]) for c in cfgs)
    recommended_min = max(int(c["recommended_chars_min"]) for c in cfgs)
    recommended_max = min(int(c["recommended_chars_max"]) for c in cfgs)
    if recommended_max < recommended_min:
        recommended_max = min(max_chars, max(recommended_min, 320))
    max_hashtags = min(int(c["max_hashtags"]) for c in cfgs)
    return {
        "max_chars": max_chars,
        "recommended_chars_min": recommended_min,
        "recommended_chars_max": min(recommended_max, max_chars),
        "max_hashtags": max(1, max_hashtags),
    }


def generate_post_preview_text(
    topic: str,
    category: Optional[str],
    tone: str,
    language: str,
    platforms: Optional[List[str]] = None,
) -> Dict[str, object]:
    limits = _platform_preview_limits(platforms)
    lang = (language or "ru").strip().lower()
    tone_value = (tone or "friendly").strip().lower()
    category_value = (category or "business").strip()
    recommended_min = int(limits["recommended_chars_min"])
    recommended_max = int(limits["recommended_chars_max"])
    max_chars = int(limits["max_chars"])
    max_hashtags = int(limits["max_hashtags"])

    system_prompt = (
        "Ты senior SMM-копирайтер. Верни только готовый текст поста для публикации, без пояснений. "
        "Текст должен выглядеть живо и естественно, без канцелярита и без шаблонной воды."
    )
    user_prompt = (
        f"Сгенерируй пост для соцсетей.\n"
        f"Тема: {topic}\n"
        f"Категория: {category_value}\n"
        f"Тон: {tone_value}\n"
        f"Язык: {lang}\n\n"
        f"Требования:\n"
        f"- длина: примерно {recommended_min}-{recommended_max} символов, максимум {max_chars};\n"
        f"- 1 четкий призыв к действию;\n"
        f"- 2-{max_hashtags} релевантных хештегов в конце;\n"
        f"- можно 0-2 эмодзи;\n"
        f"- не делай нумерацию по умолчанию; список только если он реально уместен по теме;\n"
        f"- не используй фразы типа 'в современном мире' и другие общие клише.\n"
    )

    token_budget = max(180, min(700, int(max_chars / 3)))
    result = generate_structured_text_with_usage(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_output_tokens=token_budget,
        temperature=0.7,
    )
    text = _trim_text_to_limit(_strip_code_fences(result.text or ""), max_chars)
    if not text:
        text = f"{topic}\n\nСделайте один конкретный шаг по теме уже сегодня и проверьте результат через 7 дней.\n\n#контент #бизнес"

    return {
        "text": text,
        "input_tokens": int(result.input_tokens or 0),
        "output_tokens": int(result.output_tokens or 0),
        "limits": limits,
    }


def _multiplier(variant_count: int, translation: bool) -> float:
    factor = 1.0
    if variant_count > 1:
        factor *= 3.0
    if translation:
        factor *= 1.5
    return factor


def estimate_credits(topic: str, long_post_mode: bool, variant_count: int, translation: bool) -> int:
    base = max(settings.AVG_TOKENS_PER_POST, len(topic) * 2)
    if long_post_mode:
        base = int(base * 1.4)
    return int(base * _multiplier(variant_count, translation) * settings.CREDIT_MULTIPLIER)


def _fernet() -> Fernet:
    key = settings.TOKEN_ENCRYPTION_KEY
    if not key:
        digest = hashlib.sha256(b"autosocial-default-key").digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_meta_token(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_meta_token(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def _plan_output_cap(plan_name: str) -> int:
    return 400 if plan_name == "free" else 800
def create_post_and_charge(
    user_id: int,
    project_id: int,
    platform: str,
    topic: str,
    category: Optional[str],
    tone: str,
    language: str,
    prompt_text: str,
    media_url: Optional[str],
    schedule_at,
    variant_count: int,
    translation: bool,
    long_post_mode: bool,
    generated_text_override: Optional[str] = None,
    save_as_draft: bool = False,
) -> Post:
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=user_id).first()
        if not user:
            raise ValueError("Пользователь не найден")

        ensure_user_plan_and_credits(user.id)
        db.refresh(user)
        plan = get_plan(db, user)
        enforce_limits = user.role != "admin"

        limits = check_post_limits(user)
        if enforce_limits and limits["monthly_used"] >= limits["monthly_limit"]:
            raise RuntimeError("Месячный лимит постов исчерпан. Обновите тариф.")
        # Daily limit is enforced for "publish now". Scheduling drafts should not be blocked by daily caps.
        if enforce_limits and not schedule_at and limits["daily_used"] >= limits["daily_limit"]:
            raise RuntimeError("Дневной лимит публикаций исчерпан. Попробуйте завтра.")
        if enforce_limits and schedule_at and not plan.can_schedule:
            raise RuntimeError("Планирование доступно только на платных тарифах")

        estimate = estimate_credits(topic, long_post_mode, variant_count, translation)
        if enforce_limits and user.credits_left < int(estimate * 1.2):
            raise RuntimeError("Monthly limit reached. Upgrade or buy credits.")
        if enforce_limits and user.credits_left <= settings.OVERDRAFT_LIMIT:
            raise RuntimeError("Credits limit exceeded. Buy credits or upgrade.")

        platform = (platform or "instagram").strip().lower()
        if platform not in ("instagram", "facebook", "youtube"):
            platform = "instagram"
        platform_cfg = _platform_rule(platform)
        max_output_tokens = min(_plan_output_cap(plan.name), int(platform_cfg["max_output_tokens_default"]))
        selected_hook = _pick_hook(category or topic)

        result = None
        for _attempt in range(3):
            generated = generate_post_with_usage(
                topic=f"{selected_hook}. Topic: {topic}",
                category=category,
                tone=tone,
                language=language,
                long_post_mode=long_post_mode,
                max_output_tokens=max_output_tokens,
            )
            if _contains_filler(generated.text):
                continue
            if not all(_sentence_has_value(s) for s in _split_sentences(generated.text)[:4]):
                continue
            result = generated
            break
        if result is None:
            result = generate_post_with_usage(
                topic=f"{selected_hook}. Topic: {topic}",
                category=category,
                tone=tone,
                language=language,
                long_post_mode=long_post_mode,
                max_output_tokens=max_output_tokens,
            )

        raw_sentences = _split_sentences(result.text)
        value_lines = raw_sentences[:4] if raw_sentences else [f"Совет: сфокусируйтесь на теме '{topic}' и тестируйте 1 гипотезу в день."]
        cta = "Напишите в комментариях 'ПЛАН', и мы отправим следующий шаг."
        hashtags = _sanitize_hashtags(result.text + " #autosocial #smm #marketing #youtube", platform_cfg["max_hashtags"])
        structured_text = _structured_post_text(
            hook=selected_hook,
            value_lines=value_lines[:4],
            cta=cta,
            hashtags=hashtags,
            max_chars=platform_cfg["max_chars"],
        )

        tokens_total = result.input_tokens + result.output_tokens
        charged = int(tokens_total * settings.CREDIT_MULTIPLIER * _multiplier(variant_count, translation))

        if enforce_limits:
            user.credits_left -= charged
            user.posts_used_month += 1

        final_text = (generated_text_override or "").strip() or structured_text
        resolved_media_url = (media_url or "").strip()
        if platform != "youtube" and not resolved_media_url:
            resolved_media_url = _resolve_post_media_url(
                db=db,
                project_id=project_id,
                platform=platform,
                topic=topic,
                category=category,
                language=language,
                generated_text=final_text,
            )
        # New posts should be queued first; real publish endpoint sets done/published_at.
        post_status = "scheduled" if schedule_at else "queued"
        published_at = None

        post = Post(
            user_id=user_id,
            project_id=project_id,
            platform=platform,
            prompt_text=prompt_text,
            generated_text=final_text,
            topic=topic,
            category=category,
            language=language,
            tone=tone,
            media_url=resolved_media_url or None,
            tokens_input=result.input_tokens,
            tokens_output=result.output_tokens,
            tokens_total=tokens_total,
            credits_charged=charged,
            status=post_status,
            schedule_at=schedule_at,
            published_at=published_at,
        )
        db.add(post)
        db.flush()

        if enforce_limits:
            db.add(
                CreditLedger(
                    user_id=user.id,
                    type="usage",
                    delta_credits=-charged,
                    post_id=post.id,
                    meta_json=json.dumps(
                        {
                            "topic": topic,
                            "tokens_total": tokens_total,
                            "variant_count": variant_count,
                            "translation": translation,
                        },
                        ensure_ascii=False,
                    ),
                )
            )

        suggestion = (
            db.query(TopicSuggestion)
            .filter_by(user_id=user.id, project_id=project_id, category=category, topic=topic)
            .first()
        )
        if suggestion:
            suggestion.usage_count += 1
            suggestion.last_used_at = datetime.utcnow()
        else:
            db.add(
                TopicSuggestion(
                    user_id=user.id,
                    project_id=project_id,
                    category=category,
                    topic=topic,
                    usage_count=1,
                    last_used_at=datetime.utcnow(),
                )
            )

        if tokens_total > 8000:
            db.add(
                AuditLog(
                    user_id=user.id,
                    action="abnormal_usage",
                    meta_json=json.dumps({"post_topic": topic, "tokens_total": tokens_total}, ensure_ascii=False),
                )
            )

        db.commit()
        db.refresh(post)
        return post
    finally:
        db.close()


def run_generation_job(post_id: int) -> None:
    """
    Background job: generate content for a queued Post, then finalize credit charging.

    Important: when posts are created via `materialize_content_plan`, we reserve credits up-front
    (Post.credits_charged contains the reserved amount). Here we compute the actual cost from
    OpenAI usage and reconcile the difference.
    """
    db = SessionLocal()
    try:
        post = db.query(Post).filter_by(id=post_id).first()
        if not post:
            return
        if (post.generated_text and post.tokens_total and post.status in {"done", "scheduled"}) or post.status == "running":
            return

        user = db.query(AppUser).filter_by(id=post.user_id).first()
        if not user:
            post.status = "failed"
            post.error_message = "User not found"
            db.commit()
            return

        ensure_user_plan_and_credits(user.id)
        db.refresh(user)
        plan = get_plan(db, user)

        post.status = "running"
        post.error_message = None
        db.commit()

        platform_cfg = _platform_rule(post.platform)
        max_output_tokens = min(_plan_output_cap(plan.name), int(platform_cfg["max_output_tokens_default"]))
        selected_hook = _pick_hook(post.category or post.topic)

        result = None
        for _attempt in range(3):
            generated = generate_post_with_usage(
                topic=f"{selected_hook}. Topic: {post.topic}",
                category=post.category,
                tone=post.tone,
                language=post.language,
                long_post_mode=False,
                max_output_tokens=max_output_tokens,
            )
            if _contains_filler(generated.text):
                continue
            if not all(_sentence_has_value(s) for s in _split_sentences(generated.text)[:4]):
                continue
            result = generated
            break
        if result is None:
            result = generate_post_with_usage(
                topic=f"{selected_hook}. Topic: {post.topic}",
                category=post.category,
                tone=post.tone,
                language=post.language,
                long_post_mode=False,
                max_output_tokens=max_output_tokens,
            )

        raw_sentences = _split_sentences(result.text)
        value_lines = raw_sentences[:4] if raw_sentences else [f"Совет: сфокусируйтесь на теме '{post.topic}' и тестируйте 1 гипотезу в день."]
        cta = "Напишите в комментариях 'ПЛАН', и мы отправим следующий шаг."
        hashtags = _sanitize_hashtags(result.text + " #autosocial #smm #marketing #youtube", platform_cfg["max_hashtags"])
        structured_text = _structured_post_text(
            hook=selected_hook,
            value_lines=value_lines[:4],
            cta=cta,
            hashtags=hashtags,
            max_chars=platform_cfg["max_chars"],
        )

        tokens_total = result.input_tokens + result.output_tokens
        actual = int(tokens_total * settings.CREDIT_MULTIPLIER * _multiplier(variant_count=1, translation=False))

        reserved = int(post.credits_charged or 0)
        delta = actual - reserved

        # If we need to charge extra but the user is already beyond overdraft, fail and refund reservation.
        if delta > 0 and (user.credits_left - delta) <= settings.OVERDRAFT_LIMIT:
            raise RuntimeError("Credits limit exceeded. Buy credits or upgrade.")

        user.credits_left -= delta  # may add credits back when delta < 0

        post.generated_text = structured_text
        if post.platform != "youtube" and not (post.media_url or "").strip():
            post.media_url = _resolve_post_media_url(
                db=db,
                project_id=int(post.project_id or 0),
                platform=post.platform,
                topic=post.topic,
                category=post.category,
                language=post.language,
                generated_text=structured_text,
            )
        post.tokens_input = result.input_tokens
        post.tokens_output = result.output_tokens
        post.tokens_total = tokens_total
        post.credits_charged = actual
        post.status = "scheduled" if post.schedule_at else "done"
        if not post.schedule_at:
            post.published_at = datetime.utcnow()

        if delta != 0:
            db.add(
                CreditLedger(
                    user_id=user.id,
                    type="usage_finalize",
                    delta_credits=-delta,
                    post_id=post.id,
                    meta_json=json.dumps({"reserved": reserved, "actual": actual, "tokens_total": tokens_total}, ensure_ascii=False),
                )
            )

        db.commit()
    except Exception as exc:
        # Best-effort refund of reserved credits on failure.
        try:
            post = db.query(Post).filter_by(id=post_id).first()
            if not post:
                db.rollback()
                return
            user = db.query(AppUser).filter_by(id=post.user_id).first()
            reserved = int(post.credits_charged or 0)
            if user and reserved:
                user.credits_left += reserved
                db.add(
                    CreditLedger(
                        user_id=user.id,
                        type="refund",
                        delta_credits=reserved,
                        post_id=post.id,
                        meta_json=json.dumps({"reason": "generation_failed"}, ensure_ascii=False),
                    )
                )
            post.status = "failed"
            post.error_message = str(exc)[:2000]
            post.generated_text = None
            post.tokens_input = 0
            post.tokens_output = 0
            post.tokens_total = 0
            post.credits_charged = 0
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def get_topic_suggestions(user: AppUser, project_id: int, category: Optional[str]) -> Dict[str, List[Dict[str, str]]]:
    db = SessionLocal()
    try:
        base = db.query(TopicSuggestion).filter(TopicSuggestion.project_id == project_id)
        if user.role != "admin":
            base = base.filter(TopicSuggestion.user_id == user.id)
        if category:
            base = base.filter(TopicSuggestion.category == category)

        frequent_rows = base.order_by(desc(TopicSuggestion.usage_count), desc(TopicSuggestion.last_used_at)).limit(10).all()
        recent_rows = base.order_by(desc(TopicSuggestion.last_used_at)).limit(10).all()

        frequent = [{"topic": r.topic, "category": r.category, "usage_count": r.usage_count} for r in frequent_rows]
        recent = [{"topic": r.topic, "category": r.category, "usage_count": r.usage_count} for r in recent_rows]
        presets = [{"topic": t, "category": category, "usage_count": 0} for t in DEFAULT_CATEGORIES.get(category or "", [])]
        return {"presets": presets, "frequent": frequent, "recent": recent}
    finally:
        db.close()


def get_revenue_metrics() -> Dict[str, float]:
    db = SessionLocal()
    try:
        tokens_input = db.query(func.coalesce(func.sum(Post.tokens_input), 0)).scalar() or 0
        tokens_output = db.query(func.coalesce(func.sum(Post.tokens_output), 0)).scalar() or 0
        openai_cost = (tokens_input / 1_000_000.0) * settings.OPENAI_PRICE_INPUT_PER_1M + (tokens_output / 1_000_000.0) * settings.OPENAI_PRICE_OUTPUT_PER_1M

        stripe_revenue = db.query(func.coalesce(func.sum(PaymentEvent.amount_eur), 0.0)).scalar() or 0.0
        margin = ((stripe_revenue - openai_cost) / stripe_revenue * 100.0) if stripe_revenue > 0 else 0.0

        return {
            "tokens_input": float(tokens_input),
            "tokens_output": float(tokens_output),
            "tokens_total": float(tokens_input + tokens_output),
            "estimated_openai_cost_eur": round(openai_cost, 4),
            "stripe_revenue_eur": round(float(stripe_revenue), 2),
            "margin_percent": round(margin, 2),
        }
    finally:
        db.close()


def add_credits(user_id: int, delta: int, ledger_type: str, stripe_payment_intent_id: Optional[str] = None, meta: Optional[dict] = None) -> None:
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=user_id).first()
        if not user:
            raise RuntimeError("User not found")
        user.credits_left += delta
        db.add(
            CreditLedger(
                user_id=user_id,
                type=ledger_type,
                delta_credits=delta,
                stripe_payment_intent_id=stripe_payment_intent_id,
                meta_json=json.dumps(meta or {}, ensure_ascii=False),
            )
        )
        db.commit()
    finally:
        db.close()


def reset_monthly_credits(user_id: int, plan_name: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=user_id).first()
        plan = db.query(Plan).filter_by(name=plan_name).first()
        if not user or not plan:
            return
        user.posts_used_month = 0
        user.credits_left = plan.monthly_credits
        db.add(
            CreditLedger(
                user_id=user.id,
                type="monthly_grant",
                delta_credits=plan.monthly_credits,
                meta_json=json.dumps({"plan": plan_name, "reason": "billing_cycle_grant"}, ensure_ascii=False),
            )
        )
        db.commit()
    finally:
        db.close()
def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ\s-]", "", title.strip().lower())
    slug = re.sub(r"\s+", "-", slug)
    return slug[:300].strip("-") or f"post-{int(datetime.utcnow().timestamp())}"


def _normalize_content_plan_platforms(platforms: Optional[List[str]], default: Optional[List[str]] = None) -> List[str]:
    out: List[str] = []
    for item in platforms or []:
        key = str(item or "").strip().lower()
        if key in {"facebook", "instagram", "youtube"} and key not in out:
            out.append(key)
    if out:
        return out
    return [p for p in (default or ["instagram"]) if p in {"facebook", "instagram", "youtube"}]


def _find_existing_materialized_post(db, *, user_id: int, project_id: int, platform: str, topic: str, schedule_at):
    return (
        db.query(Post)
        .filter(
            Post.user_id == user_id,
            Post.project_id == project_id,
            Post.platform == platform,
            Post.topic == topic,
            Post.schedule_at == schedule_at,
            Post.status != "deleted",
        )
        .order_by(Post.id.asc())
        .first()
    )


def create_monthly_content_plan(
    user: AppUser,
    project_id: int,
    business_type: str,
    niche: str,
    goal: str,
    language: str,
    platforms: Optional[List[str]] = None,
) -> Dict[str, int]:
    if not can_access_project(user, project_id):
        raise RuntimeError("No access to project")
    effective_platforms = _normalize_content_plan_platforms(platforms, default=["instagram"])

    db = SessionLocal()
    try:
        existing_future = (
            db.query(ContentPlan)
            .filter(ContentPlan.user_id == user.id, ContentPlan.project_id == project_id, ContentPlan.scheduled_at >= datetime.utcnow())
            .count()
        )
    finally:
        db.close()

    # If a future plan already exists, don't create duplicates.
    # Still "warm up" the next N items so the user sees something in History after clicking.
    prefetch_days = int(os.getenv("AI_MANAGER_PREFETCH_DAYS", "1") or "1")
    prefetch_days = max(0, min(prefetch_days, 7))
    if existing_future > 0:
        generated_posts = 0
        if prefetch_days > 0:
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                upcoming = (
                    db.query(ContentPlan)
                    .filter(
                        ContentPlan.user_id == user.id,
                        ContentPlan.project_id == project_id,
                        ContentPlan.scheduled_at >= now - timedelta(days=1),
                        ContentPlan.status.in_(["planned", "scheduled"]),
                    )
                    .order_by(ContentPlan.scheduled_at.asc())
                    .limit(prefetch_days)
                    .all()
                )
                for item in upcoming:
                    first_post_id = None
                    first_caption = ""
                    for platform in effective_platforms:
                        existing_post = _find_existing_materialized_post(
                            db,
                            user_id=user.id,
                            project_id=project_id,
                            platform=platform,
                            topic=item.topic,
                            schedule_at=item.scheduled_at,
                        )
                        if existing_post:
                            if first_post_id is None:
                                first_post_id = existing_post.id
                                first_caption = (existing_post.generated_text or "")[:1000]
                            continue
                        post = create_post_and_charge(
                            user_id=user.id,
                            project_id=project_id,
                            platform=platform,
                            topic=item.topic,
                            category=niche,
                            tone="friendly",
                            language=language,
                            prompt_text=f"Goal: {goal}",
                            media_url=None,
                            schedule_at=item.scheduled_at,
                            variant_count=1,
                            translation=False,
                            long_post_mode=False,
                        )
                        if first_post_id is None:
                            first_post_id = post.id
                            first_caption = (post.generated_text or "")[:1000]
                        generated_posts += 1
                    if first_post_id:
                        item.post_id = first_post_id
                        item.caption = first_caption
                        item.status = "scheduled"
                db.commit()
            finally:
                db.close()
        return {"created_plan_items": 0, "generated_posts": generated_posts, "existing_future_items": existing_future}

    now = datetime.utcnow()
    # Plan items are cheap to create; content generation happens on-demand (or via "materialize" endpoints).
    start_day = now.replace(hour=10, minute=0, second=0, microsecond=0)
    if start_day < now:
        start_day = start_day + timedelta(days=1)

    angles = [
        "3 ошибки и как исправить",
        "чеклист на 5 минут",
        "миф vs факт",
        "кейс клиента: что сработало",
        "пошаговый план",
        "до/после",
        "вопрос-ответ",
        "инструмент дня",
        "разбор частой проблемы",
        "мини-гайд",
        "реальный пример из практики",
        "что сделать за 15 минут",
        "главный провал и решение",
        "краткий аудит текущей стратегии",
        "2 рабочих сценария на выбор",
        "как повысить конверсию в лид",
        "что убрать, чтобы росла вовлеченность",
        "частый вопрос клиентов",
        "идея поста на сегодня",
        "серия на неделю",
        "оффер, который продает",
        "как усилить доверие к бренду",
        "ошибка в коммуникации с аудиторией",
        "контент без выгорания",
        "формула сильного CTA",
        "контент-подход для локального бизнеса",
        "как упаковать кейс",
        "контент для холодной аудитории",
        "быстрый шаблон для сторис/ленты",
        "7-дневный спринт роста",
    ]

    created = 0
    generated_posts = 0
    cta = "Напишите в директ, чтобы получить персональную стратегию."
    hashtags = "#autosocial #smm #aimarketing"

    db = SessionLocal()
    try:
        existing_topics = set(
            t[0]
            for t in db.query(ContentPlan.topic)
            .filter(ContentPlan.user_id == user.id, ContentPlan.project_id == project_id)
            .all()
        )
        used_topics = set(existing_topics)
        plan_rows: List[ContentPlan] = []
        for i in range(30):
            scheduled_at = start_day + timedelta(days=i)
            angle = angles[i % len(angles)]
            topic = f"{angle}: {niche} для {business_type} — цель: {goal} (день {i + 1})"
            if topic in used_topics:
                topic = f"{topic} / вариант {i + 1}"
            used_topics.add(topic)
            row = ContentPlan(
                user_id=user.id,
                project_id=project_id,
                business_type=business_type,
                goal=goal,
                language=language,
                topic=topic,
                caption="",
                hashtags=hashtags,
                cta=cta,
                scheduled_at=scheduled_at,
                status="planned",
                post_id=None,
            )
            plan_rows.append(row)
            created += 1

        db.add_all(plan_rows)
        db.commit()

        # Optionally pre-generate the first N days so History isn't empty after onboarding.
        if prefetch_days > 0:
            for item in plan_rows[:prefetch_days]:
                first_post_id = None
                first_caption = ""
                for platform in effective_platforms:
                    existing_post = _find_existing_materialized_post(
                        db,
                        user_id=user.id,
                        project_id=project_id,
                        platform=platform,
                        topic=item.topic,
                        schedule_at=item.scheduled_at,
                    )
                    if existing_post:
                        if first_post_id is None:
                            first_post_id = existing_post.id
                            first_caption = (existing_post.generated_text or "")[:1000]
                        continue
                    post = create_post_and_charge(
                        user_id=user.id,
                        project_id=project_id,
                        platform=platform,
                        topic=item.topic,
                        category=niche,
                        tone="friendly",
                        language=language,
                        prompt_text=f"Goal: {goal}",
                        media_url=None,
                        schedule_at=item.scheduled_at,
                        variant_count=1,
                        translation=False,
                        long_post_mode=False,
                    )
                    if first_post_id is None:
                        first_post_id = post.id
                        first_caption = (post.generated_text or "")[:1000]
                    generated_posts += 1
                if first_post_id:
                    item.post_id = first_post_id
                    item.caption = first_caption
                    item.status = "scheduled"
            db.commit()

        return {"created_plan_items": created, "generated_posts": generated_posts, "existing_future_items": existing_future}
    finally:
        db.close()


def materialize_content_plan(
    user: AppUser,
    project_id: int,
    days: int = 7,
    limit: int = 20,
    platforms: Optional[List[str]] = None,
) -> Dict[str, int]:
    """
    Create QUEUED Post rows for planned content-plan items and reserve credits up-front.
    The actual OpenAI generation is executed asynchronously via `run_generation_job(post_id)`.
    """
    if not can_access_project(user, project_id):
        raise RuntimeError("No access to project")

    days = max(1, min(int(days or 7), 30))
    limit = max(1, min(int(limit or 20), 50))
    effective_platforms = _normalize_content_plan_platforms(platforms, default=["instagram"])

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        end = now + timedelta(days=days)
        rows = (
            db.query(ContentPlan)
            .filter(
                ContentPlan.user_id == user.id,
                ContentPlan.project_id == project_id,
                ContentPlan.status.in_(["planned", "scheduled"]),
                ContentPlan.scheduled_at >= now - timedelta(days=1),
                ContentPlan.scheduled_at <= end,
            )
            .order_by(ContentPlan.scheduled_at.asc())
            .limit(limit)
            .all()
        )

        app_user = db.query(AppUser).filter_by(id=user.id).first()
        if not app_user:
            raise RuntimeError("User not found")
        ensure_user_plan_and_credits(app_user.id)
        db.refresh(app_user)
        enforce_limits = app_user.role != "admin"

        created_posts = 0
        post_ids: List[int] = []
        stop_materialization = False
        for item in rows:
            if stop_materialization:
                break
            first_post_id = item.post_id if item.post_id else None
            for platform in effective_platforms:
                existing_post = _find_existing_materialized_post(
                    db,
                    user_id=app_user.id,
                    project_id=project_id,
                    platform=platform,
                    topic=item.topic,
                    schedule_at=item.scheduled_at,
                )
                if existing_post:
                    if first_post_id is None:
                        first_post_id = existing_post.id
                    continue

                # Monthly limits are enforced by counting Posts, so creating queued posts still consumes the quota.
                limits = check_post_limits(app_user)
                if enforce_limits and limits["monthly_used"] >= limits["monthly_limit"]:
                    stop_materialization = True
                    break

                # Reserve credits so users can't queue unlimited jobs with the same balance.
                reserve = estimate_credits(item.topic or "", long_post_mode=False, variant_count=1, translation=False)
                if enforce_limits and app_user.credits_left < int(reserve * 1.2):
                    stop_materialization = True
                    break
                if enforce_limits and app_user.credits_left <= settings.OVERDRAFT_LIMIT:
                    stop_materialization = True
                    break

                if enforce_limits:
                    app_user.credits_left -= reserve
                    app_user.posts_used_month += 1

                post = Post(
                    user_id=app_user.id,
                    project_id=project_id,
                    platform=platform,
                    prompt_text=f"Goal: {item.goal or ''}",
                    generated_text=None,
                    topic=item.topic,
                    category=item.business_type or "",
                    language=item.language or "ru",
                    tone="friendly",
                    media_url=None,
                    tokens_input=0,
                    tokens_output=0,
                    tokens_total=0,
                    credits_charged=reserve,  # reserved amount; final amount is reconciled in job
                    status="queued",
                    schedule_at=item.scheduled_at,
                    published_at=None,
                )
                db.add(post)
                db.flush()

                if enforce_limits:
                    db.add(
                        CreditLedger(
                            user_id=app_user.id,
                            type="usage_reserve",
                            delta_credits=-reserve,
                            post_id=post.id,
                            meta_json=json.dumps({"topic": item.topic, "reserve": reserve, "platform": platform}, ensure_ascii=False),
                        )
                    )

                if first_post_id is None:
                    first_post_id = post.id
                item.caption = item.caption or ""
                item.status = "queued"
                created_posts += 1
                post_ids.append(int(post.id))

            if first_post_id:
                item.post_id = first_post_id

        db.commit()
        return {"materialized": created_posts, "post_ids": post_ids}
    finally:
        db.close()


def run_due_content_plan(limit: int = 50, user_id: Optional[int] = None, project_id: Optional[int] = None) -> Dict[str, int]:
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due = (
            db.query(ContentPlan)
            .filter(ContentPlan.status.in_(["planned", "scheduled"]), ContentPlan.scheduled_at <= now)
            .order_by(ContentPlan.scheduled_at.asc())
            .limit(limit)
            .all()
        )
        if user_id:
            due = [x for x in due if x.user_id == user_id]
        if project_id:
            due = [x for x in due if x.project_id == project_id]

        published = 0
        for item in due:
            if item.post_id:
                post = db.query(Post).filter_by(id=item.post_id).first()
                if post:
                    post.status = "done"
                    post.published_at = now
                    post.remote_id = post.remote_id or f"auto_{post.id}_{int(now.timestamp())}"
            item.status = "published"
            published += 1

        db.commit()
        return {"published": published}
    finally:
        db.close()


def generate_blog_article(topic: str, language: str = "ru") -> Dict[str, str]:
    target_words = 1500
    base_prompt = (
        f"Напиши SEO-статью на тему: '{topic}'. "
        "Язык: русский. Объем: 1500-1800 слов. Формат: Markdown с H2/H3, без таблиц и без code blocks. "
        "Тон: практичный экспертный, без воды, без повторения абзацев и без штампов. "
        "Обязательно раскрой в тексте: "
        "1) AutoSocial GPT как AI-ассистент для соцсетей; "
        "2) генерация постов, хештегов и CTA; "
        "3) планировщик и автопостинг по расписанию в Facebook + Instagram; "
        "4) аналитика: показы, вовлеченность, рост аудитории; "
        "5) преимущества для малого бизнеса и маркетологов; "
        "6) Free-план без привязки карты и старт по email. "
        "Добавь конкретику, шаги внедрения и финальный CTA: 'Начать бесплатно'. "
        "Нельзя использовать маркеры вида 'Продолжение', 'Часть 1/2', 'Section 1/2'."
    )
    result = generate_post_with_usage(
        topic=base_prompt,
        category="blog",
        tone="expert",
        language=language,
        long_post_mode=True,
        max_output_tokens=2400,
    )

    content = f"# {topic}\n\n{(result.text or '').strip()}"
    for idx in range(1, 5):
        if len(content.split()) >= target_words:
            break
        continuation_prompt = (
            f"Продолжи и углуби SEO-статью '{topic}'. Уже написано около {len(content.split())} слов. "
            "Добавь новые разделы без повторов: ошибки внедрения, FAQ, мини-кейс, план на 30 дней. "
            "Сохраняй стиль и структуру Markdown. "
            "Не добавляй служебные заголовки: 'Продолжение #1', 'Продолжение #2', 'Часть 2' и подобные."
        )
        more = generate_post_with_usage(
            topic=continuation_prompt,
            category="blog",
            tone="expert",
            language=language,
            long_post_mode=True,
            max_output_tokens=1100,
        )
        extra = (more.text or "").strip()
        if extra:
            content += "\n\n" + extra

    if len(content.split()) < target_words:
        content += (
            "\n\n## Практический чеклист запуска\n"
            "1. Определите цель на 30 дней: охват, вовлеченность или заявки.\n"
            "2. Подготовьте темы под каждый этап воронки и соберите контент-план.\n"
            "3. Сгенерируйте тексты с CTA и хештегами через AutoSocial GPT.\n"
            "4. Настройте автопостинг в Facebook и Instagram по календарю.\n"
            "5. Каждую неделю анализируйте метрики и усиливайте лучшие форматы.\n"
            "\n## Финальный шаг\n"
            "Если хотите внедрить SMM-автопилот без лишней рутины, начните с Free-плана AutoSocial GPT и зарегистрируйтесь по email."
        )
    day = 1
    while len(content.split()) < target_words:
        content += (
            f"\n\n## План действий: день {day}\n"
            f"День {day} начните с формулировки гипотезы: какой тип контента лучше сработает для вашей аудитории сегодня. "
            "Соберите один образовательный пост, один кейс и один продающий блок с четким CTA, затем запланируйте публикации в Facebook и Instagram. "
            "После выхода контента проверьте показы, вовлеченность, сохранения, клики и комментарии, чтобы понять, что действительно влияет на рост. "
            "На основе данных обновите контент-план, оставьте сильные форматы и уберите слабые. "
            "Такой цикл помогает внедрить системный SMM-процесс без хаоса и ручной рутины, а AutoSocial GPT ускоряет каждый этап от идеи до аналитики."
        )
        day += 1

    # Remove leftover continuation markers if model still emits them.
    cleaned_lines: List[str] = []
    for line in content.splitlines():
        t = line.strip().lower()
        if re.match(r"^#{0,6}\s*продолжение\s*#?\d*\s*$", t):
            continue
        if re.match(r"^#{0,6}\s*част[ьи]\s*\d+\s*$", t):
            continue
        if re.match(r"^#{0,6}\s*continuation\s*#?\d*\s*$", t):
            continue
        cleaned_lines.append(line)
    content = "\n".join(cleaned_lines).strip()

    return {
        "title": topic,
        "content": content,
        "meta_title": topic,
        "meta_description": f"SEO-статья по теме '{topic}': AI-контент, автопостинг Facebook+Instagram и аналитика в AutoSocial GPT.",
        "keywords": "autosocial gpt, ai smm, автопостинг facebook instagram, контент стратегия, smm автоматизация",
    }


def create_daily_blog_post(topic: Optional[str] = None, language: str = "ru", author_user_id: Optional[int] = None) -> BlogPost:
    if not topic:
        day_index = datetime.utcnow().timetuple().tm_yday % len(BLOG_TOPICS)
        topic = BLOG_TOPICS[day_index]

    payload = generate_blog_article(topic=topic, language=language)

    db = SessionLocal()
    try:
        slug_base = _slugify(payload["title"])
        slug = slug_base
        i = 1
        while db.query(BlogPost).filter_by(slug=slug).first():
            i += 1
            slug = f"{slug_base}-{i}"

        row = BlogPost(
            user_id=author_user_id,
            title=payload["title"],
            slug=slug,
            content=payload["content"],
            meta_title=payload["meta_title"],
            meta_description=payload["meta_description"],
            keywords=payload["keywords"],
            status="published",
            published_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def list_blog_posts(limit: int = 50) -> List[BlogPost]:
    db = SessionLocal()
    try:
        return db.query(BlogPost).order_by(BlogPost.published_at.desc()).limit(limit).all()
    finally:
        db.close()
