"""Aggregated factory dashboard + readiness API.

GET /api/factory-dashboard  -- one call feeding the main screen (real data only).
GET /api/readiness          -- protected detailed dependency check; /api/health
                               stays the minimal public liveness probe.

No secrets, keys or tokens are ever returned; only configured/not-configured
flags and variable *names*.
"""
import os
import shutil
import subprocess
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify

from ai_pricing import spent_summary
from analytics_api import _channel_stats
from database import SessionLocal
from saas_auth import require_auth
from saas_models import (
    Channel,
    Publication,
    RenderJob,
    VideoAnalyticsSnapshot,
    VideoProject,
    VideoScene,
)
from saas_settings import settings

factory_dashboard_api = Blueprint("factory_dashboard_api", __name__, url_prefix="/api")


def _iso(dt):
    return dt.isoformat() if dt else None


# ------------------------------------------------------------ infrastructure

def _redis_status() -> dict:
    try:
        from redis import Redis
        conn = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        conn.ping()
        return {"ok": True, "conn": conn}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120], "conn": None}


def _worker_status(redis_conn) -> dict:
    """Real RQ worker heartbeat from Redis; never faked in-process."""
    if not redis_conn:
        return {"online": False, "workers": [], "reason": "redis_unavailable"}
    try:
        from rq import Worker
        workers = Worker.all(connection=redis_conn)
        infos = []
        from datetime import timezone
        now = datetime.now(timezone.utc)
        online = False
        for w in workers:
            hb = w.last_heartbeat
            if hb and hb.tzinfo is None:
                hb = hb.replace(tzinfo=timezone.utc)
            alive = bool(hb and (now - hb).total_seconds() < 120)
            online = online or alive
            infos.append({
                "name": w.name,
                "queues": [q.name for q in w.queues],
                "state": w.get_state(),
                "last_heartbeat": _iso(hb),
                "alive": alive,
            })
        return {"online": online, "workers": infos}
    except Exception as exc:
        return {"online": False, "workers": [], "reason": str(exc)[:120]}


def _bin_version(binary: str) -> str | None:
    try:
        proc = subprocess.run([binary, "-version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            return (proc.stdout or "").splitlines()[0][:80]
    except Exception:
        pass
    return None


def _disk_free_gb(path) -> float | None:
    try:
        return round(shutil.disk_usage(str(path)).free / (1024 ** 3), 1)
    except Exception:
        return None


def infrastructure_status() -> dict:
    redis = _redis_status()
    worker = _worker_status(redis.get("conn"))
    queue_size = None
    if redis.get("conn"):
        try:
            from rq import Queue
            queue_size = Queue("render", connection=redis["conn"]).count
        except Exception:
            queue_size = None
    return {
        "redis": {"ok": redis["ok"], **({"error": redis["error"]} if not redis["ok"] else {})},
        "worker": {k: v for k, v in worker.items() if k != "conn"},
        "render_queue_size": queue_size,
        "ffmpeg": _bin_version(settings.FFMPEG_BIN),
        "ffprobe": _bin_version(settings.FFPROBE_BIN),
        "output_dir": str(settings.OUTPUT_VIDEOS_DIR),
        "output_writable": os.access(settings.OUTPUT_VIDEOS_DIR, os.W_OK),
        "disk_free_gb": _disk_free_gb(settings.OUTPUT_DIR),
        "render_concurrency": settings.VIDEO_RENDER_CONCURRENCY,
    }


# ---------------------------------------------------------------- dashboard

@factory_dashboard_api.route("/factory-dashboard", methods=["GET"])
@require_auth
def factory_dashboard():
    db = SessionLocal()
    try:
        uid = g.current_user.id
        channels = (
            db.query(Channel)
            .filter(Channel.owner_user_id == uid, Channel.status != "archived")
            .order_by(Channel.created_at.asc()).all()
        )
        ch_ids = [c.id for c in channels]

        projects = (
            db.query(VideoProject).filter(VideoProject.channel_id.in_(ch_ids)).all()
            if ch_ids else []
        )
        jobs = (
            db.query(RenderJob).filter(RenderJob.channel_id.in_(ch_ids))
            .order_by(RenderJob.created_at.desc()).limit(50).all()
            if ch_ids else []
        )
        pubs = (
            db.query(Publication).filter(Publication.channel_id.in_(ch_ids)).all()
            if ch_ids else []
        )
        now = datetime.utcnow()
        d7, d30 = now - timedelta(days=7), now - timedelta(days=30)

        def _views_since(since):
            if not ch_ids:
                return None
            snaps = (
                db.query(VideoAnalyticsSnapshot)
                .filter(VideoAnalyticsSnapshot.channel_id.in_(ch_ids),
                        VideoAnalyticsSnapshot.captured_at >= since)
                .order_by(VideoAnalyticsSnapshot.captured_at.asc()).all()
            )
            latest = {}
            for s in snaps:
                if s.views is not None:
                    latest[s.publication_id] = s.views
            return sum(latest.values()) if latest else None

        overview = {
            "channels_total": len(channels),
            "channels_active": sum(1 for c in channels if c.status == "active"),
            "channels_testing": sum(1 for c in channels if c.status == "testing"),
            "channels_paused": sum(1 for c in channels if c.status == "paused"),
            "projects_in_progress": sum(1 for p in projects if p.status in {"draft", "ready", "rendering"}),
            "videos_rendered": sum(1 for p in projects if p.status == "rendered"),
            # Short vs long split (long-form == duration target >= 150s, the same
            # threshold the generator/pipeline use to switch to the long path).
            "videos_short": sum(1 for p in projects if int(p.duration_target_seconds or 0) < 150),
            "videos_long": sum(1 for p in projects if int(p.duration_target_seconds or 0) >= 150),
            "jobs_pending": sum(1 for j in jobs if j.status == "pending"),
            "jobs_processing": sum(1 for j in jobs if j.status == "processing"),
            "jobs_failed": sum(1 for j in jobs if j.status == "failed"),
            "published_7d": sum(1 for p in pubs if p.published_at and p.published_at >= d7),
            "published_30d": sum(1 for p in pubs if p.published_at and p.published_at >= d30),
            "views_7d": _views_since(d7),
            "views_30d": _views_since(d30),
        }

        channels_summary = [_channel_stats(db, c, "30") | {
            "youtube_connection_status": c.youtube_connection_status or "not_connected",
            "analytics_fresh": bool(
                db.query(VideoAnalyticsSnapshot)
                .filter(VideoAnalyticsSnapshot.channel_id == c.id,
                        VideoAnalyticsSnapshot.captured_at >= d7).first()
            ),
        } for c in channels]

        recent_projects = [
            {
                "id": p.id, "title": p.title, "status": p.status,
                "channel_id": p.channel_id,
                "updated_at": _iso(p.updated_at),
                "output_url": f"/api/media/{p.output_path}" if p.output_path else None,
            }
            for p in sorted(projects, key=lambda x: x.updated_at or x.created_at, reverse=True)[:8]
        ]

        # Activity feed built from real entities (no synthetic events).
        activity = []
        for p in sorted(projects, key=lambda x: x.created_at, reverse=True)[:5]:
            activity.append({"at": _iso(p.created_at), "type": "project_created", "text": f"Создан проект «{p.title}»"})
        for j in jobs[:8]:
            if j.status == "completed":
                activity.append({"at": _iso(j.finished_at), "type": "render_completed", "text": f"Рендер завершён (job #{j.id}, проект {j.project_id})"})
            elif j.status == "failed":
                activity.append({"at": _iso(j.finished_at), "type": "render_failed", "text": f"Рендер упал (job #{j.id}): {(j.error or '')[:60]}"})
        for pub in sorted(pubs, key=lambda x: x.updated_at or x.created_at, reverse=True)[:5]:
            if pub.status == "published":
                activity.append({"at": _iso(pub.published_at), "type": "published", "text": f"Публикация #{pub.id} опубликована ({pub.publish_mode})"})
            elif pub.status == "draft":
                activity.append({"at": _iso(pub.created_at), "type": "publication_prepared", "text": f"Подготовлена публикация #{pub.id}"})
        if ch_ids:
            for s in (
                db.query(VideoAnalyticsSnapshot)
                .filter(VideoAnalyticsSnapshot.channel_id.in_(ch_ids))
                .order_by(VideoAnalyticsSnapshot.created_at.desc()).limit(3).all()
            ):
                activity.append({"at": _iso(s.created_at), "type": "analytics_snapshot", "text": f"Снимок аналитики публикации #{s.publication_id} ({s.data_source})"})
        activity = sorted([a for a in activity if a["at"]], key=lambda x: x["at"], reverse=True)[:12]

        # Alerts: each item names a real fix location.
        alerts = []
        for j in jobs:
            if j.status == "failed":
                alerts.append({"level": "error", "text": f"Render job #{j.id} упал: {(j.error or '')[:80]}", "link": "/projects"})
        for pub in pubs:
            if pub.status == "failed":
                alerts.append({"level": "error", "text": f"Публикация #{pub.id} упала: {(pub.last_error or '')[:80]}", "link": "/publications"})
        for c in channels:
            if (c.youtube_connection_status or "not_connected") != "connected":
                alerts.append({"level": "warn", "text": f"Канал «{c.name}» без подключённого YouTube", "link": "/channels"})
        for cs in channels_summary:
            if cs["published_videos"] and not cs["analytics_fresh"]:
                alerts.append({"level": "warn", "text": f"Канал «{cs['name']}»: нет свежей аналитики (7 дней)", "link": "/factory-analytics"})
        scene_counts = {}
        if projects:
            for row in db.query(VideoScene.project_id).filter(
                VideoScene.project_id.in_([p.id for p in projects])
            ).all():
                scene_counts[row[0]] = scene_counts.get(row[0], 0) + 1
        for p in projects:
            if p.status in {"draft", "ready"} and not scene_counts.get(p.id):
                alerts.append({"level": "warn", "text": f"Проект «{p.title}» без сцен", "link": "/projects"})
        costs = spent_summary(db)
        if costs["daily_remaining"] <= costs["daily_budget"] * 0.1:
            alerts.append({"level": "warn", "text": "Дневной AI-бюджет почти исчерпан", "link": "/factory-analytics"})
        if settings.PRIVATE_ADMIN_MODE and not settings.ADMIN_ALLOWLIST_EMAILS:
            alerts.append({"level": "error", "text": "PRIVATE_ADMIN_MODE включён, но ADMIN_ALLOWLIST_EMAILS пуст (fail closed)", "link": "/factory-settings"})
        infra = infrastructure_status()
        if not infra["redis"]["ok"]:
            alerts.append({"level": "warn", "text": "Redis недоступен: очередь работает в thread-режиме (задачи теряются при рестарте)", "link": "/factory-settings"})
        elif not infra["worker"]["online"]:
            alerts.append({"level": "warn", "text": "RQ worker offline: задачи рендера не будут выполняться", "link": "/factory-settings"})

        pub_summary = {
            "draft": sum(1 for p in pubs if p.status == "draft"),
            "ready": sum(1 for p in pubs if p.status == "ready"),
            "uploading": sum(1 for p in pubs if p.status == "uploading"),
            "published": sum(1 for p in pubs if p.status == "published"),
            "failed": sum(1 for p in pubs if p.status == "failed"),
        }
        return jsonify({
            "overview": overview,
            "channels": channels_summary,
            "recent_projects": recent_projects,
            "publications": pub_summary,
            "costs": costs,
            "activity": activity,
            "alerts": alerts[:20],
            "infrastructure": infra,
        })
    finally:
        db.close()


# ----------------------------------------------------------------- readiness

@factory_dashboard_api.route("/readiness", methods=["GET"])
@require_auth
def readiness():
    checks = {}

    def _check(name, ok, critical, detail=None):
        checks[name] = {"ok": bool(ok), "critical": critical, **({"detail": detail} if detail else {})}

    db = SessionLocal()
    try:
        try:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
            _check("database", True, True)
        except Exception as exc:
            _check("database", False, True, str(exc)[:120])

        _check(
            "private_admin_config",
            not settings.PRIVATE_ADMIN_MODE or bool(settings.ADMIN_ALLOWLIST_EMAILS),
            True,
            None if settings.ADMIN_ALLOWLIST_EMAILS else "ADMIN_ALLOWLIST_EMAILS is empty",
        )
        _check("encryption_key", bool(settings.TOKEN_ENCRYPTION_KEY), True,
               None if settings.TOKEN_ENCRYPTION_KEY else "TOKEN_ENCRYPTION_KEY not set")

        redis = _redis_status()
        _check("redis", redis["ok"], False, redis.get("error"))
        worker = _worker_status(redis.get("conn"))
        _check("worker", worker["online"], False,
               None if worker["online"] else "no alive RQ worker (render jobs will not run)")

        _check("ffmpeg", bool(_bin_version(settings.FFMPEG_BIN)), True)
        _check("ffprobe", bool(_bin_version(settings.FFPROBE_BIN)), True)
        _check("output_writable", os.access(settings.OUTPUT_VIDEOS_DIR, os.W_OK), True,
               str(settings.OUTPUT_VIDEOS_DIR))
        free = _disk_free_gb(settings.OUTPUT_DIR)
        _check("disk_space", free is not None and free > 1.0, True, f"{free} GB free" if free is not None else None)

        try:
            import edge_tts  # noqa: F401
            _check("tts_edge", True, False)
        except Exception:
            _check("tts_edge", False, False, "edge-tts not importable")
        _check("openai_key", bool((os.getenv("OPENAI_API_KEY") or "").strip()), False,
               None if (os.getenv("OPENAI_API_KEY") or "").strip() else "OPENAI_API_KEY not set")
        _check("pexels_key", bool((os.getenv("PEXELS_API_KEY") or "").strip()), False,
               None if (os.getenv("PEXELS_API_KEY") or "").strip() else "PEXELS_API_KEY not set")
        _check("youtube_oauth", bool((os.getenv("GOOGLE_CLIENT_ID") or "").strip() and (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()), False)

        critical_fail = any(c["critical"] and not c["ok"] for c in checks.values())
        optional_fail = any(not c["critical"] and not c["ok"] for c in checks.values())
        status = "not_ready" if critical_fail else ("degraded" if optional_fail else "ready")
        return jsonify({"status": status, "checks": checks, "env": settings.ENV}), (503 if critical_fail else 200)
    finally:
        db.close()
