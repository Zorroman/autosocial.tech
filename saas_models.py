from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base

SaaSBase = declarative_base()


class Plan(SaaSBase):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    name = Column(String(40), unique=True, nullable=False)
    price_eur_month = Column(Float, nullable=False, default=0)
    monthly_credits = Column(Integer, nullable=False, default=0)
    max_projects = Column(Integer, nullable=False, default=1)
    max_posts_month = Column(Integer, nullable=False, default=10)
    max_daily_posts = Column(Integer, nullable=False, default=5)
    can_schedule = Column(Boolean, nullable=False, default=False)
    can_autopublish = Column(Boolean, nullable=False, default=False)
    templates_enabled = Column(Boolean, nullable=False, default=False)
    team_seats = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AppUser(SaaSBase):
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    google_sub = Column(String(255), nullable=True, unique=True, index=True)
    facebook_user_id = Column(String(255), nullable=True, unique=True, index=True)
    role = Column(String(20), nullable=False, default="user")
    plan = Column(String(20), nullable=False, default="free")
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=True, index=True)
    credits_left = Column(Integer, nullable=False, default=0)
    posts_used_month = Column(Integer, nullable=False, default=0)
    billing_status = Column(String(30), nullable=False, default="inactive")
    stripe_customer_id = Column(String(120), nullable=True)
    stripe_subscription_id = Column(String(120), nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    onboarding_completed_at = Column(DateTime, nullable=True)
    onboarding_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)


class Subscription(SaaSBase):
    __tablename__ = "subscriptions"

    user_id = Column(Integer, ForeignKey("app_users.id"), primary_key=True)
    plan = Column(String(20), nullable=False, default="trial")  # trial | starter | growth | agency
    status = Column(String(20), nullable=False, default="trialing")  # trialing | active | past_due | canceled
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String(120), nullable=True)
    stripe_subscription_id = Column(String(120), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class UsageCounter(SaaSBase):
    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint("user_id", "period_start", "period_end", name="uq_usage_counter_user_period"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)
    posts_generated = Column(Integer, nullable=False, default=0)
    posts_published = Column(Integer, nullable=False, default=0)
    videos_generated = Column(Integer, nullable=False, default=0)
    videos_published = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class UsageEvent(SaaSBase):
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    type = Column(String(60), nullable=False, index=True)
    delta = Column(Integer, nullable=False, default=1)
    meta_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ApiToken(SaaSBase):
    __tablename__ = "api_tokens"

    token = Column(String(128), primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuthEmailChallenge(SaaSBase):
    __tablename__ = "auth_email_challenges"

    id = Column(Integer, primary_key=True)
    challenge_token = Column(String(120), unique=True, nullable=False, index=True)
    flow = Column(String(20), nullable=False)  # login | register
    email = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=True, index=True)
    pending_password_hash = Column(String(255), nullable=True)
    code_hash = Column(String(128), nullable=False)
    attempts_left = Column(Integer, nullable=False, default=5)
    requested_ip = Column(String(80), nullable=True, index=True)
    user_agent = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    verified_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Project(SaaSBase):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class IntegrationConnection(SaaSBase):
    __tablename__ = "social_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    provider = Column(String(30), nullable=False, default="meta")
    page_id = Column(String(120), nullable=True)
    page_name = Column(String(255), nullable=True)
    page_picture_url = Column(String(500), nullable=True)
    ig_user_id = Column(String(120), nullable=True)
    ig_username = Column(String(120), nullable=True)
    token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    # Canonical integration state:
    # not_connected | connected_need_page | connected_ready | token_expired
    # permissions_missing | disconnected | error
    status = Column(String(40), nullable=False, default="not_connected")
    status_reason_code = Column(String(120), nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# Backward-compatible alias for existing imports.
SocialAccount = IntegrationConnection


class ConnectedAccount(SaaSBase):
    __tablename__ = "connected_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", "external_id", name="uq_connected_account_user_platform_external"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    platform = Column(String(20), nullable=False, index=True)  # meta | youtube
    external_id = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ContentItem(SaaSBase):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", "external_id", name="uq_content_item_user_platform_external"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    platform = Column(String(20), nullable=False, index=True)  # meta | youtube
    external_id = Column(String(255), nullable=False)
    account_id = Column(Integer, ForeignKey("connected_accounts.id"), nullable=False, index=True)
    content_type = Column(String(40), nullable=False, default="post")
    title = Column(String(500), nullable=True)
    message = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ContentMetricDaily(SaaSBase):
    __tablename__ = "content_metrics_daily"
    __table_args__ = (
        UniqueConstraint("content_item_id", "day", name="uq_content_metrics_daily_item_day"),
    )

    id = Column(Integer, primary_key=True)
    content_item_id = Column(Integer, ForeignKey("content_items.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    impressions = Column(Integer, nullable=False, default=0)
    reach = Column(Integer, nullable=False, default=0)
    views = Column(Integer, nullable=False, default=0)
    clicks = Column(Integer, nullable=False, default=0)
    likes = Column(Integer, nullable=False, default=0)
    comments = Column(Integer, nullable=False, default=0)
    shares = Column(Integer, nullable=False, default=0)
    watch_time_seconds = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class AiScoreDaily(SaaSBase):
    __tablename__ = "ai_score_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_ai_score_daily_user_day"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    ai_score = Column(Float, nullable=False, default=0)
    performance = Column(Float, nullable=False, default=0)
    consistency = Column(Float, nullable=False, default=0)
    growth = Column(Float, nullable=False, default=0)
    optimization = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AiScoreDailyV2(SaaSBase):
    __tablename__ = "ai_scores_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_ai_scores_daily_user_day"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    score_total = Column(Float, nullable=False, default=0)
    score_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Forecast(SaaSBase):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    horizon_days = Column(Integer, nullable=False, default=7, index=True)
    forecast_json = Column(Text, nullable=False, default="{}")
    based_on_from = Column(Date, nullable=True, index=True)
    based_on_to = Column(Date, nullable=True, index=True)


class TopicSuggestion(SaaSBase):
    __tablename__ = "topics_suggestions"
    __table_args__ = (UniqueConstraint("user_id", "project_id", "category", "topic", name="uq_topic_suggestion"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    category = Column(String(120), nullable=True)
    topic = Column(String(500), nullable=False)
    usage_count = Column(Integer, nullable=False, default=1)
    last_used_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Post(SaaSBase):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    platform = Column(String(50), nullable=False, default="instagram")
    prompt_text = Column(Text, nullable=True)
    generated_text = Column(Text, nullable=True)
    topic = Column(String(500), nullable=False)
    category = Column(String(120), nullable=True)
    language = Column(String(30), nullable=False, default="ru")
    tone = Column(String(50), nullable=False, default="friendly")
    media_url = Column(Text, nullable=True)
    tokens_input = Column(Integer, nullable=False, default=0)
    tokens_output = Column(Integer, nullable=False, default=0)
    tokens_total = Column(Integer, nullable=False, default=0)
    credits_charged = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="queued")
    schedule_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    remote_id = Column(String(120), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Campaign(SaaSBase):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    mode = Column(String(20), nullable=False, default="image")  # image | video | both
    topic = Column(String(500), nullable=False)
    offer = Column(String(500), nullable=True)
    objective = Column(String(500), nullable=True)
    caption_master = Column(Text, nullable=True)
    cta = Column(String(300), nullable=True)
    hashtags_master = Column(Text, nullable=True)
    language = Column(String(30), nullable=False, default="ru")
    status = Column(String(20), nullable=False, default="draft")  # draft | ready | publishing | published | failed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class CampaignAsset(SaaSBase):
    __tablename__ = "campaign_assets"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    type = Column(String(20), nullable=False)  # image | video | thumbnail
    storage_url = Column(Text, nullable=False)
    mime_type = Column(String(120), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration_sec = Column(Integer, nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class CampaignDelivery(SaaSBase):
    __tablename__ = "campaign_deliveries"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    platform = Column(String(30), nullable=False)  # facebook | instagram | youtube
    kind = Column(String(30), nullable=False)  # image_post | reel | video | shorts
    account_ref = Column(String(160), nullable=True)
    caption_rendered = Column(Text, nullable=True)
    hashtags_rendered = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=True, index=True)
    status = Column(String(20), nullable=False, default="queued")  # queued | uploading | processing | published | failed
    remote_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ContentBrief(SaaSBase):
    __tablename__ = "content_briefs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    topic = Column(Text, nullable=False)
    offer = Column(Text, nullable=True)
    language = Column(String(20), nullable=False, default="ru")
    tone = Column(String(40), nullable=False, default="neutral")
    goal = Column(String(40), nullable=False, default="engagement")
    platforms_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ContentStrategy(SaaSBase):
    __tablename__ = "content_strategies"

    id = Column(Integer, primary_key=True)
    brief_id = Column(Integer, ForeignKey("content_briefs.id"), nullable=False, index=True)
    strategy_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ContentDraft(SaaSBase):
    __tablename__ = "content_drafts"

    id = Column(Integer, primary_key=True)
    brief_id = Column(Integer, ForeignKey("content_briefs.id"), nullable=False, index=True)
    platform = Column(String(30), nullable=False, index=True)  # facebook | instagram | youtube
    variant_index = Column(Integer, nullable=False, default=1)
    post_text = Column(Text, nullable=False)
    title = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)
    hashtags_json = Column(Text, nullable=False, default="[]")
    cta = Column(Text, nullable=True)
    asset_ideas_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class UserTemplate(SaaSBase):
    __tablename__ = "user_templates"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    preset_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Niche(SaaSBase):
    __tablename__ = "niches"

    id = Column(Integer, primary_key=True)
    slug = Column(String(80), unique=True, nullable=False, index=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=False, default="")
    icon = Column(String(80), nullable=False, default="briefcase")
    sort_order = Column(Integer, nullable=False, default=100)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Template(SaaSBase):
    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint("niche_id", "slug", name="uq_templates_niche_slug"),
    )

    id = Column(Integer, primary_key=True)
    niche_id = Column(Integer, ForeignKey("niches.id"), nullable=False, index=True)
    slug = Column(String(120), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    type = Column(String(20), nullable=False, default="post")  # post | video
    platform = Column(String(20), nullable=False, default="all")
    goal = Column(String(20), nullable=False, default="leads")  # leads | awareness
    tone = Column(String(40), nullable=False, default="local-friendly")  # local-friendly | expert
    hook_line = Column(String(300), nullable=False, default="")
    cta = Column(String(300), nullable=False, default="")
    prompt_system = Column(Text, nullable=False, default="")
    prompt_user = Column(Text, nullable=False, default="")
    variables_schema_json = Column(Text, nullable=False, default="{}")
    preview_text = Column(Text, nullable=False, default="")
    sort_order = Column(Integer, nullable=False, default=100)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class UserStylePref(SaaSBase):
    __tablename__ = "user_style_prefs"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_style_prefs_user"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    default_style_pack = Column(String(80), nullable=False, default="default_pro")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class GenerationJob(SaaSBase):
    __tablename__ = "generation_jobs"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    job_type = Column(String(30), nullable=False)  # generate_image | generate_video
    status = Column(String(20), nullable=False, default="queued")  # queued | running | done | failed
    progress = Column(Integer, nullable=False, default=0)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ContentPlan(SaaSBase):
    __tablename__ = "content_plan"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    business_type = Column(String(200), nullable=True)
    goal = Column(String(300), nullable=True)
    language = Column(String(30), nullable=False, default="ru")
    topic = Column(String(500), nullable=False)
    caption = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    cta = Column(String(300), nullable=True)
    scheduled_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(30), nullable=False, default="planned")
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BlogPost(SaaSBase):
    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=True, index=True)
    title = Column(String(300), nullable=False)
    slug = Column(String(320), unique=True, nullable=False, index=True)
    content = Column(Text, nullable=False)
    meta_title = Column(String(300), nullable=False)
    meta_description = Column(String(400), nullable=False)
    keywords = Column(String(400), nullable=False)
    status = Column(String(30), nullable=False, default="published")
    published_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PlatformRule(SaaSBase):
    __tablename__ = "platform_rules"

    id = Column(Integer, primary_key=True)
    platform = Column(String(50), unique=True, nullable=False)
    max_chars = Column(Integer, nullable=False)
    recommended_chars_min = Column(Integer, nullable=False)
    recommended_chars_max = Column(Integer, nullable=False)
    max_hashtags = Column(Integer, nullable=False, default=5)
    max_output_tokens_default = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NicheHook(SaaSBase):
    __tablename__ = "niche_hooks"

    id = Column(Integer, primary_key=True)
    niche = Column(String(80), nullable=False, index=True)
    hook = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CreditLedger(SaaSBase):
    __tablename__ = "credit_ledger"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    type = Column(String(40), nullable=False)
    delta_credits = Column(Integer, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    stripe_payment_intent_id = Column(String(120), nullable=True)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PaymentEvent(SaaSBase):
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True)
    stripe_event_id = Column(String(120), unique=True, nullable=False)
    event_type = Column(String(120), nullable=False)
    customer_id = Column(String(120), nullable=True)
    subscription_id = Column(String(120), nullable=True)
    amount_eur = Column(Float, nullable=True)
    status = Column(String(40), nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(SaaSBase):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=True, index=True)
    action = Column(String(120), nullable=False)
    ip = Column(String(80), nullable=True)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SystemLog(SaaSBase):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("app_users.id"), nullable=True, index=True)
    level = Column(String(20), nullable=False, default="info")
    message = Column(String(500), nullable=False)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Channel(SaaSBase):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    slug = Column(String(160), unique=True, nullable=False)
    niche = Column(String(120), nullable=True)
    description = Column(Text, nullable=True)
    language = Column(String(16), nullable=False, default="ru")
    target_audience = Column(Text, nullable=True)
    content_style = Column(Text, nullable=True)
    narration_style = Column(Text, nullable=True)
    default_voice = Column(String(80), nullable=True)
    visual_style = Column(Text, nullable=True)
    categories_json = Column(Text, nullable=True)
    allowed_topics = Column(Text, nullable=True)
    prohibited_topics = Column(Text, nullable=True)
    default_video_duration_seconds = Column(Integer, nullable=False, default=45)
    default_video_format = Column(String(40), nullable=False, default="shorts")
    publication_frequency = Column(String(80), nullable=True)
    timezone = Column(String(64), nullable=False, default="Europe/Berlin")
    status = Column(String(20), nullable=False, default="testing", index=True)
    niche_id = Column(Integer, ForeignKey("content_niches.id"), nullable=True, index=True)
    target_country = Column(String(80), nullable=True)
    tone_of_voice = Column(String(200), nullable=True)
    daily_video_limit = Column(Integer, nullable=False, default=0)
    default_visibility = Column(String(20), nullable=False, default="private")
    automatic_generation_enabled = Column(Boolean, nullable=False, default=False)
    # Fail-safe: new channels never auto-publish. Enabling is an explicit user
    # action; Director approve / render / OAuth connect never flip this flag.
    automatic_publishing_enabled = Column(Boolean, nullable=False, default=False)
    # Deprecated in favour of publishing_mode (kept in sync as a legacy synonym).
    autopilot_enabled = Column(Boolean, nullable=False, default=False)
    # Content Factory publishing mode — source of truth for autonomy.
    # 'manual'    = review metadata before YouTube (default, safe)
    # 'automatic' = full autopilot: publish without individual confirmation.
    publishing_mode = Column(String(20), nullable=False, default="manual")
    oauth_last_error = Column(String(300), nullable=True)
    last_generated_at = Column(DateTime, nullable=True)
    youtube_channel_id = Column(String(120), nullable=True)
    youtube_channel_title = Column(String(255), nullable=True)
    youtube_connection_status = Column(String(30), nullable=True)
    youtube_connected_at = Column(DateTime, nullable=True)
    youtube_social_account_id = Column(Integer, ForeignKey("social_accounts.id"), nullable=True)
    youtube_last_verified_at = Column(DateTime, nullable=True)
    connected_account_id = Column(Integer, ForeignKey("connected_accounts.id"), nullable=True)
    generation_settings_json = Column(Text, nullable=True)
    video_template_json = Column(Text, nullable=True)
    subtitle_template_json = Column(Text, nullable=True)
    music_settings_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ChannelIdea(SaaSBase):
    __tablename__ = "channel_ideas"

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    topic = Column(String(300), nullable=True)
    category = Column(String(120), nullable=True)
    hook_concept = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    source = Column(String(20), nullable=False, default="manual")
    status = Column(String(20), nullable=False, default="new", index=True)
    content_pillar_id = Column(Integer, ForeignKey("content_pillars.id"), nullable=True, index=True)
    normalized_title = Column(String(300), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class VideoProject(SaaSBase):
    __tablename__ = "video_projects"

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    idea_id = Column(Integer, ForeignKey("channel_ideas.id"), nullable=True)
    content_pillar_id = Column(Integer, ForeignKey("content_pillars.id"), nullable=True, index=True)
    content_strategy_id = Column(Integer, nullable=True, index=True)
    generation_profile_json = Column(Text, nullable=True)
    title = Column(String(300), nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    script_text = Column(Text, nullable=True)
    voice_mode = Column(String(20), nullable=False, default="tts")
    voiceover_path = Column(String(500), nullable=True)
    subtitle_mode = Column(String(20), nullable=False, default="auto")
    aspect_ratio = Column(String(10), nullable=False, default="9:16")
    duration_target_seconds = Column(Integer, nullable=False, default=45)
    output_path = Column(String(500), nullable=True)
    error = Column(Text, nullable=True)
    # Content Factory pipeline state (orchestrator).
    # stage:  idea|script|scenes|media|voice|render|publish
    # state:  waiting|running|needs_review|error|done
    pipeline_stage = Column(String(20), nullable=True)
    pipeline_state = Column(String(20), nullable=True)
    pipeline_error = Column(Text, nullable=True)
    # Per-video publishing override: NULL = use channel default, else manual|automatic
    publishing_override = Column(String(20), nullable=True)
    # AI Publisher output: title/description ALTERNATIVES + selection, tags,
    # hashtags, pinned comment, privacy, schedule, thumbnail plan, and a
    # generation_meta block (model/version/inputs) reserved for future learning
    # from YouTube analytics. Stored as JSON.
    youtube_meta_json = Column(Text, nullable=True)
    # Background music bed selected/mixed for this Short (see music_mix.py).
    music_track_id = Column(String(64), nullable=True)
    music_title = Column(String(200), nullable=True)
    music_provider = Column(String(40), nullable=True)
    music_start_seconds = Column(Float, nullable=True)
    music_end_seconds = Column(Float, nullable=True)
    music_gain_db = Column(Float, nullable=True)
    music_status = Column(String(20), nullable=True)  # mixed | no_music | disabled
    music_mix_version = Column(String(10), nullable=True)
    # Final spoken call-to-action (see cta_generator.py / music_mix is separate).
    cta_enabled = Column(Boolean, nullable=True)
    cta_text = Column(Text, nullable=True)
    cta_type = Column(String(30), nullable=True)
    cta_language = Column(String(10), nullable=True)
    cta_source = Column(String(20), nullable=True)  # generated | library | custom | fallback | disabled
    cta_audio_duration_seconds = Column(Float, nullable=True)
    cta_fallback_used = Column(Boolean, nullable=True)
    playlist_status = Column(String(20), nullable=True)  # added | no_playlist | failed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class VideoScene(SaaSBase):
    __tablename__ = "video_scenes"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("video_projects.id"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False, default=0)
    voiceover_text = Column(Text, nullable=True)
    on_screen_text = Column(Text, nullable=True)
    estimated_duration = Column(Float, nullable=False, default=4.0)
    actual_duration = Column(Float, nullable=True)
    visual_type = Column(String(30), nullable=False, default="stock")
    visual_prompt = Column(Text, nullable=True)
    stock_search_query = Column(String(300), nullable=True)
    selected_media_path = Column(String(500), nullable=True)
    media_meta_json = Column(Text, nullable=True)
    transition = Column(String(30), nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    is_cta = Column(Boolean, nullable=False, default=False)  # final subscribe CTA scene
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RenderJob(SaaSBase):
    __tablename__ = "render_jobs"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("video_projects.id"), nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    job_type = Column(String(30), nullable=False, default="render")
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Integer, nullable=False, default=0)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=2)
    error = Column(Text, nullable=True)
    worker = Column(String(80), nullable=True)
    output_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class Publication(SaaSBase):
    __tablename__ = "publications"

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("video_projects.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    tags_json = Column(Text, nullable=True)
    privacy_status = Column(String(20), nullable=False, default="private")
    publish_mode = Column(String(20), nullable=False, default="manual")
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    youtube_video_id = Column(String(40), nullable=True)
    youtube_url = Column(String(255), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    published_at = Column(DateTime, nullable=True)


class VideoAnalyticsSnapshot(SaaSBase):
    __tablename__ = "video_analytics_snapshots"
    __table_args__ = (
        UniqueConstraint("publication_id", "captured_at", "data_source", name="uq_analytics_pub_captured_source"),
    )

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=False, index=True)
    youtube_video_id = Column(String(40), nullable=True)
    data_source = Column(String(20), nullable=False, default="manual")  # manual | youtube_api
    captured_at = Column(DateTime, nullable=False, index=True)
    views = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    comments = Column(Integer, nullable=True)
    shares = Column(Integer, nullable=True)
    subscribers_gained = Column(Integer, nullable=True)
    watch_time_minutes = Column(Float, nullable=True)
    average_view_duration = Column(Float, nullable=True)
    average_view_percentage = Column(Float, nullable=True)
    impressions = Column(Integer, nullable=True)
    click_through_rate = Column(Float, nullable=True)
    estimated_revenue = Column(Float, nullable=True)
    currency = Column(String(3), nullable=True)
    raw_data_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AICostRecord(SaaSBase):
    __tablename__ = "ai_cost_records"

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("video_projects.id"), nullable=True, index=True)
    provider = Column(String(40), nullable=False)
    model = Column(String(80), nullable=True)
    operation_type = Column(String(40), nullable=False, index=True)
    request_id = Column(String(120), nullable=True, index=True)
    input_units = Column(Float, nullable=True)
    output_units = Column(Float, nullable=True)
    audio_characters = Column(Integer, nullable=True)
    image_count = Column(Integer, nullable=True)
    video_seconds = Column(Float, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True)
    currency = Column(String(3), nullable=True)
    status = Column(String(20), nullable=False, default="success")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class FootageAsset(SaaSBase):
    __tablename__ = "footage_assets"
    __table_args__ = (
        UniqueConstraint("provider", "provider_asset_id", name="uq_footage_provider_asset"),
    )

    id = Column(Integer, primary_key=True)
    provider = Column(String(40), nullable=False, index=True)
    provider_asset_id = Column(String(120), nullable=False, index=True)
    original_url = Column(String(600), nullable=True)
    download_url = Column(String(600), nullable=True)
    local_path = Column(String(500), nullable=True)
    file_hash = Column(String(64), nullable=True, index=True)
    duration = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    orientation = Column(String(20), nullable=True)
    search_query = Column(String(300), nullable=True)
    tags_json = Column(Text, nullable=True)
    author = Column(String(200), nullable=True)
    license_note = Column(String(200), nullable=True)
    analysis_json = Column(Text, nullable=True)
    analysis_model = Column(String(80), nullable=True)
    analyzed_at = Column(DateTime, nullable=True)
    reserved_by_job_id = Column(Integer, nullable=True, index=True)
    reserved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True, index=True)
    total_use_count = Column(Integer, nullable=False, default=0)


class FootageUsage(SaaSBase):
    __tablename__ = "footage_usages"

    id = Column(Integer, primary_key=True)
    footage_asset_id = Column(Integer, ForeignKey("footage_assets.id"), nullable=False, index=True)
    video_project_id = Column(Integer, ForeignKey("video_projects.id"), nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    scene_id = Column(Integer, ForeignKey("video_scenes.id"), nullable=True)
    used_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    start_time = Column(Float, nullable=True)
    duration = Column(Float, nullable=True)
    search_query = Column(String(300), nullable=True)
    reuse_reason = Column(String(200), nullable=True)


class ContentNiche(SaaSBase):
    __tablename__ = "content_niches"

    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    slug = Column(String(160), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    default_language = Column(String(16), nullable=False, default="ru")
    default_tone = Column(String(200), nullable=True)
    default_visual_style = Column(Text, nullable=True)
    allowed_topics = Column(Text, nullable=True)
    forbidden_topics = Column(Text, nullable=True)
    forbidden_visuals = Column(Text, nullable=True)
    disclaimer_policy = Column(String(80), nullable=True)
    factuality_policy = Column(String(80), nullable=True)
    sensitive_topics_policy = Column(String(80), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ContentPillar(SaaSBase):
    __tablename__ = "content_pillars"
    __table_args__ = (
        UniqueConstraint("niche_id", "slug", name="uq_pillar_niche_slug"),
    )

    id = Column(Integer, primary_key=True)
    niche_id = Column(Integer, ForeignKey("content_niches.id"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    slug = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    prompt_instructions = Column(Text, nullable=True)
    allowed_topics = Column(Text, nullable=True)
    forbidden_topics = Column(Text, nullable=True)
    visual_keywords = Column(Text, nullable=True)
    forbidden_visual_keywords = Column(Text, nullable=True)
    weight = Column(Integer, nullable=False, default=10)
    daily_video_limit = Column(Integer, nullable=False, default=3)
    active = Column(Boolean, nullable=False, default=True)
    youtube_playlist_id = Column(String(64), nullable=True)  # published videos of this pillar go here
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class VisualValidationRecord(SaaSBase):
    __tablename__ = "visual_validation_records"
    __table_args__ = (
        UniqueConstraint("footage_asset_id", "visual_intent_hash", "model", "prompt_version",
                         name="uq_visual_validation_cache_key"),
    )

    id = Column(Integer, primary_key=True)
    footage_asset_id = Column(Integer, ForeignKey("footage_assets.id"), nullable=False, index=True)
    visual_intent_hash = Column(String(64), nullable=False, index=True)
    provider = Column(String(40), nullable=False)
    model = Column(String(80), nullable=False)
    prompt_version = Column(String(20), nullable=False, default="v1")
    scores_json = Column(Text, nullable=True)
    accepted = Column(Boolean, nullable=False, default=False)
    rejection_reason = Column(String(200), nullable=True)
    cost = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class DirectorStrategy(SaaSBase):
    """One planned video decided by the AI Content Director (ContentStrategy
    entity in the design docs; class renamed to avoid colliding with the
    legacy ContentStrategy model used by the older content pipeline).

    Created BEFORE any script exists: the Director picks pillar -> topic ->
    angle -> hook -> outline and records why. The script generator consumes an
    approved strategy; the Director never writes the script itself.
    """
    __tablename__ = "content_strategies_director"

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    niche_id = Column(Integer, ForeignKey("content_niches.id"), nullable=True, index=True)
    pillar_id = Column(Integer, ForeignKey("content_pillars.id"), nullable=True, index=True)
    language = Column(String(16), nullable=False, default="ru")
    target_audience = Column(Text, nullable=True)

    generation_reason = Column(Text, nullable=True)
    priority = Column(Integer, nullable=False, default=50, index=True)

    estimated_ctr = Column(Float, nullable=True)
    estimated_retention = Column(Float, nullable=True)
    novelty_score = Column(Float, nullable=True)
    competition_score = Column(Float, nullable=True)
    hook_strength = Column(Float, nullable=True)
    visual_potential = Column(Float, nullable=True)
    educational_value = Column(Float, nullable=True)
    entertainment_value = Column(Float, nullable=True)

    selected_topic = Column(String(300), nullable=False)
    normalized_topic = Column(String(300), nullable=True, index=True)
    selected_angle = Column(String(200), nullable=True)
    selected_hook = Column(Text, nullable=True)
    outline_json = Column(Text, nullable=True)
    decision_json = Column(Text, nullable=True)

    # draft | approved | rejected | banned | used
    status = Column(String(20), nullable=False, default="draft", index=True)
    pinned = Column(Boolean, nullable=False, default=False)
    source = Column(String(20), nullable=False, default="heuristic")  # heuristic | ai
    video_project_id = Column(Integer, ForeignKey("video_projects.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ContentPerformance(SaaSBase):
    """Realized performance of a published project, fed back to the Director."""
    __tablename__ = "content_performance"

    id = Column(Integer, primary_key=True)
    video_project_id = Column(Integer, ForeignKey("video_projects.id"), nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True, index=True)
    pillar_id = Column(Integer, ForeignKey("content_pillars.id"), nullable=True, index=True)
    ctr = Column(Float, nullable=True)
    retention = Column(Float, nullable=True)
    watch_time_minutes = Column(Float, nullable=True)
    views = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    comments = Column(Integer, nullable=True)
    shares = Column(Integer, nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
