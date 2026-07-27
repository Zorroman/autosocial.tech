"""Daily long-form autopilot — one long video per day per enabled channel.

Completely separate from the Shorts scheduler (scheduler.py):

  * paces off Channel.longform_last_generated_at (24 h interval), so it never
    interferes with the Shorts cadence (Channel.last_generated_at);
  * reuses the Director → approve → generate-script chain (a channel whose
    default_video_duration_seconds >= 150 yields a long-form script);
  * then ENQUEUES longform_job.render_and_publish on the same single "render"
    RQ queue as the Shorts factory, so the memory-heavy long-form render never
    runs concurrently with a Shorts render on the 3.8 GB box.

Enabling is opt-in per channel (Channel.longform_enabled) and independent of
automatic_generation_enabled (which drives the Shorts factory). A long-form
channel therefore keeps automatic_generation_enabled = False.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta

from database import SessionLocal
from saas_models import Channel
from scheduler import _token, _post  # reuse internal-call helpers

log = logging.getLogger("longform.scheduler")

_INTERVAL_H = 24  # one long-form video per day per channel


def _enabled() -> bool:
    return os.getenv("LONGFORM_SCHEDULER_ENABLED", "1") not in ("0", "false", "False")


def _tick_seconds() -> int:
    # how often to wake and check; the 24 h pacing is enforced per channel.
    return int(os.getenv("LONGFORM_SCHEDULER_TICK_SECONDS", "1800"))


def _candidate_channel_ids() -> list[int]:
    db = SessionLocal()
    try:
        rows = (db.query(Channel.id)
                .filter(Channel.longform_enabled.is_(True),
                        Channel.status == "active",
                        Channel.niche_id.isnot(None),
                        Channel.youtube_connection_status == "connected")
                .all())
        return [r[0] for r in rows]
    finally:
        db.close()


def _reserve(channel_id: int) -> tuple[bool, int | None]:
    """Atomically claim today's long-form slot. Advances longform_last_generated_at
    under a row lock so no concurrent tick/restart double-generates."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        ch = (db.query(Channel)
              .filter(Channel.id == channel_id)
              .with_for_update(skip_locked=True)
              .first())
        if ch is None:
            return False, None
        if not (ch.longform_enabled and ch.niche_id
                and ch.status == "active"
                and ch.youtube_connection_status == "connected"):
            return False, None
        last = ch.longform_last_generated_at
        if last and (now - last) < timedelta(hours=_INTERVAL_H):
            return False, None
        ch.longform_last_generated_at = now
        owner = ch.owner_user_id
        db.commit()
        return True, owner
    except Exception as exc:
        db.rollback()
        log.warning("longform reserve error ch=%s: %s", channel_id, str(exc)[:200])
        return False, None
    finally:
        db.close()


def _enqueue_render(project_id: int) -> str:
    """Queue the render+publish on the single 'render' worker (serialized with
    Shorts renders). Falls back to a thread if RQ/Redis is unavailable."""
    import longform_job
    try:
        from saas_settings import settings
        if getattr(settings, "SYNC_JOBS", False):
            longform_job.render_and_publish(project_id)
            return "sync"
    except Exception:
        pass
    try:
        from redis import Redis
        from rq import Queue
        from saas_settings import settings
        conn = Redis.from_url(settings.REDIS_URL)
        conn.ping()
        Queue("render", connection=conn).enqueue(
            longform_job.render_and_publish, project_id, job_timeout=3600)
        return "rq"
    except Exception:
        t = threading.Thread(target=longform_job.render_and_publish,
                             args=(project_id,), daemon=True)
        t.start()
        return "thread"


def generate_one(channel_id: int, owner_id: int) -> tuple[bool, str]:
    """Director → approve → long-form script → enqueue render+publish."""
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
    code, out = _post(f"/video-projects/{pid}/generate-script", token, {}, timeout=300)
    if code not in (200, 201):
        return False, f"script: {out.get('error') or code}"
    # generate-script only writes script_text; scenes are a separate station.
    # longform_pipeline reuses the project's VideoScene rows, so split them now
    # (long-form → ~4 sentences/scene, incl. the final CTA scene).
    code, out = _post(f"/video-projects/{pid}/split-scenes", token, {}, timeout=120)
    if code not in (200, 201):
        return False, f"split-scenes: {out.get('error') or code}"
    mode = _enqueue_render(int(pid))
    return True, f"project {pid} (render:{mode})"


def scheduler_tick() -> None:
    for cid in _candidate_channel_ids():
        try:
            reserved, owner = _reserve(cid)
            if not reserved:
                continue
            ok, info = generate_one(cid, owner)
            if ok:
                log.info("longform: channel %s generated %s", cid, info)
            else:
                log.warning("longform: channel %s generation failed: %s", cid, info)
        except Exception as exc:
            log.warning("longform: channel %s error: %s", cid, str(exc)[:200])


def _loop() -> None:
    time.sleep(40)  # let the backend come up + stagger after the Shorts scheduler
    while True:
        try:
            if _enabled():
                scheduler_tick()
        except Exception as exc:
            log.warning("longform loop error: %s", str(exc)[:200])
        time.sleep(_tick_seconds())


def start_in_background():
    t = threading.Thread(target=_loop, name="longform-scheduler", daemon=True)
    t.start()
    log.info("long-form scheduler started (enabled=%s, tick=%ss)", _enabled(), _tick_seconds())
    return t
