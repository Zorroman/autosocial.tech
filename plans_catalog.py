from __future__ import annotations

from dataclasses import dataclass
from typing import Any


UNLIMITED = 999999


@dataclass(frozen=True)
class PlanSpec:
    code: str
    title: str
    price_eur_month: int
    monthly_credits: int
    max_projects: int
    max_posts_month: int
    max_daily_posts: int
    max_videos_period: int
    can_schedule: bool
    can_autopublish: bool
    templates_enabled: bool
    niche_templates: str
    analytics_level: str
    team_seats: int
    accounts_connected: int
    youtube_connect: bool
    public: bool
    recommended: bool
    payment_available: bool
    trial_days: int
    target: str
    team_features_label: str
    stripe_lookup_key: str


PLAN_SPECS: dict[str, PlanSpec] = {
    "admin": PlanSpec(
        code="admin",
        title="Admin Unlimited",
        price_eur_month=0,
        monthly_credits=UNLIMITED,
        max_projects=UNLIMITED,
        max_posts_month=UNLIMITED,
        max_daily_posts=UNLIMITED,
        max_videos_period=UNLIMITED,
        can_schedule=True,
        can_autopublish=True,
        templates_enabled=True,
        niche_templates="full",
        analytics_level="advanced",
        team_seats=UNLIMITED,
        accounts_connected=UNLIMITED,
        youtube_connect=True,
        public=False,
        recommended=False,
        payment_available=False,
        trial_days=0,
        target="Внутренний безлимитный план для администратора",
        team_features_label="Полный доступ",
        stripe_lookup_key="",
    ),
    "free": PlanSpec(
        code="free",
        title="Free Trial 7 days",
        price_eur_month=0,
        monthly_credits=120000,
        max_projects=1,
        max_posts_month=30,
        max_daily_posts=5,
        max_videos_period=0,
        can_schedule=False,
        can_autopublish=False,
        templates_enabled=False,
        niche_templates="limited",
        analytics_level="none",
        team_seats=1,
        accounts_connected=1,
        youtube_connect=True,
        public=True,
        recommended=False,
        payment_available=False,
        trial_days=7,
        target="Для знакомства с продуктом без расходов",
        team_features_label="Нет",
        stripe_lookup_key="autosocial_free_trial_v2",
    ),
    "starter": PlanSpec(
        code="starter",
        title="Starter",
        price_eur_month=29,
        monthly_credits=500000,
        max_projects=2,
        max_posts_month=150,
        max_daily_posts=20,
        max_videos_period=10,
        can_schedule=True,
        can_autopublish=False,
        templates_enabled=True,
        niche_templates="standard",
        analytics_level="basic",
        team_seats=1,
        accounts_connected=2,
        youtube_connect=True,
        public=True,
        recommended=False,
        payment_available=False,
        trial_days=0,
        target="Для малого бизнеса и соло-предпринимателя",
        team_features_label="Нет",
        stripe_lookup_key="autosocial_starter_eur_month_v2",
    ),
    "growth": PlanSpec(
        code="growth",
        title="Growth",
        price_eur_month=79,
        monthly_credits=1800000,
        max_projects=5,
        max_posts_month=600,
        max_daily_posts=60,
        max_videos_period=40,
        can_schedule=True,
        can_autopublish=True,
        templates_enabled=True,
        niche_templates="full",
        analytics_level="advanced",
        team_seats=3,
        accounts_connected=5,
        youtube_connect=True,
        public=True,
        recommended=True,
        payment_available=False,
        trial_days=0,
        target="Для активного бизнеса и маркетолога",
        team_features_label="Базовая командная работа",
        stripe_lookup_key="autosocial_growth_eur_month_v2",
    ),
    "agency": PlanSpec(
        code="agency",
        title="Agency",
        price_eur_month=199,
        monthly_credits=6000000,
        max_projects=UNLIMITED,
        max_posts_month=2000,
        max_daily_posts=200,
        max_videos_period=150,
        can_schedule=True,
        can_autopublish=True,
        templates_enabled=True,
        niche_templates="full",
        analytics_level="advanced",
        team_seats=10,
        accounts_connected=UNLIMITED,
        youtube_connect=True,
        public=True,
        recommended=False,
        payment_available=False,
        trial_days=0,
        target="Для агентств и multi-client работы",
        team_features_label="Командные функции по запросу",
        stripe_lookup_key="autosocial_agency_eur_month_v3",
    ),
}


PUBLIC_PLAN_ORDER = ["free", "starter", "growth", "agency"]


PLAN_ALIASES: dict[str, str] = {
    "admin": "admin",
    "trial": "free",
    "free_trial": "free",
    "free": "free",
    "starter": "starter",
    "growth": "growth",
    "agency": "agency",
    # Legacy names normalize into the new public matrix.
    "light": "starter",
    "light_legacy": "starter",
    "pro": "growth",
    "growth_legacy": "growth",
    "agency_legacy": "agency",
}


def normalize_plan_code(plan: str | None) -> str:
    key = str(plan or "").strip().lower()
    normalized = PLAN_ALIASES.get(key, "free")
    return normalized if normalized in PLAN_SPECS else "free"


def get_plan_spec(plan: str | None) -> PlanSpec:
    return PLAN_SPECS[normalize_plan_code(plan)]


def is_public_plan(plan: str | None) -> bool:
    return get_plan_spec(plan).public


def all_public_plan_specs() -> list[PlanSpec]:
    return [PLAN_SPECS[k] for k in PUBLIC_PLAN_ORDER if k in PLAN_SPECS]


def to_plan_payload(spec: PlanSpec) -> dict[str, Any]:
    return {
        "name": spec.code,
        "title": spec.title,
        "price_eur_month": spec.price_eur_month,
        "monthly_credits": spec.monthly_credits,
        "max_projects": spec.max_projects,
        "max_posts_month": spec.max_posts_month,
        "max_daily_posts": spec.max_daily_posts,
        "max_videos_period": spec.max_videos_period,
        "can_schedule": spec.can_schedule,
        "can_autopublish": spec.can_autopublish,
        "templates_enabled": spec.templates_enabled,
        "niche_templates": spec.niche_templates,
        "analytics_level": spec.analytics_level,
        "team_seats": spec.team_seats,
        "accounts_connected": spec.accounts_connected,
        "youtube_connect": spec.youtube_connect,
        "public": spec.public,
        "recommended": spec.recommended,
        "payment_available": spec.payment_available,
        "trial_days": spec.trial_days,
        "target": spec.target,
        "team_features_label": spec.team_features_label,
    }


def next_public_plan(plan: str | None) -> str:
    normalized = normalize_plan_code(plan)
    if normalized not in PUBLIC_PLAN_ORDER:
        return "starter"
    idx = PUBLIC_PLAN_ORDER.index(normalized)
    return PUBLIC_PLAN_ORDER[min(idx + 1, len(PUBLIC_PLAN_ORDER) - 1)]

