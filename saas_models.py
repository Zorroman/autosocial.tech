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
