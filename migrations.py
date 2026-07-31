from sqlalchemy import inspect, text

from database import engine
from app_models import SaaSBase


APP_USER_ADDITIONAL_COLUMNS = {
    "plan_id": "INTEGER",
    "credits_left": "INTEGER DEFAULT 0 NOT NULL",
    "posts_used_month": "INTEGER DEFAULT 0 NOT NULL",
    "billing_status": "VARCHAR(30) DEFAULT 'inactive' NOT NULL",
    "stripe_customer_id": "VARCHAR(120)",
    "stripe_subscription_id": "VARCHAR(120)",
    "current_period_end": "DATETIME",
    "onboarding_completed_at": "DATETIME",
    "onboarding_json": "TEXT",
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
    "refresh_token_encrypted": "TEXT",
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

CONTENT_BRIEFS_ADDITIONAL_COLUMNS = {
    "offer": "TEXT",
    "language": "VARCHAR(20) DEFAULT 'ru' NOT NULL",
    "tone": "VARCHAR(40) DEFAULT 'neutral' NOT NULL",
    "goal": "VARCHAR(40) DEFAULT 'engagement' NOT NULL",
    "platforms_json": "TEXT DEFAULT '[]' NOT NULL",
    "created_at": "DATETIME",
}

CONTENT_STRATEGIES_ADDITIONAL_COLUMNS = {
    "strategy_json": "TEXT",
    "created_at": "DATETIME",
}

CONTENT_DRAFTS_ADDITIONAL_COLUMNS = {
    "variant_index": "INTEGER DEFAULT 1 NOT NULL",
    "title": "VARCHAR(300)",
    "description": "TEXT",
    "hashtags_json": "TEXT DEFAULT '[]' NOT NULL",
    "cta": "TEXT",
    "asset_ideas_json": "TEXT DEFAULT '[]' NOT NULL",
    "created_at": "DATETIME",
}

USER_TEMPLATES_ADDITIONAL_COLUMNS = {
    "name": "VARCHAR(160) NOT NULL DEFAULT 'Шаблон'",
    "preset_json": "TEXT DEFAULT '{}' NOT NULL",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

NICHES_ADDITIONAL_COLUMNS = {
    "slug": "VARCHAR(80)",
    "title": "VARCHAR(160)",
    "description": "TEXT DEFAULT '' NOT NULL",
    "icon": "VARCHAR(80) DEFAULT 'briefcase' NOT NULL",
    "sort_order": "INTEGER DEFAULT 100 NOT NULL",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

TEMPLATES_ADDITIONAL_COLUMNS = {
    "niche_id": "INTEGER",
    "slug": "VARCHAR(120)",
    "title": "VARCHAR(200)",
    "description": "TEXT DEFAULT '' NOT NULL",
    "type": "VARCHAR(20) DEFAULT 'post' NOT NULL",
    "platform": "VARCHAR(20) DEFAULT 'all' NOT NULL",
    "goal": "VARCHAR(20) DEFAULT 'leads' NOT NULL",
    "tone": "VARCHAR(40) DEFAULT 'local-friendly' NOT NULL",
    "hook_line": "VARCHAR(300) DEFAULT '' NOT NULL",
    "cta": "VARCHAR(300) DEFAULT '' NOT NULL",
    "prompt_system": "TEXT DEFAULT '' NOT NULL",
    "prompt_user": "TEXT DEFAULT '' NOT NULL",
    "variables_schema_json": "TEXT DEFAULT '{}' NOT NULL",
    "preview_text": "TEXT DEFAULT '' NOT NULL",
    "sort_order": "INTEGER DEFAULT 100 NOT NULL",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

AI_SCORE_DAILY_ADDITIONAL_COLUMNS = {
    "ai_score": "FLOAT DEFAULT 0 NOT NULL",
    "performance": "FLOAT DEFAULT 0 NOT NULL",
    "consistency": "FLOAT DEFAULT 0 NOT NULL",
    "growth": "FLOAT DEFAULT 0 NOT NULL",
    "optimization": "FLOAT DEFAULT 0 NOT NULL",
    "created_at": "DATETIME",
}

AI_SCORES_DAILY_ADDITIONAL_COLUMNS = {
    "score_total": "FLOAT DEFAULT 0 NOT NULL",
    "score_json": "TEXT DEFAULT '{}' NOT NULL",
    "created_at": "DATETIME",
}

FORECASTS_ADDITIONAL_COLUMNS = {
    "horizon_days": "INTEGER DEFAULT 7 NOT NULL",
    "forecast_json": "TEXT DEFAULT '{}' NOT NULL",
    "based_on_from": "DATE",
    "based_on_to": "DATE",
    "created_at": "DATETIME",
}

USER_STYLE_PREFS_ADDITIONAL_COLUMNS = {
    "default_style_pack": "VARCHAR(80) DEFAULT 'default_pro' NOT NULL",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

SUBSCRIPTIONS_ADDITIONAL_COLUMNS = {
    "plan": "VARCHAR(20) DEFAULT 'trial' NOT NULL",
    "status": "VARCHAR(20) DEFAULT 'trialing' NOT NULL",
    "current_period_start": "DATETIME",
    "current_period_end": "DATETIME",
    "trial_ends_at": "DATETIME",
    "stripe_customer_id": "VARCHAR(120)",
    "stripe_subscription_id": "VARCHAR(120)",
    "updated_at": "DATETIME",
}

USAGE_COUNTERS_ADDITIONAL_COLUMNS = {
    "posts_generated": "INTEGER DEFAULT 0 NOT NULL",
    "posts_published": "INTEGER DEFAULT 0 NOT NULL",
    "videos_generated": "INTEGER DEFAULT 0 NOT NULL",
    "videos_published": "INTEGER DEFAULT 0 NOT NULL",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

USAGE_EVENTS_ADDITIONAL_COLUMNS = {
    "type": "VARCHAR(60)",
    "delta": "INTEGER DEFAULT 1 NOT NULL",
    "meta_json": "TEXT DEFAULT '{}' NOT NULL",
    "created_at": "DATETIME",
}


def add_missing_columns(table_name: str, columns: dict) -> None:
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns(table_name)}
    with engine.begin() as conn:
        for column_name, ddl_type in columns.items():
            if column_name in existing:
                continue
            if engine.dialect.name == "postgresql" and ddl_type == "DATETIME":
                ddl_type = "TIMESTAMP"
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
    if "video_scenes" in tables:
        add_missing_columns("video_scenes", {"media_meta_json": "TEXT"})
    if "channels" in tables:
        add_missing_columns(
            "channels",
            {
                "niche_id": "INTEGER",
                "target_country": "VARCHAR(80)",
                "tone_of_voice": "VARCHAR(200)",
                "daily_video_limit": "INTEGER DEFAULT 0",
                "default_visibility": "VARCHAR(20) DEFAULT 'private'",
                "automatic_generation_enabled": "BOOLEAN DEFAULT 0",
                # Fail-safe default: channels that gain this column start with
                # auto-publishing OFF. Rows that already have the column are
                # never re-touched (add_missing_columns skips existing columns),
                # so existing values are preserved.
                "automatic_publishing_enabled": "BOOLEAN DEFAULT 0",
                # Content Factory full-autopilot toggle. Fail-safe default OFF.
                # NOTE: Postgres rejects "DEFAULT 0" for boolean on a NEW column
                # (the pre-existing flags above only work because they already
                # exist and are skipped). Use FALSE for a fresh boolean column.
                "autopilot_enabled": "BOOLEAN DEFAULT FALSE",
                # Publishing mode (source of truth). String default is fine on PG.
                "publishing_mode": "VARCHAR(20) DEFAULT 'manual'",
                "oauth_last_error": "VARCHAR(300)",
                "last_generated_at": "DATETIME",
            },
        )
    if "video_projects" in tables:
        add_missing_columns(
            "video_projects",
            {
                "content_pillar_id": "INTEGER",
                "generation_profile_json": "TEXT",
                "content_strategy_id": "INTEGER",
                # Content Factory pipeline orchestrator state.
                "pipeline_stage": "VARCHAR(20)",
                "pipeline_state": "VARCHAR(20)",
                "pipeline_error": "TEXT",
                # Stage 3 — per-video publishing override + AI Publisher output.
                "publishing_override": "VARCHAR(20)",
                "youtube_meta_json": "TEXT",
                # Background music bed.
                "music_track_id": "VARCHAR(64)",
                "music_title": "VARCHAR(200)",
                "music_provider": "VARCHAR(40)",
                "music_start_seconds": "DOUBLE PRECISION",
                "music_end_seconds": "DOUBLE PRECISION",
                "music_gain_db": "DOUBLE PRECISION",
                "music_status": "VARCHAR(20)",
                "music_mix_version": "VARCHAR(10)",
                # Final spoken CTA.
                "cta_enabled": "BOOLEAN",
                "cta_text": "TEXT",
                "cta_type": "VARCHAR(30)",
                "cta_language": "VARCHAR(10)",
                "cta_source": "VARCHAR(20)",
                "cta_audio_duration_seconds": "DOUBLE PRECISION",
                "cta_fallback_used": "BOOLEAN",
                "playlist_status": "VARCHAR(20)",
            },
        )
    if "content_pillars" in tables:
        add_missing_columns("content_pillars", {"youtube_playlist_id": "VARCHAR(64)"})
    if "video_scenes" in tables:
        add_missing_columns(
            "video_scenes",
            {"is_cta": "BOOLEAN DEFAULT FALSE"},
        )
    if "channel_ideas" in tables:
        add_missing_columns(
            "channel_ideas",
            {"content_pillar_id": "INTEGER", "normalized_title": "VARCHAR(300)"},
        )
    if "footage_assets" in tables:
        add_missing_columns(
            "footage_assets",
            {"analysis_json": "TEXT", "analysis_model": "VARCHAR(80)", "analyzed_at": "DATETIME"},
        )
    if "channels" in tables:
        add_missing_columns(
            "channels",
            {
                "youtube_channel_title": "VARCHAR(255)",
                "youtube_connection_status": "VARCHAR(30)",
                "youtube_connected_at": "DATETIME",
                "youtube_social_account_id": "INTEGER",
                "youtube_last_verified_at": "DATETIME",
                # Daily long-form autopilot (separate, memory-safe pipeline —
                # NOT the Shorts factory render). One video/day, paced by
                # longform_last_generated_at.
                "longform_enabled": "BOOLEAN DEFAULT FALSE NOT NULL",
                "longform_last_generated_at": "DATETIME",
            },
        )
    if "posts" in tables:
        add_missing_columns("posts", POSTS_ADDITIONAL_COLUMNS)
    if "plans" in tables:
        add_missing_columns("plans", PLANS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE plans
                    SET name = 'light_legacy'
                    WHERE name = 'light'
                      AND NOT EXISTS (SELECT 1 FROM plans WHERE name = 'light_legacy')
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE plans
                    SET name = 'growth_legacy'
                    WHERE name = 'pro'
                      AND NOT EXISTS (SELECT 1 FROM plans WHERE name = 'growth_legacy')
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE plans
                    SET name = 'agency_legacy'
                    WHERE name = 'agency'
                      AND NOT EXISTS (SELECT 1 FROM plans WHERE name = 'agency_legacy')
                    """
                )
            )
            if "app_users" in tables:
                conn.execute(text("UPDATE app_users SET plan = 'light_legacy' WHERE plan = 'light'"))
                conn.execute(text("UPDATE app_users SET plan = 'growth_legacy' WHERE plan = 'pro'"))
                conn.execute(text("UPDATE app_users SET plan = 'agency_legacy' WHERE plan = 'agency'"))
            if "subscriptions" in tables:
                conn.execute(text("UPDATE subscriptions SET plan = 'free' WHERE plan = 'trial'"))
                conn.execute(text("UPDATE subscriptions SET plan = 'light_legacy' WHERE plan = 'light'"))
                conn.execute(text("UPDATE subscriptions SET plan = 'growth_legacy' WHERE plan = 'pro'"))
                conn.execute(text("UPDATE subscriptions SET plan = 'agency_legacy' WHERE plan = 'agency'"))
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
    if "content_briefs" in tables:
        add_missing_columns("content_briefs", CONTENT_BRIEFS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE content_briefs SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
    if "content_strategies" in tables:
        add_missing_columns("content_strategies", CONTENT_STRATEGIES_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE content_strategies SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
    if "content_drafts" in tables:
        add_missing_columns("content_drafts", CONTENT_DRAFTS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE content_drafts SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
    if "user_templates" in tables:
        add_missing_columns("user_templates", USER_TEMPLATES_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE user_templates SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("UPDATE user_templates SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"))
    if "niches" in tables:
        add_missing_columns("niches", NICHES_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE niches SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("UPDATE niches SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_niches_slug ON niches (slug)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_niches_sort_order ON niches (sort_order, id)"))
    if "templates" in tables:
        add_missing_columns("templates", TEMPLATES_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE templates SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("UPDATE templates SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_templates_niche_sort ON templates (niche_id, sort_order, id)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_templates_niche_slug ON templates (niche_id, slug)"))
    if "ai_score_daily" in tables:
        add_missing_columns("ai_score_daily", AI_SCORE_DAILY_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE ai_score_daily SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_score_daily_user_day ON ai_score_daily (user_id, day)")
            )
    if "ai_scores_daily" in tables:
        add_missing_columns("ai_scores_daily", AI_SCORES_DAILY_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE ai_scores_daily SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_scores_daily_user_day ON ai_scores_daily (user_id, day)")
            )
    if "forecasts" in tables:
        add_missing_columns("forecasts", FORECASTS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE forecasts SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_forecasts_user_horizon ON forecasts (user_id, horizon_days, created_at)"))
    if "user_style_prefs" in tables:
        add_missing_columns("user_style_prefs", USER_STYLE_PREFS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE user_style_prefs SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("UPDATE user_style_prefs SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_style_prefs_user ON user_style_prefs (user_id)"))
    if "subscriptions" in tables:
        add_missing_columns("subscriptions", SUBSCRIPTIONS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE subscriptions SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_user ON subscriptions (user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_subscriptions_status ON subscriptions (status)"))
    if "usage_counters" in tables:
        add_missing_columns("usage_counters", USAGE_COUNTERS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE usage_counters SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("UPDATE usage_counters SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"))
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_usage_counter_user_period "
                    "ON usage_counters (user_id, period_start, period_end)"
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_usage_counter_user ON usage_counters (user_id, period_start)"))
    if "usage_events" in tables:
        add_missing_columns("usage_events", USAGE_EVENTS_ADDITIONAL_COLUMNS)
        with engine.begin() as conn:
            conn.execute(text("UPDATE usage_events SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_usage_events_user_type ON usage_events (user_id, type, created_at)"))
    # Keep dashboard account-unification table in sync with existing social_accounts storage.
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "social_accounts" in tables and "connected_accounts" in tables:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO connected_accounts
                        (user_id, platform, external_id, display_name, access_token, refresh_token, token_expires_at, created_at, updated_at)
                    SELECT
                        sa.user_id,
                        CASE WHEN LOWER(COALESCE(sa.provider, '')) = 'youtube' THEN 'youtube' ELSE 'meta' END AS platform,
                        COALESCE(NULLIF(TRIM(sa.page_id), ''), 'account-' || CAST(sa.id AS VARCHAR)) AS external_id,
                        sa.page_name,
                        sa.token_encrypted,
                        NULL,
                        sa.token_expires_at,
                        COALESCE(sa.created_at, CURRENT_TIMESTAMP),
                        COALESCE(sa.updated_at, sa.created_at, CURRENT_TIMESTAMP)
                    FROM social_accounts sa
                    WHERE sa.user_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1
                        FROM connected_accounts ca
                        WHERE ca.user_id = sa.user_id
                          AND ca.platform = CASE WHEN LOWER(COALESCE(sa.provider, '')) = 'youtube' THEN 'youtube' ELSE 'meta' END
                          AND ca.external_id = COALESCE(NULLIF(TRIM(sa.page_id), ''), 'account-' || CAST(sa.id AS VARCHAR))
                      )
                    """
                )
            )


if __name__ == "__main__":
    run_migrations()
    print("Migrations applied")
