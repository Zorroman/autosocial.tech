"""Full automatic Content Factory pipeline, driven by a single action.

script -> checkpoint -> scenes -> media -> render -> AI Publisher, triggered
by one call to pipeline/approve -- no manual per-scene fixture-media calls.

factory_pipeline drives its stations over HTTP (real sockets between the
worker and backend containers in production). In-process here, that HTTP
layer is monkeypatched to dispatch straight into the Flask test client
instead of a real socket -- avoids both spinning up a live threaded server
and a cross-thread SQLite lock hang that a real live-server would hit against
a single sqlite file, while still exercising the real orchestration logic and
the real station endpoint handlers underneath it.
"""
import json
import subprocess

import pytest

from tests.test_private_admin import _fresh_app, _seed_admin, _token_for

SCRIPT = (
    "Чёрная луна веками считалась знаком перемен. Её символ встречается в древних текстах. "
    "Алхимики связывали её с внутренней трансформацией. Сегодня этот образ живёт в культуре. "
    "Что скрывает этот символ? Смотрите до конца."
)


class _FakeResponse:
    def __init__(self, flask_resp):
        self.status_code = flask_resp.status_code
        self._flask_resp = flask_resp

    def json(self):
        return self._flask_resp.get_json()

    @property
    def text(self):
        return self._flask_resp.get_data(as_text=True)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path)
    admin_id = _seed_admin()
    # Two separate test-client instances: the Flask test client is not meant
    # to be called re-entrantly on the same instance from within a request it
    # is still handling (corrupts its context-local bookkeeping -- observed
    # directly as a LookupError on flask.request_ctx on the next call). The
    # station calls factory_pipeline makes while pipeline/approve is still
    # running get their own, separate, plain (non-`with`) client -- `with
    # app.test_client() as x` preserves each response's request context for
    # post-call inspection, which stacks up incorrectly across the several
    # sequential nested calls the orchestrator makes and eventually pops the
    # wrong one.
    nested_c = app_module.app.test_client()
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)

        import factory_pipeline

        def _patched_post(url, headers=None, json=None, timeout=None):  # noqa: A002
            path = url.split("/api", 1)[1]
            return _FakeResponse(nested_c.post(f"/api{path}", headers=headers, json=json or {}))

        monkeypatch.setattr(factory_pipeline.requests, "post", _patched_post)
        yield c


def _h(c):
    return {"Authorization": f"Bearer {c.admin_token}"}


def test_full_automatic_pipeline_completes_with_mock_fixtures(client):
    c = client
    r = c.post("/api/channels", json={"name": "Эзотерика", "niche": "эзотерика"}, headers=_h(c))
    assert r.status_code == 201
    channel_id = r.get_json()["channel"]["id"]

    r = c.post(
        "/api/video-projects",
        json={"channel_id": channel_id, "title": "Символ чёрной луны", "script_text": SCRIPT, "voice_mode": "silent"},
        headers=_h(c),
    )
    assert r.status_code == 201
    pid = r.get_json()["project"]["id"]

    r = c.post(f"/api/video-projects/{pid}/pipeline/approve", headers=_h(c))
    assert r.status_code == 202
    assert r.get_json()["queue_mode"] == "sync"

    state = c.get(f"/api/video-projects/{pid}/pipeline/state", headers=_h(c)).get_json()
    assert state["pipeline_error"] is None, state["pipeline_error"]
    stages = {s["key"]: s["state"] for s in state["stages"]}
    assert stages["script"] == "done"
    assert stages["scenes"] == "done"
    assert stages["media"] == "done"
    assert stages["render"] == "done"

    render_job = state["render_job"]
    assert render_job["status"] == "completed", render_job
    assert render_job["output_path"]

    # auto-media must have picked fixtures automatically -- nothing in this
    # test manually assigns media to any scene.
    proj = c.get(f"/api/video-projects/{pid}", headers=_h(c)).get_json()["project"]
    assert proj["scenes"], "expected scenes to exist"
    for s in proj["scenes"]:
        assert s["visual_type"] == "fixture", s

    from app_settings import settings
    out = settings.BASE_DIR / render_job["output_path"]
    assert out.exists() and out.stat().st_size > 50_000
    probe = subprocess.run(
        [settings.FFPROBE_BIN, "-v", "quiet", "-print_format", "json", "-show_streams", str(out)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(probe.stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert v["codec_name"] == "h264"
    assert a["codec_name"] == "aac"


def test_auto_media_requires_pexels_key_when_not_mocked(client, monkeypatch):
    """USE_MOCK_PROVIDERS=false must never silently substitute fixtures for
    real stock media -- a missing PEXELS_API_KEY stays a clear config error."""
    c = client
    monkeypatch.setattr("app_settings.settings.USE_MOCK_PROVIDERS", False)
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)

    r = c.post("/api/channels", json={"name": "Real channel", "niche": "real"}, headers=_h(c))
    channel_id = r.get_json()["channel"]["id"]
    r = c.post(
        "/api/video-projects",
        json={"channel_id": channel_id, "title": "Real project", "script_text": SCRIPT},
        headers=_h(c),
    )
    pid = r.get_json()["project"]["id"]
    c.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(c))

    r = c.post(f"/api/video-projects/{pid}/auto-media", headers=_h(c))
    assert r.status_code == 503
    assert "PEXELS_API_KEY" in r.get_json()["error"]
