# -*- coding: cp1251 -*-
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    os.environ["USE_MOCK_PROVIDERS"] = "true"
    os.environ["SYNC_JOBS"] = "true"
    os.environ["ADMIN_EMAIL"] = "admin@test.local"
    os.environ["ADMIN_PASSWORD"] = "adminpass123"
    os.environ["GOOGLE_CLIENT_ID"] = ""
    os.environ["GOOGLE_CLIENT_SECRET"] = ""
    os.environ["FACEBOOK_APP_ID"] = ""
    os.environ["FACEBOOK_APP_SECRET"] = ""
    os.environ["FACEBOOK_CLIENT_ID"] = ""
    os.environ["FACEBOOK_CLIENT_SECRET"] = ""
    os.environ["FB_APP_ID"] = ""
    os.environ["FB_APP_SECRET"] = ""
    os.environ["FB_LOGIN_APP_ID"] = ""
    os.environ["FB_LOGIN_APP_SECRET"] = ""
    os.environ["FB_LOGIN_SCOPE"] = "public_profile,email"
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
    ]:
        if name in sys.modules:
            del sys.modules[name]

    app_module = importlib.import_module("app")
    with app_module.app.test_client() as test_client:
        yield test_client


def register_user(client, email="user@test.local", password="pass12345"):
    challenge = client.post("/api/auth/register", json={"email": email, "password": password})
    if challenge.status_code != 200:
        return challenge
    payload = challenge.get_json() or {}
    code = payload.get("dev_code")
    challenge_token = payload.get("challenge_token")
    assert challenge_token, "challenge_token missing in register response"
    assert code, "dev_code missing in register response"
    return client.post("/api/auth/verify-code", json={"challenge_token": challenge_token, "code": code})


def login_user(client, email, password):
    challenge = client.post("/api/auth/login", json={"email": email, "password": password})
    if challenge.status_code != 200:
        return challenge
    payload = challenge.get_json() or {}
    code = payload.get("dev_code")
    challenge_token = payload.get("challenge_token")
    assert challenge_token, "challenge_token missing in login response"
    assert code, "dev_code missing in login response"
    return client.post("/api/auth/verify-code", json={"challenge_token": challenge_token, "code": code})



def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_auth_and_role_access(client):
    reg = register_user(client)
    assert reg.status_code == 200
    token = reg.get_json()["token"]

    me = client.get("/api/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.get_json()["role"] == "user"

    admin_only = client.get("/api/admin/users", headers=auth_headers(token))
    assert admin_only.status_code == 403


def test_limit_free_plan(client):
    reg = register_user(client, "limit@test.local", "pass12345")
    token = reg.get_json()["token"]

    projects = client.get("/api/projects", headers=auth_headers(token)).get_json()
    project_id = projects[0]["id"]

    created = client.post(
        "/api/generate",
        json={"project_id": project_id, "topic": "topic 1", "category": "business"},
        headers=auth_headers(token),
    )
    assert created.status_code == 202
    post_id = created.get_json()["id"]

    blocked = client.post(
        f"/api/posts/{post_id}/publish",
        json={},
        headers=auth_headers(token),
    )
    assert blocked.status_code == 403
    body = blocked.get_json() or {}
    assert body.get("error") == "PAYWALL_FEATURE"


def test_topic_suggestions_upsert(client):
    reg = register_user(client, "suggest@test.local", "pass12345")
    token = reg.get_json()["token"]

    projects = client.get("/api/projects", headers=auth_headers(token)).get_json()
    project_id = projects[0]["id"]

    for _ in range(2):
        resp = client.post(
            "/api/generate",
            json={"project_id": project_id, "topic": "Контент-план на неделю", "category": "marketing"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 202

    suggestions = client.get(
        f"/api/topics/suggestions?project_id={project_id}&category=marketing",
        headers=auth_headers(token),
    )
    assert suggestions.status_code == 200
    payload = suggestions.get_json()
    assert any(item["topic"] == "Контент-план на неделю" and item["usage_count"] >= 2 for item in payload["frequent"])


def test_admin_can_change_plan(client):
    register_user(client, "user2@test.local", "pass12345")
    admin_login = login_user(client, "admin@test.local", "adminpass123")
    assert admin_login.status_code == 200
    admin_token = admin_login.get_json()["token"]

    users = client.get("/api/admin/users", headers=auth_headers(admin_token)).get_json()
    target = next(u for u in users if u["email"] == "user2@test.local")

    update = client.patch(
        f"/api/admin/users/{target['id']}/plan",
        json={"plan": "growth"},
        headers=auth_headers(admin_token),
    )
    assert update.status_code == 200
    assert update.get_json()["plan"] == "growth"


def test_oauth_start_redirects_when_not_configured(client):
    google = client.get("/api/auth/oauth/google/start")
    assert google.status_code == 302
    assert "oauth_error=google_not_configured" in google.location

    facebook = client.get("/api/auth/oauth/facebook/start")
    assert facebook.status_code == 302
    assert "oauth_error=facebook_not_configured" in facebook.location


def test_auth_providers_status_endpoint(client):
    resp = client.get("/api/auth/providers")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["google"]["configured"] is False
    assert payload["facebook"]["configured"] is False


def test_facebook_oauth_scope_contains_supported_permissions(client):
    os.environ["FACEBOOK_APP_ID"] = "123456"
    os.environ["FACEBOOK_APP_SECRET"] = "secret"

    resp = client.get("/api/auth/oauth/facebook/start")
    assert resp.status_code == 302
    assert "facebook.com" in resp.location
    assert "scope=public_profile%2Cemail" in resp.location


def test_meta_connection_state_machine_and_actions(client):
    reg = register_user(client, "meta@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    created = client.post("/api/connections/meta/mock-connect", json={}, headers=headers)
    assert created.status_code == 200

    listed = client.get("/api/connections", headers=headers)
    assert listed.status_code == 200
    rows = listed.get_json()
    assert len(rows) >= 1
    row = rows[0]
    assert row["status"] == "connected_ready"
    assert row["primary_action"]["action"] == "test"
    assert row["status_help_text"]

    disconnected = client.post(f"/api/connections/{row['id']}/disconnect", json={}, headers=headers)
    assert disconnected.status_code == 200
    payload = disconnected.get_json()
    assert payload["status"] == "not_connected"
    assert payload["status_reason_code"] == "user_disconnected"

    listed2 = client.get("/api/connections", headers=headers).get_json()
    row2 = listed2[0]
    assert row2["status"] == "not_connected"
    assert row2["primary_action"]["action"] == "connect"


def test_meta_refresh_without_token_sets_not_connected(client):
    reg = register_user(client, "meta2@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    created = client.post("/api/connections/meta/mock-connect", json={}, headers=headers).get_json()
    row_id = created["id"]

    # Remove token via disconnect then refresh via new integration endpoint.
    client.post(f"/api/connections/{row_id}/disconnect", json={}, headers=headers)
    refreshed = client.post("/api/integrations/meta/refresh", json={}, headers=headers)
    assert refreshed.status_code == 200
    payload = refreshed.get_json()
    assert payload["status"] == "not_connected"
    assert payload["status_reason_code"] in {"no_token", "user_disconnected"}


def test_generate_creates_editable_post_until_published(client):
    reg = register_user(client, "editable@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    project_id = client.get("/api/projects", headers=headers).get_json()[0]["id"]
    created = client.post(
        "/api/generate",
        json={
            "project_id": project_id,
            "topic": "Тест редактирования",
            "category": "business",
            "platform": "instagram",
            "generated_text": "Черновой текст",
        },
        headers=headers,
    )
    assert created.status_code == 202
    post_id = created.get_json()["id"]

    # Should be editable before publish.
    patch_ok = client.patch(
        f"/api/posts/{post_id}",
        json={"generated_text": "Обновленный текст"},
        headers=headers,
    )
    assert patch_ok.status_code == 200
    assert patch_ok.get_json()["generated_text"] == "Обновленный текст"

    # After publish (mock), editing should be blocked.
    pub = client.post(f"/api/posts/{post_id}/publish", json={}, headers=headers)
    assert pub.status_code == 200
    patch_blocked = client.patch(
        f"/api/posts/{post_id}",
        json={"generated_text": "Попытка после публикации"},
        headers=headers,
    )
    assert patch_blocked.status_code == 409


def test_delete_project_requires_exact_confirmation_and_deletes_related_data(client):
    reg = register_user(client, "delete-project@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    admin_login = login_user(client, "admin@test.local", "adminpass123")
    assert admin_login.status_code == 200
    admin_token = admin_login.get_json()["token"]
    users = client.get("/api/admin/users", headers=auth_headers(admin_token)).get_json()
    target = next(u for u in users if u["email"] == "delete-project@test.local")
    plan_update = client.patch(
        f"/api/admin/users/{target['id']}/plan",
        json={"plan": "growth"},
        headers=auth_headers(admin_token),
    )
    assert plan_update.status_code == 200

    created = client.post("/api/projects", json={"name": "Удаляемый проект"}, headers=headers)
    assert created.status_code == 200
    project_id = created.get_json()["id"]

    generated = client.post(
        "/api/generate",
        json={"project_id": project_id, "topic": "Пост к удалению", "category": "business"},
        headers=headers,
    )
    assert generated.status_code == 202
    post_id = generated.get_json()["id"]

    bad_delete = client.delete(
        f"/api/projects/{project_id}",
        json={"confirm_name": "Неверное название"},
        headers=headers,
    )
    assert bad_delete.status_code == 400

    ok_delete = client.delete(
        f"/api/projects/{project_id}",
        json={"confirm_name": "Удаляемый проект"},
        headers=headers,
    )
    assert ok_delete.status_code == 200
    payload = ok_delete.get_json()
    assert payload["ok"] is True
    assert payload["deleted_project_id"] == project_id

    from database import SessionLocal
    from saas_models import CreditLedger, Post, Project, TopicSuggestion

    db = SessionLocal()
    try:
        assert db.query(Project).filter(Project.id == project_id).count() == 0
        assert db.query(Post).filter(Post.project_id == project_id).count() == 0
        assert db.query(TopicSuggestion).filter(TopicSuggestion.project_id == project_id).count() == 0
        assert db.query(CreditLedger).filter(CreditLedger.post_id == post_id).count() == 0
    finally:
        db.close()


def test_delete_last_project_allowed(client):
    reg = register_user(client, "last-project@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    only_project = client.get("/api/projects", headers=headers).get_json()[0]
    deleted = client.delete(
        f"/api/projects/{only_project['id']}",
        json={"confirm_name": only_project["name"]},
        headers=headers,
    )
    assert deleted.status_code == 200
    payload = deleted.get_json()
    assert payload["ok"] is True
    assert payload["deleted_project_id"] == only_project["id"]
    projects_after = client.get("/api/projects", headers=headers).get_json()
    assert len(projects_after) == 0


def test_delete_project_accepts_confirm_name_from_query(client):
    reg = register_user(client, "delete-query@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    admin_login = login_user(client, "admin@test.local", "adminpass123")
    assert admin_login.status_code == 200
    admin_token = admin_login.get_json()["token"]
    users = client.get("/api/admin/users", headers=auth_headers(admin_token)).get_json()
    target = next(u for u in users if u["email"] == "delete-query@test.local")
    plan_update = client.patch(
        f"/api/admin/users/{target['id']}/plan",
        json={"plan": "growth"},
        headers=auth_headers(admin_token),
    )
    assert plan_update.status_code == 200

    created = client.post("/api/projects", json={"name": "Query Delete"}, headers=headers)
    assert created.status_code == 200
    project_id = created.get_json()["id"]

    deleted = client.delete(f"/api/projects/{project_id}?confirm_name=Query%20Delete", headers=headers)
    assert deleted.status_code == 200
    assert deleted.get_json()["ok"] is True


def test_delete_project_via_post_endpoint(client):
    reg = register_user(client, "delete-post-endpoint@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    admin_login = login_user(client, "admin@test.local", "adminpass123")
    assert admin_login.status_code == 200
    admin_token = admin_login.get_json()["token"]
    users = client.get("/api/admin/users", headers=auth_headers(admin_token)).get_json()
    target = next(u for u in users if u["email"] == "delete-post-endpoint@test.local")
    plan_update = client.patch(
        f"/api/admin/users/{target['id']}/plan",
        json={"plan": "growth"},
        headers=auth_headers(admin_token),
    )
    assert plan_update.status_code == 200

    created = client.post("/api/projects", json={"name": "Delete via POST"}, headers=headers)
    assert created.status_code == 200
    project_id = created.get_json()["id"]

    deleted = client.post(f"/api/projects/{project_id}/delete", json={"confirm_name": "Delete via POST"}, headers=headers)
    assert deleted.status_code == 200
    assert deleted.get_json()["ok"] is True



def test_stripe_webhook_subscription_updates_plan_for_dynamic_price(client, monkeypatch):
    from database import SessionLocal
    from saas_auth import hash_password
    from saas_models import AppUser
    import stripe_service as stripe_service_module

    stripe_service = importlib.reload(stripe_service_module)

    db = SessionLocal()
    try:
        user = AppUser(
            email="stripe-plan@test.local",
            password_hash=hash_password("pass12345"),
            role="user",
            plan="free",
            stripe_customer_id="cus_test_dynamic_1",
            billing_status="inactive",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    monkeypatch.setattr(
        stripe_service.stripe.Price,
        "retrieve",
        lambda _price_id: {"id": _price_id, "lookup_key": "autosocial_pro_eur_month_v1", "metadata": {}},
    )

    event = {
        "id": "evt_dynamic_plan_1",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_dynamic_1",
                "customer": "cus_test_dynamic_1",
                "status": "active",
                "current_period_end": 1_900_000_000,
                "items": {"data": [{"price": {"id": "price_dynamic_1"}}]},
                "metadata": {},
            }
        },
    }

    stripe_service.process_stripe_event(event)

    db = SessionLocal()
    try:
        refreshed = db.query(AppUser).filter_by(id=user_id).first()
        assert refreshed.plan == "growth"
        assert refreshed.billing_status == "active"
        assert refreshed.stripe_subscription_id == "sub_dynamic_1"
    finally:
        db.close()


def test_stripe_portal_creates_customer_when_missing(client, monkeypatch):
    from database import SessionLocal
    from saas_auth import hash_password
    from saas_models import AppUser
    import stripe_service as stripe_service_module

    stripe_service = importlib.reload(stripe_service_module)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test_local")
    monkeypatch.setattr(stripe_service.stripe.Customer, "create", lambda **kwargs: SimpleNamespace(id="cus_created_1"))
    monkeypatch.setattr(
        stripe_service.stripe.billing_portal.Session,
        "create",
        lambda **kwargs: SimpleNamespace(url="https://billing.stripe.test/session/1"),
    )

    db = SessionLocal()
    try:
        user = AppUser(
            email="stripe-portal@test.local",
            password_hash=hash_password("pass12345"),
            role="user",
            plan="free",
            billing_status="inactive",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
        assert not user.stripe_customer_id
    finally:
        db.close()

    url = stripe_service.create_portal_link(SimpleNamespace(id=user_id))
    assert url == "https://billing.stripe.test/session/1"

    db = SessionLocal()
    try:
        refreshed = db.query(AppUser).filter_by(id=user_id).first()
        assert refreshed.stripe_customer_id == "cus_created_1"
    finally:
        db.close()

def test_create_generate_quick_returns_drafts(client):
    reg = register_user(client, "createquick@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    payload = {
        "mode": "quick",
        "topic": "Как сервису увеличить входящие заявки",
        "offer": "Бесплатный аудит",
        "language": "ru",
        "tone": "friendly",
        "goal": "sales",
        "platforms": ["facebook", "instagram"],
        "variants": 1,
    }
    resp = client.post("/api/create/generate", json=payload, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] in {"ok", "partial"}
    assert isinstance(body.get("drafts"), list)
    assert len(body["drafts"]) >= 1
    assert body["drafts"][0]["post_text"]


def test_create_rewrite_returns_updated_caption(client):
    reg = register_user(client, "createrewrite@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    resp = client.post(
        "/api/create/rewrite",
        json={
            "caption": "Мы запускаем новую услугу для малого бизнеса. Напишите в директ.",
            "instruction": "более продающе",
            "goal": "sales",
            "tone": "sales",
            "language": "ru",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] in {"ok", "partial"}
    assert isinstance(body.get("drafts"), list)
    assert len(body["drafts"]) == 1
    assert body["drafts"][0]["caption"]


def test_create_quality_check_returns_score(client):
    reg = register_user(client, "createquality@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    resp = client.post(
        "/api/create/quality-check",
        json={
            "caption": "Как снизить стоимость лида? 3 шага, которые можно внедрить за неделю.\n\n1. Аудит\n2. Креативы\n3. Оптимизация",
            "cta": "Напишите в директ и получите чек-лист.",
            "hashtags": ["#маркетинг", "#лиды", "#бизнес"],
            "goal": "sales",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert isinstance(body.get("quality"), dict)
    assert isinstance(body["quality"].get("score"), int)




def test_checkout_subscription_disabled_for_public_paid_plans(client):
    reg = register_user(client, "billing-disabled@test.local", "pass12345")
    token = reg.get_json()["token"]

    response = client.post(
        "/api/billing/checkout/subscription",
        json={"plan": "growth"},
        headers=auth_headers(token),
    )

    assert response.status_code == 409
    assert "недоступ" in str((response.get_json() or {}).get("error") or "").lower()
