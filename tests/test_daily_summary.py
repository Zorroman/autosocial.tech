"""Daily Telegram summary of published videos.

Scope: counting today's published Shorts/long-form and sending at most one
Telegram message per calendar day, after the configured hour. Doesn't touch
the scheduler, render, or publish logic -- it only reads already-published
Publication rows.
"""
from datetime import datetime, timedelta

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


def _mk_published(db, channel_id, project_id_seed, duration_target, when):
    from app_models import VideoProject, Publication
    p = VideoProject(channel_id=channel_id, title=f"P{project_id_seed}", status="rendered",
                     duration_target_seconds=duration_target)
    db.add(p)
    db.flush()
    pub = Publication(channel_id=channel_id, project_id=p.id, title=p.title,
                      status="published", privacy_status="public", publish_mode="immediate",
                      youtube_video_id=f"vid{project_id_seed}", youtube_url="https://x",
                      published_at=when)
    db.add(pub)
    db.commit()
    return p.id


def test_counts_split_shorts_and_longform(client):
    from database import SessionLocal
    import daily_summary as ds

    r = client.post("/api/channels", json={"name": "C", "niche": "test"}, headers=_h(client))
    ch = r.get_json()["channel"]["id"]

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        _mk_published(db, ch, 1, 30, now)
        _mk_published(db, ch, 2, 45, now)
        _mk_published(db, ch, 3, 720, now)
        counts = ds.counts_for_today(db, now)
        assert counts == {"shorts": 2, "longform": 1, "total": 3}
    finally:
        db.close()


def test_counts_exclude_other_days_and_unpublished(client):
    from database import SessionLocal
    from app_models import VideoProject, Publication
    import daily_summary as ds

    r = client.post("/api/channels", json={"name": "C", "niche": "test"}, headers=_h(client))
    ch = r.get_json()["channel"]["id"]

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        _mk_published(db, ch, 1, 30, now)  # today, published -- counts
        _mk_published(db, ch, 2, 30, now - timedelta(days=1))  # yesterday -- excluded

        p3 = VideoProject(channel_id=ch, title="unpublished", status="draft", duration_target_seconds=30)
        db.add(p3)
        db.flush()
        db.add(Publication(channel_id=ch, project_id=p3.id, title="unpublished",
                           status="pending", privacy_status="public", publish_mode="immediate"))
        db.commit()

        counts = ds.counts_for_today(db, now)
        assert counts == {"shorts": 1, "longform": 0, "total": 1}
    finally:
        db.close()


def test_format_summary_shape():
    import daily_summary as ds
    now = datetime(2026, 8, 5, 20, 0, 0)
    text = ds.format_summary({"shorts": 5, "longform": 1, "total": 6}, now)
    assert "2026-08-05" in text
    assert "5" in text and "1" in text and "6" in text


def test_does_not_send_before_configured_hour(monkeypatch):
    import daily_summary as ds
    monkeypatch.setenv("DAILY_SUMMARY_HOUR", "18")
    sent = []
    monkeypatch.setattr("openai_quota_guard.send_telegram_alert", lambda text: sent.append(text) or True)
    early = datetime(2026, 8, 5, 10, 0, 0)
    assert ds.maybe_send_daily_summary(early) is False
    assert sent == []


def test_sends_once_after_hour_then_marker_prevents_resend(client, monkeypatch):
    import daily_summary as ds
    monkeypatch.setenv("DAILY_SUMMARY_HOUR", "18")
    sent = []
    monkeypatch.setattr("openai_quota_guard.send_telegram_alert", lambda text: sent.append(text) or True)

    evening = datetime.utcnow().replace(hour=19, minute=0, second=0, microsecond=0)
    ok1 = ds.maybe_send_daily_summary(evening)
    assert ok1 is True
    assert len(sent) == 1

    ok2 = ds.maybe_send_daily_summary(evening.replace(hour=21))
    assert ok2 is False
    assert len(sent) == 1  # no second message the same day


def test_disabled_via_env_var_never_fires_in_loop(monkeypatch):
    import daily_summary as ds
    monkeypatch.setenv("DAILY_SUMMARY_ENABLED", "false")
    assert ds._enabled() is False


def test_format_summary_includes_subscribers_with_delta():
    import daily_summary as ds
    now = datetime(2026, 8, 5, 20, 0, 0)
    text = ds.format_summary({"shorts": 1, "longform": 0, "total": 1}, now,
                             subscribers_total=1050, subscribers_prev=1000)
    assert "Подписчиков: 1050 (+50 за день)" in text


def test_format_summary_negative_delta_has_sign():
    import daily_summary as ds
    now = datetime(2026, 8, 5, 20, 0, 0)
    text = ds.format_summary({"shorts": 0, "longform": 0, "total": 0}, now,
                             subscribers_total=990, subscribers_prev=1000)
    assert "(-10 за день)" in text


def test_format_summary_omits_subscribers_when_unavailable():
    import daily_summary as ds
    now = datetime(2026, 8, 5, 20, 0, 0)
    text = ds.format_summary({"shorts": 0, "longform": 0, "total": 0}, now)
    assert "Подписчиков" not in text


def test_fetch_subscribers_total_none_without_connected_channel(client):
    from database import SessionLocal
    import daily_summary as ds

    r = client.post("/api/channels", json={"name": "C", "niche": "test"}, headers=_h(client))
    assert r.status_code in (200, 201)

    db = SessionLocal()
    try:
        assert ds.fetch_subscribers_total(db) is None  # no channel has a connected YouTube account
    finally:
        db.close()


def test_send_stores_subscriber_total_for_next_day_delta(client, monkeypatch):
    """The subscriber total captured today becomes tomorrow's baseline via
    the marker row's context -- no separate snapshot table."""
    import daily_summary as ds
    monkeypatch.setenv("DAILY_SUMMARY_HOUR", "18")
    sent = []
    monkeypatch.setattr("openai_quota_guard.send_telegram_alert", lambda text: sent.append(text) or True)

    counts_iter = iter([1000, 1080])
    monkeypatch.setattr(ds, "fetch_subscribers_total", lambda db: next(counts_iter))

    day1 = datetime(2026, 8, 5, 19, 0, 0)
    ok1 = ds.maybe_send_daily_summary(day1)
    assert ok1 is True
    assert "Подписчиков: 1000" in sent[0]
    assert "за день" not in sent[0]  # no prior baseline yet

    day2 = datetime(2026, 8, 6, 19, 0, 0)
    ok2 = ds.maybe_send_daily_summary(day2)
    assert ok2 is True
    assert "Подписчиков: 1080 (+80 за день)" in sent[1]


def test_telegram_not_configured_degrades_gracefully(client, monkeypatch):
    """send_telegram_alert already logs+returns False when unconfigured
    (openai_quota_guard.py) -- confirm the daily summary still records the
    marker (no repeated attempts) instead of crashing or retrying forever."""
    import daily_summary as ds
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("DAILY_SUMMARY_HOUR", "0")

    now = datetime.utcnow()
    ok = ds.maybe_send_daily_summary(now)
    assert ok is False  # telegram wasn't actually sent
    # but the marker was still recorded -- no repeated attempts this day
    ok2 = ds.maybe_send_daily_summary(now)
    assert ok2 is False
