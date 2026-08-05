"""Daily Telegram summary of published videos.

Runs as a daemon loop inside the worker (same pattern as scheduler.py /
longform_scheduler.py -- see worker.py). Once per day, after
DAILY_SUMMARY_HOUR has passed (server/UTC time), sends one Telegram message
counting how many Shorts and how many long-form videos published that day.
Reuses openai_quota_guard.send_telegram_alert(), so it degrades to a log
warning (never crashes, never spams) if TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID
aren't configured. A SystemLog marker row (one per calendar day) guarantees
at most one send per day, durable across worker restarts -- same technique
already used for the OpenAI quota-alert cooldown.

Kill switch: DAILY_SUMMARY_ENABLED=false.

Known limitation: DAILY_SUMMARY_HOUR is a fixed UTC hour, not a real
timezone-aware local time -- it will drift by an hour across a DST
transition. Simplest correct thing for a single-server, single-timezone
deployment; adjust the env var by hand if that ever matters.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime

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


def _record_sent(db, now: datetime) -> None:
    from app_models import SystemLog
    db.add(SystemLog(level="info", message=_today_marker(now), context=None))
    db.commit()


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


def format_summary(counts: dict, now: datetime) -> str:
    return (
        f"AutoSocial: итоги дня {now.strftime('%Y-%m-%d')}\n"
        f"Shorts опубликовано: {counts['shorts']}\n"
        f"Long-form опубликовано: {counts['longform']}\n"
        f"Всего: {counts['total']}"
    )


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
        text = format_summary(counts, now)
        sent = quotaguard.send_telegram_alert(text)
        _record_sent(db, now)
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
