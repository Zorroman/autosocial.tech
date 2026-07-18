"""Analytics snapshots + AI cost tracking tests (private mode, no real APIs)."""
import importlib
import json
import sys
from datetime import datetime, timedelta

import pytest

from tests.test_private_admin import ADMIN_EMAIL, _fresh_app, _seed_admin, _token_for


def _fresh(tmp_path):
    for m in ("publications_api", "video_projects_api", "analytics_api", "ai_pricing"):
        sys.modules.pop(m, None)
    return _fresh_app(tmp_path)


@pytest.fixture()
def client(tmp_path):
    app_module = _fresh(tmp_path)
    admin_id = _seed_admin()
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)
        yield c


def _h(c):
    return {"Authorization": f"Bearer {c.admin_token}"}


def _mk_published(c, name="Эзотерика"):
    ch = c.post("/api/channels", json={"name": name}, headers=_h(c)).get_json()["channel"]["id"]
    pid = c.post("/api/video-projects", json={"channel_id": ch, "title": "Видео", "script_text": "Первое. Второе. Третье. Четвёртое.", "voice_mode": "silent"}, headers=_h(c)).get_json()["project"]["id"]
    for s in c.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(c)).get_json()["scenes"]:
        c.post(f"/api/scenes/{s['id']}/fixture-media", headers=_h(c))
    c.post(f"/api/video-projects/{pid}/render", headers=_h(c))
    pub = c.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(c)).get_json()["publication"]
    vid = "vid" + str(pub["id"]).zfill(8)
    c.post(f"/api/publications/{pub['id']}/manual-complete", json={"youtube_video_id": vid}, headers=_h(c))
    return ch, pid, pub["id"]


def test_manual_snapshot_crud(client):
    ch, pid, pub = _mk_published(client)
    r = client.post(f"/api/publications/{pub}/analytics", json={"views": 1200, "likes": 90, "comments": 12}, headers=_h(client))
    assert r.status_code == 201
    snap = r.get_json()["snapshot"]
    assert snap["data_source"] == "manual"
    assert snap["views"] == 1200
    assert snap["watch_time_minutes"] is None  # absent metric stays null, not zero

    upd = client.patch(f"/api/analytics/snapshots/{snap['id']}", json={"views": 1500}, headers=_h(client))
    assert upd.status_code == 200 and upd.get_json()["snapshot"]["views"] == 1500

    lst = client.get(f"/api/analytics/snapshots?publication_id={pub}", headers=_h(client)).get_json()["snapshots"]
    assert len(lst) == 1

    assert client.delete(f"/api/analytics/snapshots/{snap['id']}", headers=_h(client)).status_code == 200
    assert client.get(f"/api/analytics/snapshots?publication_id={pub}", headers=_h(client)).get_json()["snapshots"] == []


def test_snapshot_validation(client):
    ch, pid, pub = _mk_published(client)
    h = _h(client)
    assert client.post(f"/api/publications/{pub}/analytics", json={"views": -5}, headers=h).status_code == 400
    assert client.post(f"/api/publications/{pub}/analytics", json={"views": float("1e13")}, headers=h).status_code == 400
    assert client.post(f"/api/publications/{pub}/analytics", json={"average_view_percentage": 150}, headers=h).status_code == 400
    assert client.post(f"/api/publications/{pub}/analytics", json={"views": 10, "currency": "евро"}, headers=h).status_code == 400
    assert client.post(f"/api/publications/{pub}/analytics", json={}, headers=h).status_code == 400
    # NaN via JSON string
    assert client.post(f"/api/publications/{pub}/analytics", json={"views": "nan"}, headers=h).status_code == 400
    # duplicate captured_at
    ok = client.post(f"/api/publications/{pub}/analytics", json={"views": 10, "captured_at": "2026-07-01T10:00:00"}, headers=h)
    assert ok.status_code == 201
    dup = client.post(f"/api/publications/{pub}/analytics", json={"views": 11, "captured_at": "2026-07-01T10:00:00"}, headers=h)
    assert dup.status_code == 409


def test_channel_aggregation_and_isolation(client):
    ch1, _, pub1 = _mk_published(client, "A")
    ch2, _, pub2 = _mk_published(client, "B")
    h = _h(client)
    client.post(f"/api/publications/{pub1}/analytics", json={"views": 100, "likes": 10}, headers=h)
    client.post(f"/api/publications/{pub2}/analytics", json={"views": 900, "likes": 9, "comments": 1}, headers=h)

    out = client.get("/api/analytics/channels?period=all", headers=h).get_json()
    stats = {s["channel_id"]: s for s in out["channels"]}
    assert stats[ch1]["total_views"] == 100
    assert stats[ch2]["total_views"] == 900
    assert stats[ch2]["median_views"] == 900
    assert stats[ch1]["engagement_rate"] == 10.0
    # channel with no snapshots in a 7-day-old window still returns nulls, not zeros
    assert client.get("/api/analytics/channels?period=bogus", headers=h).status_code == 400

    # empty channel -> nulls
    ch3 = client.post("/api/channels", json={"name": "Пустой"}, headers=h).get_json()["channel"]["id"]
    out = client.get("/api/analytics/channels?period=all", headers=h).get_json()
    empty = next(s for s in out["channels"] if s["channel_id"] == ch3)
    assert empty["total_views"] is None
    assert empty["engagement_rate"] is None
    assert empty["median_views"] is None


def test_sync_requires_connection_and_mocked_paths(client, monkeypatch):
    ch, pid, pub = _mk_published(client)
    h = _h(client)
    # no YouTube connection -> 409
    r = client.post(f"/api/channels/{ch}/analytics/sync", headers=h)
    assert r.status_code == 409

    from database import SessionLocal
    from saas_models import Channel
    db = SessionLocal()
    c = db.query(Channel).filter_by(id=ch).first()
    c.youtube_channel_id = "UCx"
    c.youtube_connection_status = "connected"
    db.commit(); db.close()

    import analytics_api as aa
    # token unavailable -> 409 honest error
    monkeypatch.setattr(aa, "_valid_account_token", lambda db, acc: None)
    monkeypatch.setattr(aa, "_user_youtube_account", lambda db: object())
    r = client.post(f"/api/channels/{ch}/analytics/sync", headers=h)
    assert r.status_code == 409
    assert "token" in r.get_json()["error"].lower()

    # mocked API success
    monkeypatch.setattr(aa, "_valid_account_token", lambda db, acc: "tok")
    class FakeResp:
        status_code = 200
        ok = True
        def json(self):
            return {"items": [{"id": "vid" + str(pub).zfill(8), "statistics": {"viewCount": "321", "likeCount": "7", "commentCount": "2"}}]}
    monkeypatch.setattr(aa.requests, "get", lambda *a, **k: FakeResp())
    r = client.post(f"/api/channels/{ch}/analytics/sync", headers=h)
    assert r.status_code == 200
    assert r.get_json()["synced"] == 1
    snaps = client.get(f"/api/analytics/snapshots?publication_id={pub}", headers=h).get_json()["snapshots"]
    api_snaps = [s for s in snaps if s["data_source"] == "youtube_api"]
    assert api_snaps and api_snaps[0]["views"] == 321
    assert "token" not in json.dumps(snaps).lower()
    # API snapshot cannot be edited/deleted
    assert client.patch(f"/api/analytics/snapshots/{api_snaps[0]['id']}", json={"views": 1}, headers=h).status_code == 409
    assert client.delete(f"/api/analytics/snapshots/{api_snaps[0]['id']}", headers=h).status_code == 409

    # mocked quota error
    class QuotaResp:
        status_code = 403
        ok = False
        def json(self):
            return {"error": {"message": "quotaExceeded: The request cannot be completed"}}
    monkeypatch.setattr(aa.requests, "get", lambda *a, **k: QuotaResp())
    r = client.post(f"/api/channels/{ch}/analytics/sync", headers=h)
    assert r.status_code == 429
    # mocked revoked token
    class RevokedResp:
        status_code = 401
        ok = False
        def json(self):
            return {}
    monkeypatch.setattr(aa.requests, "get", lambda *a, **k: RevokedResp())
    r = client.post(f"/api/channels/{ch}/analytics/sync", headers=h)
    assert r.status_code == 409


def test_cost_records_and_free_ops(client):
    ch, pid, pub = _mk_published(client)
    out = client.get("/api/analytics/costs", headers=_h(client)).get_json()
    ops = {r["operation_type"] for r in out["records"]}
    # render and stock ops happened in fixture flow? fixture-media is local, render recorded:
    assert "render" in ops
    render_rec = next(r for r in out["records"] if r["operation_type"] == "render")
    assert render_rec["estimated_cost"] == 0.0  # known-free local op
    assert out["summary"]["daily_budget"] > 0


def test_unknown_price_is_null_not_zero(client):
    from ai_pricing import estimate_cost, record_cost
    assert estimate_cost("unknown-provider", "mystery-model", 1000, 1000) is None
    rec = record_cost(provider="unknown-provider", model="mystery-model",
                      operation_type="other", input_units=1000)
    assert rec.estimated_cost is None
    assert rec.actual_cost is None
    assert rec.currency is None


def test_cost_idempotency(client):
    from ai_pricing import record_cost
    a = record_cost(provider="pexels", model="stock", operation_type="stock_download", request_id="dup-1")
    b = record_cost(provider="pexels", model="stock", operation_type="stock_download", request_id="dup-1")
    assert a.id == b.id


def test_budget_enforcement(client, monkeypatch):
    import ai_pricing
    from database import SessionLocal
    monkeypatch.setenv("AI_DAILY_BUDGET", "0.01")
    db = SessionLocal()
    # existing paid spend
    ai_pricing.record_cost(provider="openai", model="gpt-4o-mini", operation_type="idea_generation",
                           input_units=1_000_000, output_units=0, db=db)  # 0.15 USD
    with pytest.raises(ai_pricing.BudgetExceeded):
        ai_pricing.check_budget(db, estimated_cost=0.05)
    # free op always passes
    ai_pricing.check_budget(db, estimated_cost=0.0)
    db.close()


def test_per_video_budget_and_regenerations(client, monkeypatch):
    import ai_pricing
    from database import SessionLocal
    monkeypatch.setenv("AI_MAX_COST_PER_VIDEO", "0.10")
    monkeypatch.setenv("AI_MAX_REGENERATIONS_PER_PROJECT", "2")
    db = SessionLocal()
    ai_pricing.record_cost(provider="openai", model="gpt-4o-mini", operation_type="script_generation",
                           project_id=999, input_units=600_000, output_units=0, db=db)  # 0.09
    with pytest.raises(ai_pricing.BudgetExceeded):
        ai_pricing.check_budget(db, project_id=999, estimated_cost=0.05)
    for i in range(2):
        ai_pricing.record_cost(provider="openai", model="gpt-4o-mini", operation_type="regeneration",
                               project_id=998, input_units=1, db=db)
    with pytest.raises(ai_pricing.BudgetExceeded):
        ai_pricing.check_budget(db, project_id=998, estimated_cost=0.01)
    db.close()


def test_edge_tts_recorded_free(client):
    from ai_pricing import estimate_cost
    assert estimate_cost("edge", "edge-tts", 500, None) == 0.0
    # paid OpenAI TTS calculation: 1M chars input price 0.60
    assert estimate_cost("openai", "gpt-4o-mini-tts", 1_000_000, None) == 0.60


def test_anonymous_and_isolation(client):
    assert client.get("/api/analytics/channels").status_code == 401
    assert client.get("/api/analytics/costs").status_code == 401
    ch, pid, pub = _mk_published(client)
    # other allowlisted user sees no data of this owner
    import os
    os.environ["ADMIN_ALLOWLIST_EMAILS"] = f"{ADMIN_EMAIL},other2@test.local"
    import saas_settings
    importlib.reload(saas_settings)
    other = _token_for(_seed_admin(email="other2@test.local", role="user"))
    r = client.post(f"/api/publications/{pub}/analytics", json={"views": 5}, headers={"Authorization": f"Bearer {other}"})
    assert r.status_code in (403, 404)
