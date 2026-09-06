"""TTS provider/voice consistency within a single video.

Root cause of the reported "странный голос" (voice sounds off partway
through): video/tts.py picked a TTS provider independently per phrase, so a
single transient edge_tts hiccup on just one phrase silently produced that
one phrase in OpenAI's voice instead, while the rest of the video stayed on
edge's Russian neural voice -- an audible, jarring voice switch mid-video.

Fix, verified here: the provider is chosen once for the whole video. A
single-phrase failure retries the SAME provider (bounded) rather than
switching; only a provider that fails persistently across the whole video
triggers a full re-synthesis of every phrase on the fallback provider (never
a partial mix). If both providers are unavailable, synthesize_voiceover
raises TTSProviderUnavailableError instead of producing silent/flite audio
(flite isn't installed in production and was a silent-failure path).
"""
import json
import subprocess

import pytest

from tests.test_private_admin import _fresh_app, _seed_admin, _token_for


def _write_tiny_mp3(path):
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=0.5",
            "-q:a", "9", "-acodec", "libmp3lame", str(path),
        ],
        check=True, capture_output=True,
    )


@pytest.fixture()
def tts_module(monkeypatch):
    import video.tts as tts
    monkeypatch.setattr(tts.settings, "FFMPEG_BIN", "ffmpeg")
    monkeypatch.setattr(tts.settings, "FFPROBE_BIN", "ffprobe")
    return tts


PHRASES = ["Первая фраза сценария.", "Вторая фраза сценария.", "Третья фраза сценария.",
          "Четвёртая фраза сценария.", "Пятая фраза сценария."]


# --------------------------------------------------- 1. single provider for whole video

def test_all_phrases_use_same_provider_when_primary_succeeds(tts_module, tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_TTS_PRIMARY", "edge")
    calls = {"edge": 0, "openai": 0}

    def fake_edge(text, out_path, **kw):
        calls["edge"] += 1
        _write_tiny_mp3(out_path)

    def fake_openai(text, out_path, **kw):
        calls["openai"] += 1
        raise RuntimeError("must not be called -- edge is healthy")

    monkeypatch.setattr(tts_module, "_tts_phrase_edge", fake_edge)
    monkeypatch.setattr(tts_module, "_tts_phrase_openai", fake_openai)

    voice_str, durations = tts_module.synthesize_voiceover(PHRASES, tmp_path, "p")

    assert calls["edge"] == len(PHRASES)
    assert calls["openai"] == 0
    log = json.loads((tmp_path / "p_tts_log.json").read_text())
    assert len(log) == len(PHRASES)
    assert {entry["provider"] for entry in log} == {"edge"}
    assert all(entry["fallback_reason"] is None for entry in log)


# --------------------------------------------- 2. retry same provider, no silent switch

def test_transient_single_phrase_failure_retries_same_provider(tts_module, tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_TTS_PRIMARY", "edge")
    edge_calls = {"n": 0}

    def flaky_edge(text, out_path, **kw):
        edge_calls["n"] += 1
        # Fail once on phrase index 2 (3rd phrase), succeed every other call.
        if "Третья" in text and edge_calls["n"] < 10:
            # only fail the FIRST attempt at this specific phrase
            if not getattr(flaky_edge, "_phrase3_failed_once", False):
                flaky_edge._phrase3_failed_once = True
                raise RuntimeError("transient edge_tts hiccup")
        _write_tiny_mp3(out_path)

    def fake_openai(text, out_path, **kw):
        raise RuntimeError("must not be called -- edge recovers on retry")

    monkeypatch.setattr(tts_module, "_tts_phrase_edge", flaky_edge)
    monkeypatch.setattr(tts_module, "_tts_phrase_openai", fake_openai)

    voice_str, durations = tts_module.synthesize_voiceover(PHRASES, tmp_path, "p")

    log = json.loads((tmp_path / "p_tts_log.json").read_text())
    assert {entry["provider"] for entry in log} == {"edge"}  # never switched


# ------------------------------------------- 3. whole-project switch, never a partial mix

def test_persistent_primary_failure_switches_whole_video_not_partial(tts_module, tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_TTS_PRIMARY", "edge")
    openai_calls = []

    def always_fail_edge(text, out_path, **kw):
        raise RuntimeError("edge_tts is down")

    def fake_openai(text, out_path, **kw):
        openai_calls.append(text)
        _write_tiny_mp3(out_path)

    monkeypatch.setattr(tts_module, "_tts_phrase_edge", always_fail_edge)
    monkeypatch.setattr(tts_module, "_tts_phrase_openai", fake_openai)

    voice_str, durations = tts_module.synthesize_voiceover(PHRASES, tmp_path, "p")

    assert len(openai_calls) == len(PHRASES)  # ALL phrases redone on fallback
    log = json.loads((tmp_path / "p_tts_log.json").read_text())
    assert {entry["provider"] for entry in log} == {"openai"}  # no mixing
    assert all(entry["fallback_reason"] for entry in log)


# ------------------------------------------------- 4. no silent/flite fallback, blocks instead

def test_both_providers_down_raises_instead_of_silent_audio(tts_module, tmp_path, monkeypatch):
    def always_fail(text, out_path, **kw):
        raise RuntimeError("provider down")

    monkeypatch.setattr(tts_module, "_tts_phrase_edge", always_fail)
    monkeypatch.setattr(tts_module, "_tts_phrase_openai", always_fail)

    with pytest.raises(tts_module.TTSProviderUnavailableError):
        tts_module.synthesize_voiceover(PHRASES, tmp_path, "p")

    # no partial phrase files or silent-audio artifacts left behind to be
    # accidentally picked up by a later step
    assert not list(tmp_path.glob("p_voiceover*.mp3"))


def test_flite_is_not_a_hidden_fallback_path(tts_module):
    assert not hasattr(tts_module, "_tts_phrase_fallback")


# --------------------------------------------------------- 5. diagnostic table shape

def test_tts_log_has_required_columns_for_diagnosis(tts_module, tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_TTS_PRIMARY", "edge")
    monkeypatch.setattr(tts_module, "_tts_phrase_edge",
                        lambda text, out_path, **kw: _write_tiny_mp3(out_path))
    monkeypatch.setattr(tts_module, "_tts_phrase_openai",
                        lambda text, out_path, **kw: (_ for _ in ()).throw(RuntimeError()))

    tts_module.synthesize_voiceover(PHRASES, tmp_path, "p")
    log = json.loads((tmp_path / "p_tts_log.json").read_text())
    required = {"phrase_index", "text_start", "provider", "voice", "duration", "fallback_reason"}
    for entry in log:
        assert required <= set(entry.keys())
    assert [e["phrase_index"] for e in log] == list(range(len(PHRASES)))
    assert log[2]["text_start"].startswith("Третья")


# ------------------------ long-form: blocked status, not a silent crash

@pytest.fixture()
def client(tmp_path):
    app_module = _fresh_app(tmp_path)
    admin_id = _seed_admin()
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)
        yield c


def _h(c):
    return {"Authorization": f"Bearer {c.admin_token}"}


def test_longform_render_blocks_with_clear_status_when_both_tts_providers_down(client, monkeypatch):
    """render_and_publish() must never let a TTSProviderUnavailableError from
    inside longform_pipeline.run() propagate uncaught -- that would crash the
    RQ job silently, leaving pipeline_state stale instead of a clear blocked
    status (the exact 'тишина' the fix is meant to prevent)."""
    r = client.post("/api/channels", json={"name": "LF", "niche": "test"}, headers=_h(client))
    ch = r.get_json()["channel"]["id"]
    r = client.post("/api/video-projects", json={"channel_id": ch, "title": "Long-form TTS test"},
                    headers=_h(client))
    pid = r.get_json()["project"]["id"]

    import longform_job
    import longform_pipeline
    from video.tts import TTSProviderUnavailableError

    def fake_run(project_id, job_root=None):
        raise TTSProviderUnavailableError("both TTS providers unavailable (edge: x; openai: y)")

    monkeypatch.setattr(longform_pipeline, "run", fake_run)

    result = longform_job.render_and_publish(pid)
    assert result["published"] is False
    assert result["reason"] == "tts_provider_unavailable"

    from database import SessionLocal
    from app_models import VideoProject
    db = SessionLocal()
    try:
        p = db.get(VideoProject, pid)
        assert p.pipeline_state == "blocked_external_provider"
        assert "TTS blocked" in (p.pipeline_error or "")
    finally:
        db.close()


# --------------------------------------------------- calm tone -> slower native speed

def test_calm_tone_uses_slower_openai_speed(tts_module, tmp_path, monkeypatch):
    """Root cause of 'голос не спокойный': voice_tone was never actually
    passed at either Shorts or long-form call sites, so it silently defaulted
    to neutral even though a calm profile already existed in the code. This
    checks the fix at the level that actually reaches the API: a native
    `speed` argument, which shapes real generated pacing rather than
    stretching it after the fact."""
    captured = {}

    class _FakeStreamingResponse:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream_to_file(self, path):
            _write_tiny_mp3(path)

    class _FakeSpeech:
        with_streaming_response = type(
            "R", (), {"create": staticmethod(lambda **kw: _FakeStreamingResponse(**kw))})()

    class _FakeAudio:
        speech = _FakeSpeech()

    class _FakeClient:
        def __init__(self, *a, **kw):
            self.audio = _FakeAudio()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(tts_module, "OpenAI", _FakeClient)

    out_path = tmp_path / "phrase.mp3"
    tts_module._tts_phrase_openai("Спокойный текст.", out_path, voice_tone="calm")
    assert captured["speed"] == pytest.approx(0.92)

    captured.clear()
    tts_module._tts_phrase_openai("Обычный текст.", out_path, voice_tone="neutral")
    assert captured["speed"] == pytest.approx(1.0)


def test_shorts_and_longform_call_sites_pass_calm_tone():
    """The actual root cause: voice_tone existed in the code but was never
    passed at either real call site, so it silently defaulted to neutral."""
    import inspect
    import video_projects_api
    import longform_pipeline

    src1 = inspect.getsource(video_projects_api)
    src2 = inspect.getsource(longform_pipeline)
    assert 'voice_tone="calm"' in src1
    assert 'voice_tone="calm"' in src2


def test_shorts_use_the_same_narrator_voice_as_longform():
    """By explicit request: Shorts must sound like the same narrator as
    long-form, unconditionally -- even overriding a channel's own explicit
    default_voice setting (confirmed: channel 1 already had one set to an
    edge_tts voice, and the request was to override it too, not just fill in
    the unset case)."""
    import inspect
    import video_projects_api
    import longform_pipeline

    src1 = inspect.getsource(video_projects_api)
    src2 = inspect.getsource(longform_pipeline)
    assert 'voice_name="onyx"' in src1
    assert 'voice_name="onyx"' in src2
    # The old per-channel override must no longer decide the Shorts voice.
    assert "voice_name=(_ch or Channel()).default_voice or None" not in src1
