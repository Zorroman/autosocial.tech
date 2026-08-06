"""Daily Telegram summary of published videos.

Runs as a daemon loop inside the worker (same pattern as scheduler.py /
longform_scheduler.py -- see worker.py). Once per day, after
DAILY_SUMMARY_HOUR has passed (server/UTC time), sends one Telegram message
counting how many Shorts and how many long-form videos published that day,
plus the current total subscriber count and the change since yesterday's
summary (subscriber count is fetched live from the YouTube Data API --
never fabricated; omitted from the message if no channel is connected or
the API call fails). Reuses openai_quota_guard.send_telegram_alert(), so it
degrades to a log warning (never crashes, never spams) if
TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID aren't configured. A SystemLog marker
row (one per calendar day) guarantees at most one send per day, durable
across worker restarts -- same technique already used for the OpenAI
quota-alert cooldown. That marker's context column also stores the
subscriber total captured that day, which doubles as yesterday's baseline
for the next day's delta -- no separate snapshot table needed.

Kill switch: DAILY_SUMMARY_ENABLED=false.

Known limitation: DAILY_SUMMARY_HOUR is a fixed UTC hour, not a real
timezone-aware local time -- it will drift by an hour across a DST
transition. Simplest correct thing for a single-server, single-timezone
deployment; adjust the env var by hand if that ever matters.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime

import requests

log = logging.getLogger("daily.summary")

_MARKER_PREFIX = "daily_summary_sent:"

# Shorts vs long-form split, matching the threshold used everywhere else in
# the pipeline (video_script_generator.generate(), etc.).
_LONGFORM_THRESHOLD_SECONDS = 150


def _enabled() -> bool:
    return os.getenv("DAILY_SUMMARY_ENABLED", "true").lower() in {"1", "true", "yes"}


def _hour() -> int:
    try:
        h = int(os.getenv("DAILY_SUMMARY_HOUR", "18"))  # ~20:00 Europe/Berlin (CEST)
    except Exception:
        h = 18
    return min(max(0, h), 23)


def _today_marker(now: datetime) -> str:
    return f"{_MARKER_PREFIX}{now.strftime('%Y-%m-%d')}"


def _already_sent_today(db, now: datetime) -> bool:
    from app_models import SystemLog
    return db.query(SystemLog).filter(SystemLog.message == _today_marker(now)).first() is not None


def _record_sent(db, now: datetime, subscribers_total: int | None) -> None:
    from app_models import SystemLog
    context = json.dumps({"subscribers_total": subscribers_total}) if subscribers_total is not None else None
    db.add(SystemLog(level="info", message=_today_marker(now), context=context))
    db.commit()


def _previous_subscribers_total(db, now: datetime) -> int | None:
    """Subscriber total captured on the most recent prior day this summary
    sent -- yesterday's baseline for today's delta. Marker messages are
    'daily_summary_sent:YYYY-MM-DD', a fixed-width format that sorts
    lexicographically the same as chronologically."""
    from app_models import SystemLog
    prev = (
        db.query(SystemLog)
        .filter(SystemLog.message.like(f"{_MARKER_PREFIX}%"), SystemLog.message < _today_marker(now))
        .order_by(SystemLog.message.desc())
        .first()
    )
    if not prev or not prev.context:
        return None
    try:
        return json.loads(prev.context).get("subscribers_total")
    except Exception:
        return None


def _channel_youtube_token(db, channel) -> str | None:
    """Google OAuth access token for this channel's connected YouTube
    account. Mirrors publications_api._user_youtube_account/_valid_account_token,
    but scoped by channel.owner_user_id instead of flask.g -- this runs in a
    background thread, outside any request context."""
    from app_models import SocialAccount
    from publications_api import _valid_account_token

    acc = None
    if channel.youtube_social_account_id:
        acc = db.query(SocialAccount).filter_by(id=channel.youtube_social_account_id).first()
    if not acc:
        acc = (
            db.query(SocialAccount)
            .filter(SocialAccount.user_id == channel.owner_user_id, SocialAccount.provider == "youtube")
            .order_by(SocialAccount.updated_at.desc())
            .first()
        )
    if not acc:
        return None
    return _valid_account_token(db, acc)


def fetch_subscribers_total(db) -> int | None:
    """Sum of current subscriberCount across every connected YouTube channel,
    via the YouTube Data API (channels.list?part=statistics; already-granted
    youtube.readonly scope, same as analytics_api.py's video sync). Returns
    None (never 0) if there are no connected channels or every lookup
    failed, so the summary can omit the line instead of reporting a fake 0."""
    from app_models import Channel

    channels = (
        db.query(Channel)
        .filter(Channel.youtube_channel_id.isnot(None), Channel.youtube_connection_status == "connected")
        .all()
    )
    if not channels:
        return None
    total = 0
    got_any = False
    for ch in channels:
        token = _channel_youtube_token(db, ch)
        if not token:
            continue
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "statistics", "id": ch.youtube_channel_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if not resp.ok:
                continue
            items = (resp.json() or {}).get("items") or []
            if not items:
                continue
            total += int((items[0].get("statistics") or {}).get("subscriberCount") or 0)
            got_any = True
        except Exception as exc:
            log.warning("daily summary: subscriber fetch failed for channel %s: %s", ch.id, str(exc)[:200])
    return total if got_any else None


def counts_for_today(db, now: datetime) -> dict:
    from app_models import Publication, VideoProject

    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.query(VideoProject.duration_target_seconds)
        .join(Publication, Publication.project_id == VideoProject.id)
        .filter(Publication.status == "published",
               Publication.published_at >= start,
               Publication.published_at <= now)
        .all()
    )
    shorts = sum(1 for (d,) in rows if (d or 0) < _LONGFORM_THRESHOLD_SECONDS)
    longform = sum(1 for (d,) in rows if (d or 0) >= _LONGFORM_THRESHOLD_SECONDS)
    return {"shorts": shorts, "longform": longform, "total": len(rows)}


def format_summary(counts: dict, now: datetime, subscribers_total: int | None = None,
                    subscribers_prev: int | None = None) -> str:
    lines = [
        f"AutoSocial: итоги дня {now.strftime('%Y-%m-%d')}",
        f"Shorts опубликовано: {counts['shorts']}",
        f"Long-form опубликовано: {counts['longform']}",
        f"Всего: {counts['total']}",
    ]
    if subscribers_total is not None:
        if subscribers_prev is not None:
            delta = subscribers_total - subscribers_prev
            lines.append(f"Подписчиков: {subscribers_total} ({'+' if delta >= 0 else ''}{delta} за день)")
        else:
            lines.append(f"Подписчиков: {subscribers_total}")
    return "\n".join(lines)


def maybe_send_daily_summary(now: datetime | None = None) -> bool:
    """Checks the configured hour and the once-per-day marker, sends at most
    one Telegram message per calendar day. Never raises."""
    from database import SessionLocal
    import openai_quota_guard as quotaguard

    now = now or datetime.utcnow()
    if now.hour < _hour():
        return False
    db = SessionLocal()
    try:
        if _already_sent_today(db, now):
            return False
        counts = counts_for_today(db, now)
        subs_prev = _previous_subscribers_total(db, now)
        subs_total = fetch_subscribers_total(db)
        text = format_summary(counts, now, subs_total, subs_prev)
        sent = quotaguard.send_telegram_alert(text)
        _record_sent(db, now, subs_total)
        return sent
    except Exception as exc:
        log.warning("daily summary failed: %s", str(exc)[:200])
        return False
    finally:
        db.close()


def _loop() -> None:
    time.sleep(20)  # let the backend finish starting up first
    while True:
        try:
            if _enabled():
                maybe_send_daily_summary()
        except Exception as exc:
            log.warning("daily summary loop error: %s", str(exc)[:200])
        # Cheap to check often -- the once-per-day marker makes over-checking
        # harmless, and a 10-minute cadence keeps the actual send close to
        # the configured hour without needing real cron semantics.
        time.sleep(600)


def start_in_background():
    t = threading.Thread(target=_loop, name="daily-summary", daemon=True)
    t.start()
    log.info("daily summary scheduler started (enabled=%s, hour=%s UTC)", _enabled(), _hour())
    return t
