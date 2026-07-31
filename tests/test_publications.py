"""Publication workflow tests (private mode). No real YouTube calls —
upload/network paths are monkeypatched."""
import importlib
import json
import sys
from datetime import datetime, timedelta

import pytest

from tests.test_private_admin import ADMIN_EMAIL, _fresh_app, _seed_admin, _token_for

SCRIPT = "Первое предложение о свечах. Второе предложение о луне. Третье о традициях. Четвёртое о культуре."


def _fresh_app_pub(tmp_path):
    sys.modules.pop("publications_api", None)
    sys.modules.pop("video_projects_api", None)
    return _fresh_app(tmp_path)


@pytest.fixture()
def client(tmp_path):
    app_module = _fresh_app_pub(tmp_path)
    admin_id = _seed_admin()
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)
        yield c


def _h(c):
    return {"Authorization": f"Bearer {c.admin_token}"}


def _mk_rendered_project(c):
    """Channel -> project -> scenes -> fixture media -> sync render -> rendered."""
    ch = c.post("/api/channels", json={"name": "Эзотерика"}, headers=_h(c)).get_json()["channel"]["id"]
    pid = c.post("/api/video-projects", json={"channel_id": ch, "title": "Тестовый Short", "script_text": SCRIPT, "voice_mode": "silent"}, headers=_h(c)).get_json()["project"]["id"]
    scenes = c.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(c)).get_json()["scenes"]
    for s in scenes:
        r = c.post(f"/api/scenes/{s['id']}/fixture-media", headers=_h(c))
        assert r.status_code == 200
    r = c.post(f"/api/video-projects/{pid}/render", headers=_h(c))
    assert r.status_code == 202
    proj = c.get(f"/api/video-projects/{pid}", headers=_h(c)).get_json()["project"]
    assert proj["status"] == "rendered", proj.get("error")
    return ch, pid


def test_prepare_requires_completed_render(client):
    ch = client.post("/api/channels", json={"name": "X"}, headers=_h(client)).get_json()["channel"]["id"]
    pid = client.post("/api/video-projects", json={"channel_id": ch, "title": "Draft"}, headers=_h(client)).get_json()["project"]["id"]
    r = client.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(client))
    assert r.status_code == 409


def test_publication_crud_and_validation(client):
    ch, pid = _mk_rendered_project(client)
    r = client.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(client))
    assert r.status_code == 201
    pub = r.get_json()["publication"]
    assert pub["status"] == "draft"
    assert pub["file"]["size_bytes"] > 10_000

    # duplicate prepare -> 409
    assert client.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(client)).status_code == 409

    pub_id = pub["id"]
    upd = client.patch(f"/api/publications/{pub_id}", json={"title": "Символы луны", "tags": "#луна, #мистика", "privacy_status": "unlisted"}, headers=_h(client))
    assert upd.status_code == 200
    assert upd.get_json()["publication"]["tags"] == ["луна", "мистика"]

    assert client.patch(f"/api/publications/{pub_id}", json={"privacy_status": "secret"}, headers=_h(client)).status_code == 400
    past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    assert client.patch(f"/api/publications/{pub_id}", json={"scheduled_at": past}, headers=_h(client)).status_code == 400
    assert client.patch(f"/api/publications/{pub_id}", json={"title": ""}, headers=_h(client)).status_code == 400

    lst = client.get("/api/publications", headers=_h(client)).get_json()["publications"]
    assert len(lst) == 1
    # no tokens anywhere in the payload
    assert "token" not in json.dumps(lst).lower()


def test_manual_publish_flow(client):
    ch, pid = _mk_rendered_project(client)
    pub = client.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(client)).get_json()["publication"]
    r = client.post(f"/api/publications/{pub['id']}/manual-complete", json={"youtube_url": "https://www.youtube.com/shorts/dQw4w9WgXcQ"}, headers=_h(client))
    assert r.status_code == 200
    done = r.get_json()["publication"]
    assert done["status"] == "published"
    assert done["youtube_video_id"] == "dQw4w9WgXcQ"
    assert done["published_at"]

    # duplicate video id in another publication -> 409
    ch2, pid2 = _mk_rendered_project(client)
    pub2 = client.post(f"/api/video-projects/{pid2}/prepare-publication", headers=_h(client)).get_json()["publication"]
    r = client.post(f"/api/publications/{pub2['id']}/manual-complete", json={"youtube_video_id": "dQw4w9WgXcQ"}, headers=_h(client))
    assert r.status_code == 409
    # invalid id
    r = client.post(f"/api/publications/{pub2['id']}/manual-complete", json={"youtube_video_id": "nope"}, headers=_h(client))
    assert r.status_code == 400
    # already published -> 409
    r = client.post(f"/api/publications/{pub['id']}/manual-complete", json={"youtube_video_id": "aaaaaaaaaaa"}, headers=_h(client))
    assert r.status_code == 409


def test_upload_requires_connected_youtube(client):
    ch, pid = _mk_rendered_project(client)
    pub = client.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(client)).get_json()["publication"]
    r = client.post(f"/api/publications/{pub['id']}/upload", headers=_h(client))
    assert r.status_code == 409
    assert "YouTube" in r.get_json()["error"]


def _link_youtube(client, ch):
    from database import SessionLocal
    from saas_models import Channel
    db = SessionLocal()
    c = db.query(Channel).filter_by(id=ch).first()
    c.youtube_channel_id = "UCtestchannel000000000000"
    c.youtube_channel_title = "Test YT"
    c.youtube_connection_status = "connected"
    # Publishing now defaults OFF for new channels (safety); a channel that is
    # fully connected and ready to upload is one where the user has explicitly
    # enabled publishing. The upload endpoint gates on this flag.
    c.automatic_publishing_enabled = True
    db.commit()
    db.close()


def test_upload_job_mocked_success_and_errors(client, monkeypatch):
    import publications_api as pa

    ch, pid = _mk_rendered_project(client)
    _link_youtube(client, ch)
    pub = client.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(client)).get_json()["publication"]
    pub_id = pub["id"]

    # -- mocked success
    def fake_upload_ok(p_id):
        from database import SessionLocal
        from saas_models import Publication
        db = SessionLocal()
        p = db.query(Publication).filter_by(id=p_id).first()
        p.youtube_video_id = "MOCKvid0001"
        p.youtube_url = "https://www.youtube.com/shorts/MOCKvid0001"
        p.status = "published"
        p.published_at = datetime.utcnow()
        db.commit(); db.close()

    monkeypatch.setattr(pa, "run_upload_job", fake_upload_ok)
    r = client.post(f"/api/publications/{pub_id}/upload", headers=_h(client))
    assert r.status_code == 202
    got = client.get(f"/api/publications/{pub_id}", headers=_h(client)).get_json()["publication"]
    assert got["status"] == "published"
    assert got["youtube_video_id"] == "MOCKvid0001"

    # -- double upload protection after published
    assert client.post(f"/api/publications/{pub_id}/upload", headers=_h(client)).status_code == 409
    # retry after success forbidden
    assert client.post(f"/api/publications/{pub_id}/retry", headers=_h(client)).status_code == 409


def test_upload_job_quota_and_token_errors(client, monkeypatch):
    import publications_api as pa

    ch, pid = _mk_rendered_project(client)
    _link_youtube(client, ch)
    pub_id = client.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(client)).get_json()["publication"]["id"]

    # token refresh failure: no social account token -> honest failed status
    r = client.post(f"/api/publications/{pub_id}/upload", headers=_h(client))
    assert r.status_code == 202  # SYNC_JOBS runs inline; real job hits token check
    got = client.get(f"/api/publications/{pub_id}", headers=_h(client)).get_json()["publication"]
    assert got["status"] == "failed"
    assert "token" in (got["last_error"] or "").lower()
    assert got["attempts"] == 1

    # mocked quota error on retry
    def fake_quota(p_id):
        from database import SessionLocal
        from saas_models import Publication
        db = SessionLocal()
        p = db.query(Publication).filter_by(id=p_id).first()
        p.status = "failed"
        p.last_error = "quota_exceeded: The request cannot be completed (quotaExceeded)"
        db.commit(); db.close()

    monkeypatch.setattr(pa, "run_upload_job", fake_quota)
    r = client.post(f"/api/publications/{pub_id}/retry", headers=_h(client))
    assert r.status_code == 202
    got = client.get(f"/api/publications/{pub_id}", headers=_h(client)).get_json()["publication"]
    assert got["status"] == "failed"
    assert "quota" in got["last_error"].lower()


def test_anonymous_and_isolation(client):
    assert client.get("/api/publications").status_code == 401
    ch, pid = _mk_rendered_project(client)
    pub_id = client.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(client)).get_json()["publication"]["id"]
    # another allowlisted user cannot see it
    import os
    os.environ["ADMIN_ALLOWLIST_EMAILS"] = f"{ADMIN_EMAIL},other@test.local"
    import saas_settings
    importlib.reload(saas_settings)
    other_id = _seed_admin(email="other@test.local", role="user")
    other_token = _token_for(other_id)
    r = client.get(f"/api/publications/{pub_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert r.status_code in (403, 404)


def test_channel_youtube_status_no_tokens(client):
    ch = client.post("/api/channels", json={"name": "YT"}, headers=_h(client)).get_json()["channel"]["id"]
    r = client.get(f"/api/channels/{ch}/youtube/status", headers=_h(client))
    assert r.status_code == 200
    body = r.get_json()
    assert body["youtube_connection_status"] == "not_connected"
    assert "oauth_missing_vars" in body
    dumped = json.dumps(body).lower()
    assert "access_token" not in dumped and "refresh" not in dumped
    # available without account -> 409
    assert client.get(f"/api/channels/{ch}/youtube/available", headers=_h(client)).status_code == 409
