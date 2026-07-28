import importlib
import os
import sys

import pytest


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test_video.db"
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
    ]:
        if name in sys.modules:
            del sys.modules[name]

    app_module = importlib.import_module("app")
    with app_module.app.test_client() as test_client:
        yield test_client


def register_user(client, email="user@test.local", password="pass12345"):
    challenge = client.post("/api/auth/register", json={"email": email, "password": password})
    payload = challenge.get_json() or {}
    return client.post("/api/auth/verify-code", json={"challenge_token": payload.get("challenge_token"), "code": payload.get("dev_code")})


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_video_script_generator_shape():
    import video_script_generator as vsg

    bundle = vsg.generate(
        topic="Как сервису увеличить входящие заявки",
        offer=None,
        language="ru",
        target_seconds=30,
        style="expert",
    )
    assert isinstance(bundle.phrases, list) and len(bundle.phrases) >= 3
    assert isinstance(bundle.shotlist, list) and len(bundle.shotlist) >= 1
    assert isinstance(bundle.title, str) and bundle.title
    assert isinstance(bundle.description, str)


def test_video_generate_endpoint_creates_job(client, monkeypatch):
    reg = register_user(client, "videojob@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    import saas_api as saas_api_module
    monkeypatch.setattr(saas_api_module, "_start_generation_job", lambda *_args, **_kwargs: None)

    resp = client.post(
        "/api/video/generate",
        json={
            "topic": "Видео о построении контент-воронки",
            "format": "short",
            "target_seconds": 30,
            "orientation": "vertical",
            "style": "friendly",
            "language": "ru",
        },
        headers=headers,
    )
    assert resp.status_code == 202
    payload = resp.get_json()
    assert payload["job_id"] > 0

    status = client.get(f"/api/video/jobs/{payload['job_id']}", headers=headers)
    assert status.status_code == 200
    body = status.get_json()
    assert body["status"] in {"queued", "running", "downloading", "rendering", "uploading", "done"}


def test_video_style_packs_endpoint(client):
    reg = register_user(client, "styles@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)
    resp = client.get("/api/video/style-packs", headers=headers)
    assert resp.status_code == 200
    payload = resp.get_json()
    assert isinstance(payload.get("items"), list)
    assert any(str(x.get("id")) == "default_pro" for x in payload["items"])
    assert str(payload.get("default_style_pack")) != ""


def test_ai_video_render_and_status_shape(client, monkeypatch):
    reg = register_user(client, "ai-video@test.local", "pass12345")
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    import saas_api as saas_api_module
    monkeypatch.setattr(saas_api_module, "_start_generation_job", lambda *_args, **_kwargs: None)

    resp = client.post(
        "/api/ai/video/render",
        json={
            "topic": "Ролик про SMM автоматизацию",
            "format": "short",
            "target_seconds": 30,
            "orientation": "vertical",
            "language": "ru",
            "scene_seconds": 4,
            "minimize_repeats": True,
            "realistic_only": True,
        },
        headers=headers,
    )
    assert resp.status_code == 202
    payload = resp.get_json() or {}
    job_id = int(payload.get("job_id") or 0)
    assert job_id > 0

    status = client.get(f"/api/ai/video/jobs/{job_id}", headers=headers)
    assert status.status_code == 200
    body = status.get_json() or {}
    assert body.get("status") in {"queued", "running", "success", "error"}
    assert isinstance(body.get("progress"), int)
    assert body.get("step") in {"queued", "preparing_script", "structure", "footage", "render", "export", "upload"}
    assert "message" in body
