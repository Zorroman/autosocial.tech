"""Factory dashboard, readiness and cleanup safety tests."""
import json
import sys

import pytest

from tests.test_private_admin import _fresh_app, _seed_admin, _token_for


def _fresh(tmp_path):
    for m in ("publications_api", "video_projects_api", "analytics_api", "ai_pricing", "factory_dashboard_api"):
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


def test_dashboard_empty_state(client):
    r = client.get("/api/factory-dashboard", headers=_h(client))
    assert r.status_code == 200
    d = r.get_json()
    assert d["overview"]["channels_total"] == 0
    assert d["overview"]["views_7d"] is None  # no data -> null, not zero
    assert d["channels"] == []
    assert d["recent_projects"] == []
    body = json.dumps(d).lower()
    assert "stripe" not in body and "trial" not in body and "billing" not in body


def test_dashboard_with_data_and_alerts(client):
    h = _h(client)
    ch = client.post("/api/channels", json={"name": "Эзотерика"}, headers=h).get_json()["channel"]["id"]
    pid = client.post("/api/video-projects", json={"channel_id": ch, "title": "Видео", "script_text": "Раз. Два. Три. Четыре.", "voice_mode": "silent"}, headers=h).get_json()["project"]["id"]
    d = client.get("/api/factory-dashboard", headers=h).get_json()
    assert d["overview"]["channels_total"] == 1
    assert d["overview"]["projects_in_progress"] == 1
    # project without scenes -> alert; channel without YouTube -> alert
    texts = " ".join(a["text"] for a in d["alerts"])
    assert "без сцен" in texts
    assert "без подключённого YouTube" in texts
    assert all(a.get("link") for a in d["alerts"])
    # activity contains real project creation event only
    types = {a["type"] for a in d["activity"]}
    assert "project_created" in types


def test_dashboard_requires_auth(client):
    assert client.get("/api/factory-dashboard").status_code == 401
    assert client.get("/api/readiness").status_code == 401


def test_readiness_shape_and_no_secrets(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value-should-not-leak")
    r = client.get("/api/readiness", headers=_h(client))
    assert r.status_code in (200, 503)
    d = r.get_json()
    assert d["status"] in {"ready", "degraded", "not_ready"}
    body = json.dumps(d)
    assert "sk-secret-value-should-not-leak" not in body
    assert "checks" in d and "database" in d["checks"]
    assert d["checks"]["database"]["critical"] is True
    assert d["checks"]["pexels_key"]["critical"] is False  # optional dep


def test_readiness_optional_missing_is_degraded_not_critical(client, monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    r = client.get("/api/readiness", headers=_h(client))
    d = r.get_json()
    # optional failures alone must not produce not_ready
    if all(c["ok"] for c in d["checks"].values() if c["critical"]):
        assert d["status"] in {"degraded", "ready"}
        assert r.status_code == 200


def test_readiness_critical_failure_not_ready(client, monkeypatch):
    import factory_dashboard_api as fda
    monkeypatch.setattr(fda, "_bin_version", lambda b: None)  # ffmpeg "missing"
    r = client.get("/api/readiness", headers=_h(client))
    assert r.status_code == 503
    assert r.get_json()["status"] == "not_ready"


def test_cleanup_dry_run_protects_referenced_files(client, tmp_path):
    h = _h(client)
    ch = client.post("/api/channels", json={"name": "C"}, headers=h).get_json()["channel"]["id"]
    pid = client.post("/api/video-projects", json={"channel_id": ch, "title": "V", "script_text": "Раз. Два.", "voice_mode": "silent"}, headers=h).get_json()["project"]["id"]
    scenes = client.post(f"/api/video-projects/{pid}/split-scenes", headers=h).get_json()["scenes"]
    for s in scenes:
        client.post(f"/api/scenes/{s['id']}/fixture-media", headers=h)

    sys.path.insert(0, "scripts")
    import importlib
    import cleanup_runtime
    importlib.reload(cleanup_runtime)
    from database import SessionLocal
    db = SessionLocal()
    try:
        refs = cleanup_runtime.referenced_paths(db)
        assert refs, "scene media must be referenced"
        candidates = cleanup_runtime.collect_candidates(db)
        candidate_paths = {str(p.resolve()) for _, p in candidates}
        # no referenced file may appear in deletion candidates
        assert not (refs & candidate_paths)
    finally:
        db.close()
