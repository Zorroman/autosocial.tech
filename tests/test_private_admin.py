"""Private single-admin mode + Channel API tests.

Covers: registration always 403, allowlist login, stale session denial,
fail-closed empty allowlist, channel CRUD, isolation, idea flow.
"""
import importlib
import os
import sys

import pytest

ADMIN_EMAIL = "owner@test.local"
ADMIN_PASSWORD = "ownerpass123"


def _fresh_app(tmp_path, allowlist=ADMIN_EMAIL, private="true"):
    db_file = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    os.environ["USE_MOCK_PROVIDERS"] = "true"
    os.environ["SYNC_JOBS"] = "true"
    os.environ["ENV"] = "development"
    os.environ["PRIVATE_ADMIN_MODE"] = private
    os.environ["ADMIN_ALLOWLIST_EMAILS"] = allowlist
    os.environ["SMTP_HOST"] = ""
    for name in [
        "app", "database", "models", "app_models", "app_services", "auth",
        "api", "job_queue", "app_settings", "channels_api", "video_projects_api",
        "services.entitlements", "plans_catalog", "factory_pipeline", "footage_library",
        "media_diversity", "video_script_generator", "shorts_hook_diversity",
        "openai_client", "openai_quota_guard",
    ]:
        sys.modules.pop(name, None)
    return importlib.import_module("app")


def _seed_admin(email=ADMIN_EMAIL, password=ADMIN_PASSWORD, role="admin"):
    from database import SessionLocal
    from auth import hash_password
    from app_models import AppUser

    db = SessionLocal()
    try:
        user = AppUser(email=email, password_hash=hash_password(password), role=role, plan="pro")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def _token_for(user_id):
    from auth import create_token
    return create_token(user_id)


@pytest.fixture()
def client(tmp_path):
    app_module = _fresh_app(tmp_path)
    admin_id = _seed_admin()
    outsider_id = _seed_admin(email="outsider@test.local", role="user")
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)
        c.outsider_token = _token_for(outsider_id)
        yield c


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_always_403(client):
    r = client.post("/api/auth/register", json={"email": "new@test.local", "password": "password123"})
    assert r.status_code == 403


def test_register_403_even_for_allowlisted_email(client):
    r = client.post("/api/auth/register", json={"email": ADMIN_EMAIL, "password": "password123"})
    assert r.status_code == 403


def test_login_outside_allowlist_403(client):
    r = client.post("/api/auth/login", json={"email": "outsider@test.local", "password": ADMIN_PASSWORD})
    assert r.status_code == 403


def test_allowlisted_login_challenge_starts(client):
    r = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    assert (r.get_json() or {}).get("challenge_token")


def test_anonymous_protected_api_401(client):
    assert client.get("/api/channels").status_code == 401


def test_stale_session_outside_allowlist_403(client):
    r = client.get("/api/channels", headers=_h(client.outsider_token))
    assert r.status_code == 403


def test_admin_session_allowed(client):
    r = client.get("/api/channels", headers=_h(client.admin_token))
    assert r.status_code == 200


def test_empty_allowlist_fails_closed(tmp_path):
    app_module = _fresh_app(tmp_path, allowlist="")
    admin_id = _seed_admin()
    token = _token_for(admin_id)
    with app_module.app.test_client() as c:
        assert c.get("/api/channels", headers=_h(token)).status_code == 403
        assert c.post("/api/auth/register", json={"email": "x@y.z", "password": "password123"}).status_code == 403
        assert c.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).status_code == 403


def test_channel_crud_and_isolation(client):
    h = _h(client.admin_token)
    created = client.post("/api/channels", json={"name": "Эзотерика", "niche": "эзотерика"}, headers=h)
    assert created.status_code == 201
    ch = created.get_json()["channel"]
    assert ch["slug"] == "channel" or ch["slug"]  # cyrillic name -> fallback slug
    cid = ch["id"]

    got = client.get(f"/api/channels/{cid}", headers=h)
    assert got.status_code == 200

    upd = client.patch(f"/api/channels/{cid}", json={"status": "active", "default_video_duration_seconds": 50}, headers=h)
    assert upd.status_code == 200
    assert upd.get_json()["channel"]["status"] == "active"

    bad = client.patch(f"/api/channels/{cid}", json={"status": "bogus"}, headers=h)
    assert bad.status_code == 400

    # Ideas
    idea = client.post(f"/api/channels/{cid}/ideas", json={"title": "Знаки луны"}, headers=h)
    assert idea.status_code == 201
    idea_id = idea.get_json()["idea"]["id"]
    st = client.patch(f"/api/ideas/{idea_id}", json={"status": "saved"}, headers=h)
    assert st.status_code == 200
    assert st.get_json()["idea"]["status"] == "saved"

    # Delete blocked by dependent ideas
    assert client.delete(f"/api/channels/{cid}", headers=h).status_code == 409

    # Isolation: another allowlisted user cannot see this channel
    from auth import create_token
    other_id = _seed_admin(email="second@test.local", role="user")
    os.environ["ADMIN_ALLOWLIST_EMAILS"] = f"{ADMIN_EMAIL},second@test.local"
    import app_settings
    importlib.reload(app_settings)
    other_token = create_token(other_id)
    r = client.get(f"/api/channels/{cid}", headers=_h(other_token))
    assert r.status_code in (403, 404)


def test_channel_limit(client):
    h = _h(client.admin_token)
    for i in range(10):
        r = client.post("/api/channels", json={"name": f"Ch {i}"}, headers=h)
        assert r.status_code == 201
    r = client.post("/api/channels", json={"name": "Ch 11"}, headers=h)
    assert r.status_code == 409
