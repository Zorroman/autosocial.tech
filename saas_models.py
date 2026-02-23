from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
