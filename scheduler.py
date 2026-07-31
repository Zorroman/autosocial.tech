"""Content Factory — auto-generation scheduler.

For every channel with automatic_generation_enabled + a niche + active status,
produces up to `daily_video_limit` videos per day, paced across the day. Each
video: Director picks an idea → project → AI writes the script → the factory
line runs (scenes → media → render → AI Publisher → publish). The script
checkpoint is auto-passed for scheduled videos (no human at 3am); publishing
still follows the channel's publishing_mode — manual channels stop for review
at AI Publisher, only full-autopilot channels publish without confirmation.

Runs as a daemon loop inside the worker. Kill switch:
FACTORY_SCHEDULER_ENABLED=false. Cadence: FACTORY_SCHEDULER_INTERVAL seconds.

Concurrency safety (does NOT rely on the single daemon thread):
Before the long, money-spending pipeline runs, a slot is *reserved* inside a
single Postgres transaction that (a) locks the channel row with
`SELECT ... FOR UPDATE SKIP LOCKED`, (b) re-checks the enabled flags, the daily
quota and the due-time, and (c) advances `last_generated_at` to now. Because the
reservation commits before generation starts, a worker restart mid-pipeline, a
second worker replica, or two overlapping ticks can never create a duplicate:
the second caller either skips the locked row or fails the re-checked due-time.
`last_generated_at` is the idempotency key — one reservation per (channel,
interval). A failed generation keeps the reservation (the slot is spent) so a
persistently-broken channel is retried at most once per interval, never in a
tight loop.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

from database import SessionLocal
from app_models import Channel, VideoProject

log = logging.getLogger("factory.scheduler")
_API = (os.getenv("FACTORY_API_BASE") or "http://backend:5000").rstrip("/")

# Never let more than this many unfinished factory projects pile up per channel.
try:
    _BACKLOG_LIMIT = max(1, int(os.getenv("FACTORY_BACKLOG_LIMIT", "6")))
except Exception:
    _BACKLOG_LIMIT = 6


def _window_hours() -> tuple[int, int]:
    """Daytime publishing window [start, end) in the channel's local timezone.
    Shorts are only generated inside this window and paced across it (default
    06:00–22:00 → 20/day lands every ~48 min, none overnight). Set start=0,
    end=24 for round-the-clock."""
    try:
        s = int(os.getenv("SHORTS_WINDOW_START_HOUR", "6"))
        e = int(os.getenv("SHORTS_WINDOW_END_HOUR", "22"))
    except Exception:
        s, e = 6, 22
    s = min(max(0, s), 23)
    e = min(max(s + 1, e), 24)
    return s, e


def _enabled() -> bool:
    return os.getenv("FACTORY_SCHEDULER_ENABLED", "true").lower() in {"1", "true", "yes"}


def _interval_seconds() -> int:
    try:
        return max(120, int(os.getenv("FACTORY_SCHEDULER_INTERVAL", "900")))
    except Exception:
        return 900


def _token(user_id: int) -> str:
    import sys
    _r = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        from auth import create_token
        return create_token(user_id)
    finally:
        sys.stdout = _r


def _post(path: str, token: str, body: dict | None = None, timeout: int = 180):
    try:
        r = requests.post(f"{_API}/api{path}",
                          headers={"Authorization": f"Bearer {token}"},
                          json=(body or {}), timeout=timeout)
        try:
            j = r.json()
        except Exception:
            j = {}
        return r.status_code, j
    except Exception as exc:
        return 0, {"error": str(exc)[:200]}


def _local(channel: Channel, now_utc: datetime) -> datetime:
    """`now_utc` expressed in the channel's local timezone (tz-aware)."""
    tzname = (channel.timezone or "UTC").strip() or "UTC"
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tzname)
    except Exception:
        tz = timezone.utc
    return now_utc.replace(tzinfo=timezone.utc).astimezone(tz)


def _day_start_utc(channel: Channel, now_utc: datetime) -> datetime:
    """Naive-UTC timestamp of the start of *today* in the channel's timezone.

    Pacing (the interval between videos) is wall-clock-independent — it counts
    from last_generated_at. This boundary only decides which videos count
    toward today's quota, and it honours the channel's configured timezone so
    "6 per day" means the channel owner's day, not the server's.
    """
    local = _local(channel, now_utc)
    local_midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)


def _in_window(channel: Channel, now_utc: datetime) -> bool:
    """True if the channel's local time is inside the daytime publishing window."""
    start, end = _window_hours()
    if start <= 0 and end >= 24:
        return True
    return start <= _local(channel, now_utc).hour < end


def _made_today(db, channel: Channel, now_utc: datetime) -> int:
    start = _day_start_utc(channel, now_utc)
    return (db.query(VideoProject)
            .filter(VideoProject.channel_id == channel.id,
                    VideoProject.created_at >= start).count())


def _due(channel: Channel, made_today: int, now_utc: datetime) -> bool:
    limit = int(channel.daily_video_limit or 0)
    if limit <= 0 or made_today >= limit:
        return False
    # Only during the daytime window, and paced across the window (not 24h) so
    # all `limit` videos land inside 06:00–22:00 (~48 min apart for 20/day).
    if not _in_window(channel, now_utc):
        return False
    start, end = _window_hours()
    interval = timedelta(hours=(end - start)) / limit
    last = channel.last_generated_at
    if last and (now_utc - last) < interval:
        return False
    return True


def _reserve(channel_id: int) -> tuple[bool, int | None, int | None]:
    """Atomically claim one generation slot for a channel.

    Returns (reserved, owner_user_id, daily_limit). When reserved is True the
    caller — and only this caller — must proceed to generate one video; the
    channel's last_generated_at has already been advanced inside the locked
    transaction so no concurrent tick, replica or restart can pass the same
    due-time.
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # Lock the channel row. SKIP LOCKED → if another tick holds it, we get
        # None and simply move on. (No-op lock on SQLite dev, which is fine:
        # dev runs a single worker thread.)
        ch = (db.query(Channel)
              .filter(Channel.id == channel_id)
              .with_for_update(skip_locked=True)
              .first())
        if ch is None:
            return False, None, None
        # Re-check every precondition inside the transaction — state may have
        # changed (e.g. the owner paused the channel) since the candidate scan.
        if not (ch.automatic_generation_enabled and ch.niche_id
                and ch.status == "active"):
            return False, None, None
        made = _made_today(db, ch, now)
        if not _due(ch, made, now):
            return False, None, None
        # At most one actively-running pipeline per channel at a time — but a
        # render that was killed (OOM, restart) leaves pipeline_state="running"
        # forever and would silently stall ALL generation. Self-heal: any project
        # "running" longer than the stale window is treated as dead, reset to
        # needs_review, and no longer blocks. A live short render finishes well
        # within this window.
        stale_min = int(os.getenv("FACTORY_RUNNING_STALE_MIN", "30"))
        stale_before = now - timedelta(minutes=stale_min)
        active = 0
        for rp in (db.query(VideoProject)
                   .filter(VideoProject.channel_id == channel_id,
                           VideoProject.pipeline_state == "running").all()):
            if (rp.updated_at or rp.created_at or now) < stale_before:
                rp.pipeline_state = "needs_review"
                rp.pipeline_error = f"Рендер завис в running >{stale_min} мин; авто-сброс планировщиком."
                rp.updated_at = now
                log.warning("scheduler: reset stale-running project %s (channel %s)", rp.id, channel_id)
            else:
                active += 1
        if active > 0:
            return False, None, None
        # Backlog cap: never let more than BACKLOG_LIMIT unfinished factory
        # projects pile up (e.g. many needs_review). Retry a later tick once the
        # backlog drains — last_generated_at is NOT advanced on this skip.
        unfinished = (db.query(VideoProject)
                      .filter(VideoProject.channel_id == channel_id,
                              VideoProject.pipeline_stage.isnot(None),
                              VideoProject.pipeline_state != "done").count())
        if unfinished >= _BACKLOG_LIMIT:
            return False, None, None
        # Reserve: spend the slot before the long pipeline runs.
        ch.last_generated_at = now
        owner = ch.owner_user_id
        limit = ch.daily_video_limit
        db.commit()
        return True, owner, limit
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def generate_one(channel_id: int, owner_id: int) -> tuple[bool, str]:
    """Drive one full video through Director → project → script → factory line.

    Assumes the slot has already been reserved by _reserve(); this only spends
    the reserved slot. Publishing stays gated by publishing_mode inside the
    orchestrator, so a manual channel never auto-uploads to YouTube.
    """
    token = _token(owner_id)
    code, out = _post("/content-director/generate", token, {"channel_id": channel_id})
    if code not in (200, 201):
        return False, f"director: {out.get('error') or code}"
    sid = (out.get("strategy") or {}).get("id")
    if not sid:
        return False, "director: no strategy id"
    code, out = _post("/content-director/approve", token, {"strategy_id": sid})
    if code not in (200, 201):
        return False, f"approve: {out.get('error') or code}"
    pid = out.get("video_project_id") or (out.get("strategy") or {}).get("video_project_id")
    if not pid:
        return False, "approve: no project id"
    code, out = _post(f"/video-projects/{pid}/generate-script", token, {}, timeout=120)
    if code not in (200, 201):
        return False, f"script: {out.get('error') or code}"
    code, out = _post(f"/video-projects/{pid}/pipeline/approve", token, {})
    if code not in (200, 201, 202):
        return False, f"run: {out.get('error') or code}"
    return True, f"project {pid}"


def _candidate_channel_ids() -> list[int]:
    """Cheap read-only scan for channels that *might* be due. The authoritative
    check + reservation happens per-channel under a row lock in _reserve()."""
    db = SessionLocal()
    try:
        rows = (db.query(Channel.id)
                .filter(Channel.automatic_generation_enabled.is_(True),
                        Channel.status == "active",
                        Channel.niche_id.isnot(None),
                        Channel.daily_video_limit > 0)
                .all())
        return [r[0] for r in rows]
    finally:
        db.close()


def scheduler_tick() -> None:
    for cid in _candidate_channel_ids():
        # One problematic channel must never block the others.
        try:
            reserved, owner, limit = _reserve(cid)
            if not reserved:
                continue
            ok, info = generate_one(cid, owner)
            if ok:
                log.info("scheduler: channel %s generated %s (limit %s/day)", cid, info, limit)
            else:
                # Reservation is intentionally kept — the slot is spent, so a
                # broken channel retries at most once per interval, not per tick.
                log.warning("scheduler: channel %s generation failed: %s", cid, info)
        except Exception as exc:
            log.warning("scheduler: channel %s error: %s", cid, str(exc)[:200])


def _loop() -> None:
    # small startup delay so the backend is ready to serve internal calls
    time.sleep(20)
    while True:
        try:
            if _enabled():
                scheduler_tick()
        except Exception as exc:
            log.warning("scheduler loop error: %s", str(exc)[:200])
        time.sleep(_interval_seconds())


def start_in_background():
    t = threading.Thread(target=_loop, name="factory-scheduler", daemon=True)
    t.start()
    log.info("factory scheduler started (enabled=%s, interval=%ss)", _enabled(), _interval_seconds())
    return t
