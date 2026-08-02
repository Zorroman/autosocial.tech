"""OpenAI quota/billing safety net.

Scope: detecting quota/billing errors specifically (not ordinary timeouts or
rate limits), Telegram alerting with a durable cooldown, Shorts falling back
without repeating the old templated opener, and long-form blocking instead
of publishing a low-quality fallback. Scheduler, media selection, TTS,
subtitles, music, CTA, render, and YouTube upload are untouched -- see
test_factory_pipeline_e2e.py and test_shorts_hook_diversity.py for proof
those still pass unchanged.
"""
import httpx
import openai as openai_sdk
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


def _mk_project(c, channel_id, title, duration=30):
    # Project creation ignores a duration in the request body -- it always
    # inherits the channel's default_video_duration_seconds (see
    # video_projects_api.py:245) -- so set that first.
    c.patch(f"/api/channels/{channel_id}", json={"default_video_duration_seconds": duration}, headers=_h(c))
    r = c.post("/api/video-projects", json={"channel_id": channel_id, "title": title}, headers=_h(c))
    assert r.status_code == 201
    return r.get_json()["project"]["id"]


def _mk_status_error(cls, status_code: int, code: str, err_type: str, message: str):
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    resp = httpx.Response(status_code, request=req)
    return cls(message, response=resp, body={"code": code, "type": err_type, "message": message})


def _mk_timeout_error():
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai_sdk.APITimeoutError(request=req)


# --------------------------------------------------------- 1+2. classification

def test_insufficient_quota_is_recognized_as_billing_error():
    from openai_quota_guard import classify_openai_error
    exc = _mk_status_error(openai_sdk.RateLimitError, 429, "insufficient_quota",
                           "insufficient_quota", "You exceeded your current quota")
    assert classify_openai_error(exc) == "quota_billing"


def test_billing_hard_limit_and_account_deactivated_are_billing_errors():
    from openai_quota_guard import classify_openai_error
    hard_limit = _mk_status_error(openai_sdk.RateLimitError, 429, "billing_hard_limit_reached",
                                  "billing_hard_limit_reached", "Billing hard limit reached")
    deactivated = _mk_status_error(openai_sdk.PermissionDeniedError, 403, "account_deactivated",
                                   "account_deactivated", "Your account has been deactivated")
    assert classify_openai_error(hard_limit) == "quota_billing"
    assert classify_openai_error(deactivated) == "quota_billing"


def test_ordinary_timeout_is_not_a_billing_error():
    from openai_quota_guard import classify_openai_error
    assert classify_openai_error(_mk_timeout_error()) == "timeout"


def test_ordinary_rate_limit_is_not_a_billing_error():
    from openai_quota_guard import classify_openai_error
    exc = _mk_status_error(openai_sdk.RateLimitError, 429, "rate_limit_exceeded",
                           "requests", "Rate limit reached for requests")
    assert classify_openai_error(exc) == "rate_limit"


# ------------------------------------------------------- 3+4. Shorts fallback

def test_shorts_switches_to_diverse_fallback_on_quota_error(monkeypatch):
    import video_script_generator as vsg
    from shorts_hook_diversity import is_templated_hook

    monkeypatch.setattr(vsg, "is_openai_enabled", lambda: True)

    def fake_generate(**kwargs):
        raise vsg.OpenAIClientError("quota exceeded", error_class="quota_billing")

    monkeypatch.setattr(vsg, "generate_json_with_retry", fake_generate)

    bundle = vsg.generate(topic="Счастливые числа", offer=None, language="ru",
                          target_seconds=30, style="")
    assert bundle.used_fallback is True
    assert bundle.openai_error_class == "quota_billing"
    assert not is_templated_hook(bundle.phrases[0])
    assert "Сегодня коротко и понятно" not in bundle.phrases[0]


# --------------------------------------------------- 5. long-form not published via fallback

def test_longform_blocks_instead_of_publishing_weak_fallback(monkeypatch):
    import openai_client
    import video_script_generator as vsg

    monkeypatch.setattr(vsg, "is_openai_enabled", lambda: True)

    def fake_generate(**kwargs):
        raise vsg.OpenAIClientError("quota exceeded", error_class="quota_billing")

    # _generate_longform does its own `from openai_client import
    # generate_json_with_retry` at call time, bypassing a patch on
    # video_script_generator's module-level name -- patch the real source.
    monkeypatch.setattr(openai_client, "generate_json_with_retry", fake_generate)

    with pytest.raises(vsg.LongformProviderBlockedError):
        vsg.generate(topic="Медитация", offer=None, language="ru", target_seconds=600, style="спокойный")


def test_longform_endpoint_returns_blocked_status(client, monkeypatch):
    import openai_client
    import video_script_generator as vsg

    monkeypatch.setattr(vsg, "is_openai_enabled", lambda: True)
    monkeypatch.setattr(openai_client, "generate_json_with_retry",
                        lambda **kwargs: (_ for _ in ()).throw(
                            vsg.OpenAIClientError("quota exceeded", error_class="quota_billing")))

    ch = _mk_channel(client)
    pid = _mk_project(client, ch, "Медитация", duration=600)
    r = client.post(f"/api/video-projects/{pid}/generate-script", json={}, headers=_h(client))
    assert r.status_code == 503
    assert r.get_json()["pipeline_state"] == "blocked_external_provider"

    # _project_dict doesn't expose pipeline_state (only /pipeline/state does,
    # pre-existing and out of scope here) -- verify persistence via the DB.
    from app_models import VideoProject
    from database import SessionLocal
    db = SessionLocal()
    try:
        row = db.get(VideoProject, pid)
        assert row.pipeline_state == "blocked_external_provider"
    finally:
        db.close()


def test_longform_survives_non_quota_failure_via_existing_fallback(monkeypatch):
    """Preserves existing (pre-this-fix) behavior: a non-billing long-form
    failure still falls through to the standard path rather than blocking --
    only quota/billing blocks, per spec."""
    import openai_client
    import video_script_generator as vsg

    monkeypatch.setattr(vsg, "is_openai_enabled", lambda: True)
    monkeypatch.setattr(openai_client, "generate_json_with_retry",
                        lambda **kwargs: (_ for _ in ()).throw(
                            vsg.OpenAIClientError("weird transient error", error_class="other")))

    bundle = vsg.generate(topic="Медитация", offer=None, language="ru", target_seconds=600, style="спокойный")
    assert bundle.used_fallback is True  # degraded, but not blocked


# ------------------------------------------------------------ 6+7. Telegram alert + cooldown

def test_telegram_alert_sent_once_and_cooldown_prevents_spam(client, monkeypatch):
    import openai_quota_guard as qg

    sent = []
    monkeypatch.setattr(qg, "send_telegram_alert", lambda text: sent.append(text) or True)

    from database import SessionLocal
    db = SessionLocal()
    try:
        ok1 = qg.handle_quota_event(db, stage="script", project_id=1, channel_name="Test",
                                    error_class="quota_billing", fallback_target="Shorts fallback")
        ok2 = qg.handle_quota_event(db, stage="script", project_id=2, channel_name="Test",
                                    error_class="quota_billing", fallback_target="Shorts fallback")
        assert ok1 is True
        assert ok2 is False  # cooldown -- no second Telegram send
        assert len(sent) == 1
        assert "OpenAI quota/billing exhausted" in sent[0]
    finally:
        db.close()


def test_cooldown_expires_after_six_hours(client, monkeypatch):
    import openai_quota_guard as qg
    from app_models import SystemLog
    from database import SessionLocal
    from datetime import datetime, timedelta

    sent = []
    monkeypatch.setattr(qg, "send_telegram_alert", lambda text: sent.append(text) or True)

    db = SessionLocal()
    try:
        db.add(SystemLog(level="warning", message=qg._ALERT_SENT_MARKER,
                         context="{}", created_at=datetime.utcnow() - timedelta(hours=7)))
        db.commit()
        ok = qg.handle_quota_event(db, stage="script", project_id=1, channel_name="Test",
                                   error_class="quota_billing", fallback_target="Shorts fallback")
        assert ok is True
        assert len(sent) == 1
    finally:
        db.close()


def test_telegram_alert_never_leaks_secrets():
    import openai_quota_guard as qg
    text = qg.format_quota_alert(stage="script", project_id=5, channel_name="Test Channel",
                                 error_class="quota_billing", fallback_target="Shorts fallback")
    assert "sk-" not in text
    assert "Authorization" not in text
    assert "api_key" not in text.lower()


# --------------------------------------------------------------- 8+9. recovery

def test_recovery_alert_sent_once_after_being_in_fallback(client, monkeypatch):
    import openai_quota_guard as qg

    sent = []
    monkeypatch.setattr(qg, "send_telegram_alert", lambda text: sent.append(text) or True)

    from database import SessionLocal
    db = SessionLocal()
    try:
        # not in fallback mode yet -- recovery is a no-op
        assert qg.handle_recovery_event(db) is False
        assert sent == []

        qg.handle_quota_event(db, stage="script", project_id=1, channel_name="Test",
                              error_class="quota_billing", fallback_target="Shorts fallback")
        assert qg.is_in_fallback_mode(db) is True
        assert len(sent) == 1  # the quota alert

        assert qg.handle_recovery_event(db) is True
        assert len(sent) == 2  # exactly one NEW message: the recovery alert
        assert "OpenAI access restored" in sent[1]
        assert qg.is_in_fallback_mode(db) is False

        # calling again after recovery is a no-op -- no further messages
        assert qg.handle_recovery_event(db) is False
        assert len(sent) == 2
    finally:
        db.close()


def test_after_recovery_normal_openai_path_is_used(monkeypatch):
    import video_script_generator as vsg

    monkeypatch.setattr(vsg, "is_openai_enabled", lambda: True)

    def fake_generate(system_prompt, user_prompt, validator, max_output_tokens, temperature):
        payload = {
            "phrases": ["Одно число может преследовать вас не случайно."] +
                       [f"Фраза номер {i} длинного связного повествования по теме." for i in range(2, 6)],
            "shotlist": [], "title": "t", "description": "d", "hashtags": [], "safety_rules": [],
        }
        validator(payload)

        class _R:
            pass
        r = _R()
        r.payload = payload
        return r

    monkeypatch.setattr(vsg, "generate_json_with_retry", fake_generate)
    bundle = vsg.generate(topic="Числа", offer=None, language="ru", target_seconds=30, style="")
    assert bundle.used_fallback is False
    assert bundle.openai_error_class is None


# ----------------------------------------------------- 10. no catch-up batch

def test_recovery_does_not_touch_scheduler_or_create_projects(client, monkeypatch):
    """handle_recovery_event only sends a message and writes one SystemLog
    row -- it must never create/queue/touch any VideoProject."""
    import openai_quota_guard as qg
    from app_models import VideoProject
    from database import SessionLocal

    monkeypatch.setattr(qg, "send_telegram_alert", lambda text: True)

    db = SessionLocal()
    try:
        before = db.query(VideoProject).count()
        qg.handle_quota_event(db, stage="script", project_id=1, channel_name="Test",
                              error_class="quota_billing", fallback_target="Shorts fallback")
        qg.handle_recovery_event(db)
        after = db.query(VideoProject).count()
        assert after == before
    finally:
        db.close()


# ------------------------------------------------------- observability counters

def test_counters_track_named_events_only(monkeypatch):
    import openai_quota_guard as qg

    for name in qg._COUNTER_NAMES:
        qg._counters[name] = 0  # isolate from other tests in the same process

    qg.record_event("openai_success")
    qg.record_event("openai_quota_error")
    qg.record_event("not_a_real_counter")  # must be silently ignored, no KeyError

    counters = qg.get_counters()
    assert counters["openai_success"] == 1
    assert counters["openai_quota_error"] == 1
    assert "not_a_real_counter" not in counters
    assert set(counters.keys()) == set(qg._COUNTER_NAMES)


# --------------------------------------------------- Telegram not configured (honest degrade)

def test_telegram_not_configured_logs_instead_of_crashing(monkeypatch):
    import openai_quota_guard as qg
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert qg.send_telegram_alert("test message") is False  # no exception, honest False
