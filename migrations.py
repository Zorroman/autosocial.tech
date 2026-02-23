from sqlalchemy import inspect, text

from database import engine
from saas_models import SaaSBase


APP_USER_ADDITIONAL_COLUMNS = {
    "plan_id": "INTEGER",
    "credits_left": "INTEGER DEFAULT 0 NOT NULL",
    "posts_used_month": "INTEGER DEFAULT 0 NOT NULL",
    "billing_status": "VARCHAR(30) DEFAULT 'inactive' NOT NULL",
    "stripe_customer_id": "VARCHAR(120)",
    "stripe_subscription_id": "VARCHAR(120)",
    "current_period_end": "DATETIME",
    "last_login": "DATETIME",
    "google_sub": "VARCHAR(255)",
    "facebook_user_id": "VARCHAR(255)",
}

POSTS_ADDITIONAL_COLUMNS = {
    "topic": "VARCHAR(500) DEFAULT '' NOT NULL",
    "category": "VARCHAR(120)",
    "language": "VARCHAR(30) DEFAULT 'ru' NOT NULL",
    "tone": "VARCHAR(50) DEFAULT 'friendly' NOT NULL",
    "retry_count": "INTEGER DEFAULT 0 NOT NULL",
}

PLANS_ADDITIONAL_COLUMNS = {
    "templates_enabled": "BOOLEAN DEFAULT 0 NOT NULL",
}

CONTENT_PLAN_ADDITIONAL_COLUMNS = {
    "business_type": "VARCHAR(200)",
    "goal": "VARCHAR(300)",
    "language": "VARCHAR(30) DEFAULT 'ru' NOT NULL",
}

SOCIAL_ACCOUNTS_ADDITIONAL_COLUMNS = {
    "page_picture_url": "VARCHAR(500)",
    "ig_username": "VARCHAR(120)",
    "status_reason_code": "VARCHAR(120)",
    "last_success_at": "DATETIME",
    "updated_at": "DATETIME",
}

CAMPAIGNS_ADDITIONAL_COLUMNS = {
    "project_id": "INTEGER",
    "offer": "VARCHAR(500)",
    "objective": "VARCHAR(500)",
    "caption_master": "TEXT",
    "cta": "VARCHAR(300)",
    "hashtags_master": "TEXT",
    "language": "VARCHAR(30) DEFAULT 'ru' NOT NULL",
    "status": "VARCHAR(20) DEFAULT 'draft' NOT NULL",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

CAMPAIGN_ASSETS_ADDITIONAL_COLUMNS = {
    "mime_type": "VARCHAR(120)",
    "width": "INTEGER",
    "height": "INTEGER",
    "duration_sec": "INTEGER",
    "size_bytes": "BIGINT",
    "created_at": "DATETIME",
}

CAMPAIGN_DELIVERIES_ADDITIONAL_COLUMNS = {
    "account_ref": "VARCHAR(160)",
    "caption_rendered": "TEXT",
    "hashtags_rendered": "TEXT",
    "scheduled_at": "DATETIME",
    "status": "VARCHAR(20) DEFAULT 'queued' NOT NULL",
    "remote_id": "VARCHAR(255)",
    "error_message": "TEXT",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

GENERATION_JOBS_ADDITIONAL_COLUMNS = {
    "job_type": "VARCHAR(30)",
    "status": "VARCHAR(20) DEFAULT 'queued' NOT NULL",
    "progress": "INTEGER DEFAULT 0 NOT NULL",
    "result_json": "TEXT",
    "error_message": "TEXT",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}


def add_missing_columns(table_name: str, columns: dict) -> None:
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns(table_name)}
    with engine.begin() as conn:
        for column_name, ddl_type in columns.items():
            if column_name in existing:
                continue
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl_type}"))


def run_migrations() -> None:
    SaaSBase.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "app_users" in tables:
        add_missing_columns("app_users", APP_USER_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_app_users_google_sub ON app_users (google_sub)"))
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_app_users_facebook_user_id ON app_users (facebook_user_id)")
            )

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "posts" in tables:
        add_missing_columns("posts", POSTS_ADDITIONAL_COLUMNS)
    if "plans" in tables:
        add_missing_columns("plans", PLANS_ADDITIONAL_COLUMNS)
    if "content_plan" in tables:
        add_missing_columns("content_plan", CONTENT_PLAN_ADDITIONAL_COLUMNS)
    if "social_accounts" in tables:
        add_missing_columns("social_accounts", SOCIAL_ACCOUNTS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE social_accounts SET status='not_connected' WHERE status IS NULL OR TRIM(status)=''"))
            conn.execute(
                text(
                    "UPDATE social_accounts SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"
                )
            )
    if "campaigns" in tables:
        add_missing_columns("campaigns", CAMPAIGNS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE campaigns SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
            )
            conn.execute(
                text("UPDATE campaigns SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)")
            )
    if "campaign_assets" in tables:
        add_missing_columns("campaign_assets", CAMPAIGN_ASSETS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE campaign_assets SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
            )
    if "campaign_deliveries" in tables:
        add_missing_columns("campaign_deliveries", CAMPAIGN_DELIVERIES_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE campaign_deliveries SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
            )
            conn.execute(
                text("UPDATE campaign_deliveries SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)")
            )
    if "generation_jobs" in tables:
        add_missing_columns("generation_jobs", GENERATION_JOBS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE generation_jobs SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
            )
            conn.execute(
                text("UPDATE generation_jobs SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)")
            )


if __name__ == "__main__":
    run_migrations()
    print("Migrations applied")
