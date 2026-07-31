import importlib
import os
import sys
from datetime import datetime, timedelta

import pytest


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "entitlements_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    os.environ["USE_MOCK_PROVIDERS"] = "true"
    os.environ["SYNC_JOBS"] = "true"
    os.environ["ADMIN_EMAIL"] = "admin@test.local"
    os.environ["ADMIN_PASSWORD"] = "adminpass123"
    os.environ["GOOGLE_CLIENT_ID"] = ""
    os.environ["GOOGLE_CLIENT_SECRET"] = ""
    os.environ["FB_LOGIN_APP_ID"] = ""
    os.environ["FB_LOGIN_APP_SECRET"] = ""
    os.environ["ENV"] = "development"
    os.environ["SMTP_HOST"] = ""
    os.environ["SMTP_FROM"] = ""
    os.environ["SMTP_USER"] = ""
    os.environ["SMTP_PASSWORD"] = ""

    for name in [
        "app",
        "database",
        "models",
        "saas_models",
        "saas_services",
        "saas_auth",
        "saas_api",
        "saas_queue",
        "saas_settings",
        "services.entitlements",
    ]:
        if name in sys.modules:
            del sys.modules[name]

    app_module = importlib.import_module("app")
    with app_module.app.test_client() as test_client:
        yield test_client


def _register(client, email: str, password: str = "pass12345") -> dict:
    challenge = client.post("/api/auth/register", json={"email": email, "password": password})
    assert challenge.status_code == 200
    payload = challenge.get_json() or {}
    verify = client.post(
        "/api/auth/verify-code",
        json={"challenge_token": payload.get("challenge_token"), "code": payload.get("dev_code")},
    )
    assert verify.status_code == 200
    return verify.get_json() or {}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_trial_user_cannot_publish(client):
    data = _register(client, "trial-publish@test.local")
    from database import SessionLocal
    from saas_models import AppUser
    from services.entitlements import ACTION_POST_PUBLISH, authorizeAction, sync_subscription_state

    user_id = int(data["user"]["id"])
    now = datetime.utcnow()
    sync_subscription_state(
        user_id=user_id,
        plan="free",
        status="trialing",
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=6),
        trial_ends_at=now + timedelta(days=6),
    )

    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=user_id).first()
        result = authorizeAction(user, ACTION_POST_PUBLISH, {})
    finally:
        db.close()

    assert result["allowed"] is False
    assert result["http_status"] == 403
    assert result["error_payload"]["error"] == "PAYWALL_FEATURE"


def test_expired_trial_cannot_generate_or_publish(client):
    data = _register(client, "trial-expired@test.local")
    from database import SessionLocal
    from saas_models import AppUser
    from services.entitlements import (
        ACTION_POST_GENERATE,
        ACTION_VIDEO_GENERATE,
        authorizeAction,
        sync_subscription_state,
    )

    user_id = int(data["user"]["id"])
    now = datetime.utcnow()
    sync_subscription_state(
        user_id=user_id,
        plan="free",
        status="trialing",
        current_period_start=now - timedelta(days=8),
        current_period_end=now - timedelta(days=1),
        trial_ends_at=now - timedelta(days=1),
    )

    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=user_id).first()
        post_result = authorizeAction(user, ACTION_POST_GENERATE, {})
        video_result = authorizeAction(user, ACTION_VIDEO_GENERATE, {})
    finally:
        db.close()

    assert post_result["allowed"] is False
    assert post_result["http_status"] == 402
    assert post_result["error_payload"]["required_plan"] == "starter"
    assert "Пробный период завершён" in post_result["error_payload"]["message"]
    assert video_result["allowed"] is False
    assert video_result["http_status"] == 402


def test_starter_autopublish_is_locked(client):
    data = _register(client, "starter-publish@test.local")
    from database import SessionLocal
    from saas_models import AppUser, UsageCounter
    from services.entitlements import ACTION_POST_PUBLISH, authorizeAction, sync_subscription_state

    user_id = int(data["user"]["id"])
    now = datetime.utcnow()
    sync_subscription_state(
        user_id=user_id,
        plan="starter",
        status="active",
        current_period_start=now - timedelta(days=3),
        current_period_end=now + timedelta(days=27),
    )

    db = SessionLocal()
    try:
        db.add(
            UsageCounter(
                user_id=user_id,
                period_start=now - timedelta(days=3),
                period_end=now + timedelta(days=27),
                posts_generated=0,
                posts_published=149,
                videos_generated=0,
                videos_published=0,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=user_id).first()
        ok = authorizeAction(user, ACTION_POST_PUBLISH, {})
    finally:
        db.close()
    assert ok["allowed"] is False
    assert ok["error_payload"]["error"] == "PAYWALL_FEATURE"
    assert ok["error_payload"]["required_plan"] == "growth"


def test_growth_limits_config(client):
    data = _register(client, "growth-limits@test.local")
    from database import SessionLocal
    from services.entitlements import getLimits, sync_subscription_state

    user_id = int(data["user"]["id"])
    now = datetime.utcnow()
    sync_subscription_state(
        user_id=user_id,
        plan="growth",
        status="active",
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
    )

    db = SessionLocal()
    try:
        limits = getLimits("growth")
    finally:
        db.close()

    assert limits["posts_per_month"] == 600
    assert limits["videos_per_month"] == 40
    assert limits["projects"] == 5


def test_legacy_pro_maps_to_growth_limits(client):
    data = _register(client, "pro-map@test.local")
    from database import SessionLocal
    from services.entitlements import getLimits, sync_subscription_state

    user_id = int(data["user"]["id"])
    now = datetime.utcnow()
    sync_subscription_state(
        user_id=user_id,
        plan="pro",
        status="active",
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
    )

    db = SessionLocal()
    try:
        limits = getLimits("pro")
    finally:
        db.close()

    assert limits["posts_per_month"] == 600
    assert limits["videos_per_month"] == 40


def test_agency_limits_and_unlimited_projects(client):
    data = _register(client, "agency-limits@test.local")
    from database import SessionLocal
    from services.entitlements import getLimits, sync_subscription_state

    user_id = int(data["user"]["id"])
    now = datetime.utcnow()
    sync_subscription_state(
        user_id=user_id,
        plan="agency",
        status="active",
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
    )

    db = SessionLocal()
    try:
        limits = getLimits("agency")
    finally:
        db.close()

    assert limits["posts_per_month"] == 2000
    assert limits["videos_per_month"] == 150
    assert limits["projects"] >= 999999


def test_billing_entitlements_endpoint(client):
    data = _register(client, "entitlements@test.local")
    token = data["token"]
    response = client.get("/api/billing/entitlements", headers=_headers(token))
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert "plan" in payload
    assert "limits" in payload
    assert "usage" in payload
    assert "remaining" in payload
    assert "percent_used" in payload
