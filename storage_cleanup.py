"""Disk-usage cleanup for the footage cache and confirmed-published render
outputs -- both grow without bound otherwise (root cause of the 2026-08-11
disk-full outage that crash-looped postgres, see project notes). Runs as a
daemon loop inside the worker (same pattern as scheduler.py /
daily_summary.py -- see worker.py).

Two independent, conservative sweeps:

- Footage cache (`cache/footage`, tracked via FootageAsset): deletes only
  the on-disk FILE for unreserved assets whose last_used_at (falling back to
  created_at if never reused) is older than FOOTAGE_CACHE_RETENTION_DAYS.
  The FootageAsset DB row is kept (cheap metadata/provenance), only
  `local_path` is cleared -- footage_library.pick_local_candidates() already
  skips any asset whose local_path file is missing, and register_asset()
  already re-downloads/re-registers when a provider_asset_id's local_path is
  gone, so clearing it can never crash the render pipeline, only cost a
  fresh download on next reuse.

- Rendered outputs (`output/videos`, `output/longform_jobs`): deletes only
  VideoProject.output_path files for projects with a CONFIRMED published
  Publication (status="published", youtube_video_id set) whose
  published_at is older than OUTPUT_RETENTION_DAYS. The video already lives
  on YouTube; the local copy past that point is pure disk cost. Never
  touches a project without a confirmed publish -- drafts, needs_review,
  and stuck/failed uploads stay untouched (exactly the kind of row the
  2026-08-11 incident showed can't be assumed dead from status alone).

Kill switch: STORAGE_CLEANUP_ENABLED=false. Never raises; records what it
freed via a once-per-day SystemLog marker (same durable-across-restarts
technique as daily_summary.py).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("storage.cleanup")

_MARKER_PREFIX = "storage_cleanup_ran:"


def _enabled() -> bool:
    return os.getenv("STORAGE_CLEANUP_ENABLED", "true").lower() in {"1", "true", "yes"}


def _footage_retention_days() -> int:
    try:
        return max(1, int(os.getenv("FOOTAGE_CACHE_RETENTION_DAYS", "10")))
    except Exception:
        return 21


def _output_retention_days() -> int:
    try:
        return max(1, int(os.getenv("OUTPUT_RETENTION_DAYS", "5")))
    except Exception:
        return 5


def _today_marker(now: datetime) -> str:
    return f"{_MARKER_PREFIX}{now.strftime('%Y-%m-%d')}"


def _already_ran_today(db, now: datetime) -> bool:
    from app_models import SystemLog
    return db.query(SystemLog).filter(SystemLog.message == _today_marker(now)).first() is not None


def _record_ran(db, now: datetime, freed_bytes: int, footage_n: int, output_n: int) -> None:
    from app_models import SystemLog
    context = json.dumps({"freed_bytes": freed_bytes, "footage_deleted": footage_n, "output_deleted": output_n})
    db.add(SystemLog(level="info", message=_today_marker(now), context=context))
    db.commit()


def cleanup_footage_cache(db, now: datetime | None = None) -> tuple[int, int]:
    """Deletes stale, unreserved cached footage FILES (keeps the FootageAsset
    row). Returns (files_deleted, bytes_freed). Never raises."""
    from app_models import FootageAsset

    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=_footage_retention_days())
    rows = (
        db.query(FootageAsset)
        .filter(FootageAsset.local_path.isnot(None),
                FootageAsset.reserved_by_job_id.is_(None))
        .all()
    )
    deleted, freed = 0, 0
    for a in rows:
        stamp = a.last_used_at or a.created_at
        if not stamp or stamp >= cutoff:
            continue
        try:
            path = Path(a.local_path)
            if path.exists():
                freed += path.stat().st_size
                path.unlink()
            a.local_path = None
            deleted += 1
        except Exception as exc:
            log.warning("footage cleanup: failed to delete %s: %s", a.local_path, str(exc)[:200])
    if deleted:
        db.commit()
    return deleted, freed


def cleanup_published_outputs(db, now: datetime | None = None) -> tuple[int, int]:
    """Deletes rendered-output files for confirmed-published projects past
    the retention window. Returns (files_deleted, bytes_freed). Never
    raises."""
    from app_models import VideoProject, Publication
    from app_settings import settings

    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=_output_retention_days())
    rows = (
        db.query(VideoProject.id, VideoProject.output_path)
        .join(Publication, Publication.project_id == VideoProject.id)
        .filter(Publication.status == "published",
                Publication.youtube_video_id.isnot(None),
                Publication.published_at.isnot(None),
                Publication.published_at < cutoff,
                VideoProject.output_path.isnot(None))
        .all()
    )
    base = settings.BASE_DIR.resolve()
    deleted, freed = 0, 0
    for _pid, output_path in rows:
        if not output_path:
            continue
        try:
            path = (settings.BASE_DIR / output_path).resolve()
            if base not in path.parents and path != base:
                continue  # never follow a path outside BASE_DIR
            if path.exists():
                freed += path.stat().st_size
                path.unlink()
                deleted += 1
        except Exception as exc:
            log.warning("output cleanup: failed to delete %s: %s", output_path, str(exc)[:200])
    return deleted, freed


def run_cleanup(now: datetime | None = None) -> dict:
    from database import SessionLocal

    now = now or datetime.utcnow()
    db = SessionLocal()
    try:
        if _already_ran_today(db, now):
            return {"skipped": "already_ran_today"}
        footage_n, footage_bytes = cleanup_footage_cache(db, now)
        output_n, output_bytes = cleanup_published_outputs(db, now)
        freed = footage_bytes + output_bytes
        _record_ran(db, now, freed, footage_n, output_n)
        if freed:
            log.info("storage cleanup: freed %.1f MB (%s footage files, %s rendered outputs)",
                      freed / 1_000_000, footage_n, output_n)
        return {"freed_bytes": freed, "footage_deleted": footage_n, "output_deleted": output_n}
    except Exception as exc:
        log.warning("storage cleanup failed: %s", str(exc)[:200])
        return {"error": str(exc)[:200]}
    finally:
        db.close()


def _loop() -> None:
    time.sleep(30)  # let the backend finish starting up first
    while True:
        try:
            if _enabled():
                run_cleanup()
        except Exception as exc:
            log.warning("storage cleanup loop error: %s", str(exc)[:200])
        # Cheap to check often -- the once-per-day marker makes over-checking
        # harmless, same technique as daily_summary.py.
        time.sleep(1800)


def start_in_background():
    t = threading.Thread(target=_loop, name="storage-cleanup", daemon=True)
    t.start()
    log.info("storage cleanup scheduler started (enabled=%s, footage_retention=%sd, output_retention=%sd)",
              _enabled(), _footage_retention_days(), _output_retention_days())
    return t
