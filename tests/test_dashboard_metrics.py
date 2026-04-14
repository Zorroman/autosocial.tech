import importlib
import os
import sys

import pytest


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "dashboard_test.db"
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
        "dashboard_metrics",
    ]:
        if name in sys.modules:
            del sys.modules[name]

    app_module = importlib.import_module("app")
    with app_module.app.test_client() as test_client:
        yield test_client


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def register_user(client, email="dash@test.local", password="pass12345"):
    challenge = client.post("/api/auth/register", json={"email": email, "password": password})
    payload = challenge.get_json() or {}
    return client.post(
        "/api/auth/verify-code",
        json={"challenge_token": payload.get("challenge_token"), "code": payload.get("dev_code")},
    )


def test_dashboard_sync_idempotent_and_read_endpoints(client, monkeypatch):
    reg = register_user(client)
    assert reg.status_code == 200
    token = reg.get_json()["token"]
    headers = auth_headers(token)

    from database import SessionLocal
    from saas_models import AiScoreDaily, AiScoreDailyV2, Forecast, ContentItem, ContentMetricDaily, SocialAccount
    from saas_services import encrypt_meta_token

    user_id = client.get("/api/me", headers=headers).get_json()["id"]
    from services.entitlements import sync_subscription_state
    sync_subscription_state(user_id=user_id, plan="growth", status="active")
    db = SessionLocal()
    try:
        db.add(
            SocialAccount(
                user_id=user_id,
                provider="meta",
                page_id="meta-page-1",
                page_name="Meta Page",
                ig_user_id="ig-user-1",
                ig_username="autosocial_ig",
                token_encrypted=encrypt_meta_token("meta-user-token"),
                status="connected_ready",
            )
        )
        db.add(
            SocialAccount(
                user_id=user_id,
                provider="youtube",
                page_id="yt-channel-1",
                page_name="YT Channel",
                token_encrypted=encrypt_meta_token("yt-access-token"),
                status="connected_ready",
            )
        )
        db.commit()
    finally:
        db.close()

    class FakeResponse:
        def __init__(self, payload, ok=True, status_code=200):
            self._payload = payload
            self.ok = ok
            self.status_code = status_code
            self.text = str(payload)
            self.content = b"1"

        def json(self):
            return self._payload

    def fake_list_pages(_token, include_page_access_token=False):
        return {
            "data": [
                {
                    "id": "meta-page-1",
                    "name": "Meta Page",
                    "access_token": "meta-page-token",
                }
            ]
        }

    def fake_get(url, params=None, headers=None, timeout=20):
        if "graph.facebook.com" in url and url.endswith("/posts"):
            return FakeResponse(
                {
                    "data": [
                        {
                            "id": "meta-post-1",
                            "message": "Meta post test",
                            "created_time": "2026-02-20T10:00:00+0000",
                            "permalink_url": "https://facebook.com/meta-post-1",
                            "attachments": {"data": [{"type": "photo"}]},
                        }
                    ]
                }
            )
        if "graph.facebook.com" in url and "/media" in url:
            return FakeResponse(
                {
                    "data": [
                        {
                            "id": "ig-media-1",
                            "caption": "Instagram post test",
                            "media_type": "IMAGE",
                            "permalink": "https://instagram.com/p/ig-media-1",
                            "timestamp": "2026-02-20T11:00:00+0000",
                        }
                    ]
                }
            )
        if "graph.facebook.com" in url and url.endswith("/insights"):
            return FakeResponse(
                {
                    "data": [
                        {"name": "post_impressions", "values": [{"value": 120}]},
                        {"name": "post_impressions_unique", "values": [{"value": 90}]},
                        {"name": "post_clicks", "values": [{"value": 10}]},
                        {"name": "post_reactions_like_total", "values": [{"value": 8}]},
                        {"name": "post_comments", "values": [{"value": 3}]},
                        {"name": "post_shares", "values": [{"value": 2}]},
                    ]
                }
            )
        if "graph.facebook.com" in url and "ig-media-1/insights" in url:
            return FakeResponse(
                {
                    "data": [
                        {"name": "impressions", "values": [{"value": 80}]},
                        {"name": "reach", "values": [{"value": 60}]},
                    ]
                }
            )
        if "graph.facebook.com" in url and "ig-media-1" in url:
            return FakeResponse({"like_count": 7, "comments_count": 2})
        if "graph.facebook.com" in url:
            return FakeResponse(
                {
                    "reactions": {"summary": {"total_count": 8}},
                    "comments": {"summary": {"total_count": 3}},
                    "shares": {"count": 2},
                }
            )
        if "youtube/v3/channels" in url:
            return FakeResponse(
                {
                    "items": [
                        {
                            "id": "yt-channel-1",
                            "snippet": {"title": "YT Channel"},
                            "contentDetails": {"relatedPlaylists": {"uploads": "uploads-1"}},
                        }
                    ]
                }
            )
        if "youtube/v3/playlistItems" in url:
            return FakeResponse({"items": [{"contentDetails": {"videoId": "yt-video-1"}}]})
        if "youtube/v3/videos" in url:
            return FakeResponse(
                {
                    "items": [
                        {
                            "id": "yt-video-1",
                            "snippet": {
                                "title": "YT Video 1",
                                "description": "Video body",
                                "publishedAt": "2026-02-21T12:00:00Z",
                            },
                            "statistics": {"viewCount": "200", "likeCount": "20", "commentCount": "5"},
                            "contentDetails": {"duration": "PT2M10S"},
                        }
                    ]
                }
            )
        return FakeResponse({}, ok=False, status_code=404)

    dashboard_metrics = importlib.import_module("dashboard_metrics")
    monkeypatch.setattr(dashboard_metrics, "list_pages", fake_list_pages)
    monkeypatch.setattr(dashboard_metrics.requests, "get", fake_get)

    first_sync = client.post("/api/dashboard/sync", json={}, headers=headers)
    assert first_sync.status_code == 200
    assert first_sync.get_json()["meta_items"] >= 1
    assert first_sync.get_json()["youtube_items"] >= 1

    second_sync = client.post("/api/dashboard/sync", json={}, headers=headers)
    assert second_sync.status_code == 200

    db = SessionLocal()
    try:
        items_count = db.query(ContentItem).filter(ContentItem.user_id == user_id).count()
        metrics_count = (
            db.query(ContentMetricDaily)
            .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
            .filter(ContentItem.user_id == user_id)
            .count()
        )
        assert items_count == 3
        assert metrics_count == 3
    finally:
        db.close()

    summary = client.get("/api/dashboard/summary?days=30", headers=headers)
    assert summary.status_code == 200
    assert summary.get_json()["reach"] >= 290
    assert summary.get_json()["views"] >= 320
    assert "ai_score" in summary.get_json()
    assert "current" in summary.get_json()
    assert "prev" in summary.get_json()
    assert "delta" in summary.get_json()
    assert "facebook" in (summary.get_json().get("by_platform") or {})
    assert "instagram" in (summary.get_json().get("by_platform") or {})
    assert "youtube" in (summary.get_json().get("by_platform") or {})

    timeseries = client.get("/api/dashboard/timeseries?days=30", headers=headers)
    assert timeseries.status_code == 200
    assert len(timeseries.get_json()["points"]) == 30
    first_point = (timeseries.get_json().get("points") or [{}])[0]
    assert "facebook_reach" in first_point
    assert "instagram_reach" in first_point
    assert "youtube_reach" in first_point

    ai_score = client.get("/api/dashboard/ai-score?days=30", headers=headers)
    assert ai_score.status_code == 200
    ai_payload = ai_score.get_json()
    assert "current" in ai_payload
    assert "delta_7d" in ai_payload
    assert "delta_vs_prev_period" in ai_payload
    assert "breakdown" in ai_payload
    assert len((ai_payload.get("breakdown") or {}).get("factors") or []) == 5
    assert len(ai_payload.get("timeseries") or []) == 30

    forecast = client.get("/api/dashboard/forecast?horizon=7&days=90", headers=headers)
    assert forecast.status_code == 200
    forecast_payload = forecast.get_json()
    assert int(forecast_payload.get("horizon_days") or 0) == 7
    assert len(forecast_payload.get("points") or []) == 7
    assert float((forecast_payload.get("totals") or {}).get("reach") or 0) >= 0
    assert float((forecast_payload.get("totals") or {}).get("views") or 0) >= 0

    insights = client.get("/api/dashboard/insights?days=30", headers=headers)
    assert insights.status_code == 200
    assert len(insights.get_json()["insights"]) >= 1

    recent = client.get("/api/dashboard/recent?limit=10", headers=headers)
    assert recent.status_code == 200
    assert len(recent.get_json()["items"]) == 3

    db = SessionLocal()
    try:
        stored_scores = db.query(AiScoreDaily).filter(AiScoreDaily.user_id == user_id).count()
        assert stored_scores >= 1
        stored_scores_v2 = db.query(AiScoreDailyV2).filter(AiScoreDailyV2.user_id == user_id).count()
        assert stored_scores_v2 >= 1
        stored_forecasts = db.query(Forecast).filter(Forecast.user_id == user_id).count()
        assert stored_forecasts >= 1
    finally:
        db.close()
