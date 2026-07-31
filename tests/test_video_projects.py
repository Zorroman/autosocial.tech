"""VideoProject / scenes / render queue tests (private mode).

Includes a real end-to-end render through the queue with SYNC_JOBS=true:
channel -> project -> script -> split scenes -> fixture media -> render job
-> real MP4 validated with ffprobe.
"""
import json
import subprocess

import pytest

from tests.test_private_admin import _fresh_app, _seed_admin, _token_for


@pytest.fixture()
def client(tmp_path):
    app_module = _fresh_app(tmp_path)
    admin_id = _seed_admin()
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)
        yield c


def _h(c):
    return {"Authorization": f"Bearer {c.admin_token}"}


def _mk_channel(c, name="Эзотерика"):
    r = c.post("/api/channels", json={"name": name, "niche": "эзотерика"}, headers=_h(c))
    assert r.status_code == 201
    return r.get_json()["channel"]["id"]


SCRIPT = (
    "Чёрная луна веками считалась знаком перемен. Её символ встречается в древних текстах. "
    "Алхимики связывали её с внутренней трансформацией. Сегодня этот образ живёт в культуре. "
    "Что скрывает этот символ? Смотрите до конца."
)


def _mk_project(c, channel_id, voice_mode="silent"):
    r = c.post(
        "/api/video-projects",
        json={"channel_id": channel_id, "title": "Символ чёрной луны", "script_text": SCRIPT, "voice_mode": voice_mode},
        headers=_h(c),
    )
    assert r.status_code == 201
    return r.get_json()["project"]["id"]


def test_project_crud_and_scene_split(client):
    ch = _mk_channel(client)
    pid = _mk_project(client, ch)

    got = client.get(f"/api/video-projects/{pid}", headers=_h(client))
    assert got.status_code == 200
    assert got.get_json()["project"]["voice_mode"] == "silent"

    split = client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client))
    assert split.status_code == 201
    scenes = split.get_json()["scenes"]
    assert len(scenes) >= 2
    assert all(s["voiceover_text"] for s in scenes)

    # split refuses to overwrite without replace
    again = client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client))
    assert again.status_code == 409
    replaced = client.post(f"/api/video-projects/{pid}/split-scenes", json={"replace": True}, headers=_h(client))
    assert replaced.status_code == 201

    # scene CRUD
    sid = replaced.get_json()["scenes"][0]["id"]
    upd = client.patch(f"/api/scenes/{sid}", json={"on_screen_text": "Знак перемен", "estimated_duration": 3.5}, headers=_h(client))
    assert upd.status_code == 200
    assert upd.get_json()["scene"]["estimated_duration"] == 3.5

    bad = client.patch(f"/api/scenes/{sid}", json={"estimated_duration": 999}, headers=_h(client))
    assert bad.status_code == 400

    path_attack = client.patch(f"/api/scenes/{sid}", json={"selected_media_path": "/etc/passwd"}, headers=_h(client))
    assert path_attack.status_code == 400

    added = client.post(f"/api/video-projects/{pid}/scenes", json={"voiceover_text": "Финал"}, headers=_h(client))
    assert added.status_code == 201
    new_sid = added.get_json()["scene"]["id"]
    assert client.delete(f"/api/scenes/{new_sid}", headers=_h(client)).status_code == 200


def test_render_requires_scene_media(client):
    ch = _mk_channel(client)
    pid = _mk_project(client, ch)
    client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client))
    # SYNC_JOBS=true: render runs inline and must fail honestly (no media attached)
    r = client.post(f"/api/video-projects/{pid}/render", headers=_h(client))
    assert r.status_code == 202
    job_id = r.get_json()["job"]["id"]
    j = client.get(f"/api/render-jobs/{job_id}", headers=_h(client)).get_json()["job"]
    assert j["status"] == "failed"
    assert "scenes_missing_media" in (j["error"] or "")
    assert j["attempts"] == 1

    # retry allowed for failed job below max_attempts
    rr = client.post(f"/api/render-jobs/{job_id}/retry", headers=_h(client))
    assert rr.status_code == 202


def test_cancel_only_pending(client):
    ch = _mk_channel(client)
    pid = _mk_project(client, ch)
    client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client))
    r = client.post(f"/api/video-projects/{pid}/render", headers=_h(client))
    job_id = r.get_json()["job"]["id"]
    # job already failed (sync) -> cancel must refuse
    cancel = client.post(f"/api/render-jobs/{job_id}/cancel", headers=_h(client))
    assert cancel.status_code == 409


def test_duplicate_render_protection(client, monkeypatch):
    ch = _mk_channel(client)
    pid = _mk_project(client, ch)
    client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client))
    import video_projects_api as vpa
    monkeypatch.setattr(vpa, "_enqueue_render", lambda job_id: "noop")  # leave job pending
    first = client.post(f"/api/video-projects/{pid}/render", headers=_h(client))
    assert first.status_code == 202
    second = client.post(f"/api/video-projects/{pid}/render", headers=_h(client))
    assert second.status_code == 409
    # cancel the pending job
    job_id = first.get_json()["job"]["id"]
    cancel = client.post(f"/api/render-jobs/{job_id}/cancel", headers=_h(client))
    assert cancel.status_code == 200
    assert cancel.get_json()["job"]["status"] == "cancelled"


def test_full_e2e_render_real_mp4(client):
    from app_settings import settings

    ch = _mk_channel(client)
    pid = _mk_project(client, ch, voice_mode="silent")
    split = client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client))
    scenes = split.get_json()["scenes"]

    for s in scenes:
        fm = client.post(f"/api/scenes/{s['id']}/fixture-media", headers=_h(client))
        assert fm.status_code == 200
        assert fm.get_json()["scene"]["visual_type"] == "fixture"

    r = client.post(f"/api/video-projects/{pid}/render", headers=_h(client))
    assert r.status_code == 202
    job_id = r.get_json()["job"]["id"]
    job = client.get(f"/api/render-jobs/{job_id}", headers=_h(client)).get_json()["job"]
    assert job["status"] == "completed", f"render failed: {job['error']}"
    assert job["progress"] == 100
    assert job["output_path"]
    assert job["started_at"] and job["finished_at"]

    out = settings.BASE_DIR / job["output_path"]
    assert out.exists() and out.stat().st_size > 50_000

    probe = subprocess.run(
        [settings.FFPROBE_BIN, "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(out)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(probe.stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert v["codec_name"] == "h264" and (v["width"], v["height"]) == (1080, 1920)
    assert a["codec_name"] == "aac"
    assert float(info["format"]["duration"]) > 5.0

    # download through the API media route
    dl = client.get(f"/api/media/{job['output_path']}", headers=_h(client))
    assert dl.status_code == 200
    assert len(dl.data) == out.stat().st_size

    proj = client.get(f"/api/video-projects/{pid}", headers=_h(client)).get_json()["project"]
    assert proj["status"] == "rendered"
    assert proj["output_url"] == f"/api/media/{job['output_path']}"


def test_output_url_is_null_when_rendered_file_is_missing(client):
    """A project can carry output_path while the file is gone (cleanup, restored
    DB, failed render). The API must not hand the UI a URL then, otherwise the
    details page shows an empty <video> and a dead Download link."""
    from database import SessionLocal
    from app_models import VideoProject

    ch = _mk_channel(client)
    pid = _mk_project(client, ch)
    db = SessionLocal()
    try:
        p = db.query(VideoProject).filter_by(id=pid).first()
        p.output_path = "output/definitely_missing_file.mp4"
        db.commit()
    finally:
        db.close()

    got = client.get(f"/api/video-projects/{pid}", headers=_h(client)).get_json()["project"]
    assert got["output_path"] == "output/definitely_missing_file.mp4"
    assert got["output_url"] is None
