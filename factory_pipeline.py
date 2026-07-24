"""Content Factory — pipeline orchestrator.

Runs a video project through the production line, one station at a time:

    script → [checkpoint] → scenes → media → render → publish

Design: the orchestrator runs on the WORKER and drives each station by calling
the app's own HTTP endpoints over the internal Docker network. This reuses the
existing, tested station logic (split-scenes, auto-media, render) verbatim —
no duplicated pipeline code — while updating the project's pipeline_stage /
pipeline_state so the UI can visualise the line.

State model (stored on VideoProject):
    pipeline_stage : script | scenes | media | render | publish
    pipeline_state : waiting | running | needs_review | error | done

On any station failure the project stops at pipeline_state="error" with a human
message in pipeline_error — the station can then be retried without recreating
the video. Render itself is an async job; its live status is reflected by the
/pipeline/state endpoint, not blocked on here.
"""
from __future__ import annotations

import os

import requests

from database import SessionLocal
from saas_models import Channel, RenderJob, VideoProject, VideoScene

# Internal base URL of the backend, reachable from the worker container.
_API_BASE = (os.getenv("FACTORY_API_BASE") or "http://backend:5000").rstrip("/")
_ACTIVE_JOB = {"pending", "queued", "processing", "rendering"}


def effective_mode(project, channel) -> str:
    """Resolve the effective publishing mode for a video:
    per-video override → channel default → 'manual' (safe fallback).
    Returns 'manual' or 'automatic'."""
    ov = (getattr(project, "publishing_override", None) or "").strip().lower()
    if ov in ("manual", "automatic"):
        return ov
    m = (getattr(channel, "publishing_mode", None) or "").strip().lower()
    if m in ("manual", "automatic"):
        return m
    return "automatic" if getattr(channel, "autopilot_enabled", False) else "manual"


def _set(db, p: VideoProject, stage: str, state: str, error: str | None = None) -> None:
    p.pipeline_stage = stage
    p.pipeline_state = state
    p.pipeline_error = error
    db.commit()


def _call(path: str, token: str) -> tuple[bool, str]:
    """POST an internal station endpoint. Returns (ok, human_error)."""
    try:
        r = requests.post(f"{_API_BASE}/api{path}",
                          headers={"Authorization": f"Bearer {token}"},
                          json={}, timeout=1200)
    except Exception as exc:  # network / timeout
        return False, f"connection: {str(exc)[:200]}"
    if r.status_code in (200, 201, 202):
        return True, ""
    try:
        msg = (r.json() or {}).get("error") or r.text[:200]
    except Exception:
        msg = r.text[:200]
    return False, f"{r.status_code}: {msg}"


def run(project_id: int, token: str) -> None:
    """Advance a project as far down the line as it can go in one pass.

    Idempotent: each station is skipped when its output already exists, so a
    retry simply resumes from the failed station."""
    db = SessionLocal()
    try:
        p = db.query(VideoProject).filter_by(id=project_id).first()
        if not p:
            return
        ch = db.query(Channel).filter_by(id=p.channel_id).first()

        # station 1 — script must exist (produced by /generate-script)
        if not (p.script_text or "").strip():
            _set(db, p, "script", "needs_review", "Сначала нужно сгенерировать сценарий.")
            return

        # checkpoint — do not spend money past the script unless approved.
        # Approval sets pipeline_state="done" at the script stage; autopilot
        # channels are treated as pre-approved.
        approved = (effective_mode(p, ch) == "automatic") or (
            p.pipeline_stage == "script" and p.pipeline_state == "done"
        ) or p.pipeline_stage in ("scenes", "media", "render", "publish")
        if not approved:
            _set(db, p, "script", "needs_review", None)
            return

        # station 2 — scenes
        if db.query(VideoScene).filter_by(project_id=p.id).count() == 0:
            _set(db, p, "scenes", "running")
            ok, err = _call(f"/video-projects/{p.id}/split-scenes", token)
            if not ok:
                _set(db, p, "scenes", "error", f"Не удалось разбить на сцены. {err}")
                return

        # station 3 — media (every scene needs an attached clip)
        scenes = db.query(VideoScene).filter_by(project_id=p.id).all()
        if any(not s.selected_media_path for s in scenes):
            _set(db, p, "media", "running")
            ok, err = _call(f"/video-projects/{p.id}/auto-media", token)
            if not ok:
                _set(db, p, "media", "error", f"Не удалось подобрать видеоряд. {err}")
                return
            db.expire_all()
            scenes = db.query(VideoScene).filter_by(project_id=p.id).all()
            if any(not s.selected_media_path for s in scenes):
                _set(db, p, "media", "needs_review",
                     "Не для всех сцен нашёлся видеоряд — проверьте вручную.")
                return

        # station 4 — render (async job). Enqueue once; live status comes from
        # the render job itself (surfaced by /pipeline/state).
        if not p.output_path:
            active = (db.query(RenderJob)
                      .filter(RenderJob.project_id == p.id,
                              RenderJob.status.in_(_ACTIVE_JOB)).first())
            if not active:
                _set(db, p, "render", "running")
                ok, err = _call(f"/video-projects/{p.id}/render", token)
                if not ok:
                    _set(db, p, "render", "error", f"Не удалось запустить рендер. {err}")
                    return
            else:
                _set(db, p, "render", "running")
            return  # render is async; the render job auto-continues the line

        # station 5 — AI Publisher (metadata + thumbnail), after render output.
        if p.output_path and not (p.youtube_meta_json or "").strip():
            _set(db, p, "ai_publisher", "running")
            ok, err = _call(f"/video-projects/{p.id}/ai-publisher", token)
            if not ok:
                _set(db, p, "ai_publisher", "error", f"AI Publisher: {err}")
                return
            # the endpoint set needs_review (manual) or done (automatic).
        # station 6 — publish is Stage 3c.
    finally:
        db.close()
