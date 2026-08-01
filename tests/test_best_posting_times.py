import importlib
import os
import sys

import pytest


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test_best_times.db"
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
        "app_models",
        "app_services",
        "auth",
        "api",
        "job_queue",
        "app_settings",
    ]:
        if name in sys.modules:
            del sys.modules[name]

    app_module = importlib.import_module("app")
    with app_module.app.test_client() as test_client:
        yield test_client


def register_user(client, email="best@test.local", password="pass12345"):
    challenge = client.post("/api/auth/register", json={"email": email, "password": password})
    payload = challenge.get_json() or {}
    return client.post("/api/auth/verify-code", json={"challenge_token": payload.get("challenge_token"), "code": payload.get("dev_code")})


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_best_posting_times_returns_slots(client):
    reg = register_user(client, "best1@test.local", "pass12345")
    token = reg.get_json()["token"]
    r = client.get("/api/ai/best-posting-times?days=90&platform=instagram", headers=auth_headers(token))
    assert r.status_code == 200
    body = r.get_json() or {}
    assert body.get("status") == "ok"
    assert isinstance(body.get("best_days"), list) and len(body.get("best_days")) >= 1
    assert isinstance(body.get("best_hours"), list) and len(body.get("best_hours")) >= 1
    assert isinstance(body.get("next_slots"), list) and len(body.get("next_slots")) >= 1
