import importlib
import os
import sys

import pytest


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test_preview.db"
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


def register_user(client, email="preview@test.local", password="pass12345"):
    challenge = client.post("/api/auth/register", json={"email": email, "password": password})
    payload = challenge.get_json() or {}
    return client.post("/api/auth/verify-code", json={"challenge_token": payload.get("challenge_token"), "code": payload.get("dev_code")})


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_preview_validate_image_ok(client):
    reg = register_user(client, "preview1@test.local", "pass12345")
    token = reg.get_json()["token"]
    r = client.post(
        "/api/preview/validate",
        headers=auth_headers(token),
        json={
            "platform": "instagram",
            "content_type": "image_post",
            "caption": "Короткий пост с пользой и вопросом в конце?",
            "cta": "Напишите в сообщения",
            "hashtags": ["#контент", "#маркетинг", "#smm", "#бизнес", "#рост"],
            "media": {"type": "image", "url": "https://example.com/image.jpg", "width": 1080, "height": 1350},
            "meta": {"goal": "engagement"},
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] in {"ok", "partial"}
    data = body.get("data") or {}
    assert int(data.get("score") or 0) > 0
    assert (data.get("preview") or {}).get("platform") == "instagram"


def test_preview_validate_blocks_youtube_without_video(client):
    reg = register_user(client, "preview2@test.local", "pass12345")
    token = reg.get_json()["token"]
    r = client.post(
        "/api/preview/validate",
        headers=auth_headers(token),
        json={
            "platform": "youtube",
            "content_type": "image_post",
            "caption": "Описание видео",
            "hashtags": ["#one", "#two", "#three", "#four", "#five"],
            "media": {"type": "image", "url": "https://example.com/image.jpg"},
            "meta": {"goal": "awareness"},
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "error"
    warnings = ((body.get("data") or {}).get("warnings") or [])
    codes = {str(w.get("code")) for w in warnings if isinstance(w, dict)}
    assert "platform_mismatch" in codes


def test_preview_validate_video_warnings(client):
    reg = register_user(client, "preview3@test.local", "pass12345")
    token = reg.get_json()["token"]
    r = client.post(
        "/api/preview/validate",
        headers=auth_headers(token),
        json={
            "platform": "instagram",
            "content_type": "video_post",
            "caption": "Тестовый ролик",
            "hashtags": ["#one"],
            "media": {"type": "video", "url": "https://example.com/video.mp4", "width": 1920, "height": 1080, "duration_s": 95},
            "meta": {"goal": "engagement", "format_hint": "reel"},
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "partial"
    warnings = ((body.get("data") or {}).get("warnings") or [])
    codes = {str(w.get("code")) for w in warnings if isinstance(w, dict)}
    assert "short_duration_gt_60" in codes
    assert "short_ratio_mismatch" in codes
