import importlib
import os
import sys
from pathlib import Path

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
    return client.post("/api/auth/register", json={"email": email, "password": password})


def login_user(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


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

    for i in range(5):
        resp = client.post(
            "/api/generate",
            json={"project_id": project_id, "topic": f"topic {i}", "category": "business"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 202

    blocked = client.post(
        "/api/generate",
        json={"project_id": project_id, "topic": "topic 6", "category": "business"},
        headers=auth_headers(token),
    )
    assert blocked.status_code == 429


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
        json={"plan": "pro"},
        headers=auth_headers(admin_token),
    )
    assert update.status_code == 200
    assert update.get_json()["plan"] == "pro"


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
