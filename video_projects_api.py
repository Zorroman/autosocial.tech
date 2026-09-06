"""VideoProject / scenes / render queue API for private YouTube-factory mode.

Vertical slice: channel -> project -> script -> scenes -> media -> render job
-> real MP4 (via video/render/render_video.py) -> preview/download.

Render jobs run through RQ when Redis is available, otherwise an in-process
thread (dev fallback; jobs are lost on restart - documented limitation).
Progress values are written at real pipeline stages, never simulated.
"""
import json
import logging
import re
import socket
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from flask import Blueprint, g, jsonify, request

from database import SessionLocal
from auth import require_auth
from app_models import Channel, ChannelIdea, Publication, RenderJob, VideoProject, VideoScene
from app_settings import settings

video_projects_api = Blueprint("video_projects_api", __name__, url_prefix="/api")

PROJECT_STATUSES = {"draft", "ready", "rendering", "rendered", "failed", "archived"}
JOB_ACTIVE = {"pending", "processing"}
VOICE_MODES = {"tts", "file", "silent"}

_RENDER_SEMAPHORE = threading.Semaphore(settings.VIDEO_RENDER_CONCURRENCY)

# Media paths attached to scenes must resolve inside one of these roots.
_PROJECT_ROOT = Path(__file__).resolve().parent


def _allowed_media_roots():
    return [
        settings.BASE_DIR.resolve(),
        settings.OUTPUT_DIR.resolve(),
        settings.CACHE_DIR.resolve(),
        (_PROJECT_ROOT / "tests" / "render_fixtures").resolve(),
        (_PROJECT_ROOT / "generated_media").resolve(),
    ]


def _media_path_ok(raw: str) -> Path | None:
    try:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (_PROJECT_ROOT / p)
        p = p.resolve()
    except Exception:
        return None
    for root in _allowed_media_roots():
        if root == p or root in p.parents:
            return p
    return None


def _own_channel(db, channel_id: int) -> Channel | None:
    return (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


def _own_project(db, project_id: int) -> VideoProject | None:
    return (
        db.query(VideoProject)
        .join(Channel, Channel.id == VideoProject.channel_id)
        .filter(VideoProject.id == project_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


def _output_file_exists(p) -> bool:
    """True when the project's rendered file is actually on disk.

    Guards the UI against an empty <video> player and a dead Download link when
    output_path is set but the file is gone (cleanup, failed render, restored DB).
    """
    rel = (getattr(p, "output_path", None) or "").strip()
    if not rel:
        return False
    try:
        f = (settings.BASE_DIR / rel).resolve()
        return settings.BASE_DIR in f.parents and f.is_file()
    except Exception:
        return False


def _iso(dt):
    return dt.isoformat() if dt else None


def _scene_dict(s: VideoScene) -> dict:
    return {
        "id": s.id,
        "project_id": s.project_id,
        "order_index": s.order_index,
        "voiceover_text": s.voiceover_text,
        "on_screen_text": s.on_screen_text,
        "estimated_duration": s.estimated_duration,
        "actual_duration": s.actual_duration,
        "visual_type": s.visual_type,
        "visual_prompt": s.visual_prompt,
        "stock_search_query": s.stock_search_query,
        "selected_media_path": s.selected_media_path,
        "media_meta": (json.loads(s.media_meta_json) if s.media_meta_json else None),
        "transition": s.transition,
        "status": s.status,
    }


def _project_dict(p: VideoProject, scenes=None, jobs=None) -> dict:
    out = {
        "id": p.id,
        "channel_id": p.channel_id,
        "idea_id": p.idea_id,
        "title": p.title,
        "status": p.status,
        "script_text": p.script_text,
        "voice_mode": p.voice_mode,
        "voiceover_path": p.voiceover_path,
        "aspect_ratio": p.aspect_ratio,
        "duration_target_seconds": p.duration_target_seconds,
        "output_path": p.output_path,
        # Only expose a playable/downloadable URL when the file really exists —
        # otherwise the UI renders an empty <video> and a dead Download link.
        "output_url": f"/api/media/{p.output_path}" if _output_file_exists(p) else None,
        "content_pillar_id": p.content_pillar_id,
        "generation_profile": (json.loads(p.generation_profile_json) if p.generation_profile_json else None),
        "error": p.error,
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
    }
    if scenes is not None:
        out["scenes"] = [_scene_dict(s) for s in scenes]
    if jobs is not None:
        out["jobs"] = [_job_dict(j) for j in jobs]
    return out


def _job_dict(j: RenderJob) -> dict:
    return {
        "id": j.id,
        "project_id": j.project_id,
        "channel_id": j.channel_id,
        "job_type": j.job_type,
        "status": j.status,
        "progress": j.progress,
        "attempts": j.attempts,
        "max_attempts": j.max_attempts,
        "error": j.error,
        "worker": j.worker,
        "output_path": j.output_path,
        "output_url": f"/api/media/{j.output_path}" if j.output_path else None,
        "created_at": _iso(j.created_at),
        "started_at": _iso(j.started_at),
        "finished_at": _iso(j.finished_at),
    }


# ---------------------------------------------------------------- projects

@video_projects_api.route("/video-projects", methods=["GET"])
@require_auth
def list_projects():
    channel_id = request.args.get("channel_id", type=int)
    db = SessionLocal()
    try:
        q = (
            db.query(VideoProject)
            .join(Channel, Channel.id == VideoProject.channel_id)
            .filter(Channel.owner_user_id == g.current_user.id)
        )
        if channel_id:
            q = q.filter(VideoProject.channel_id == channel_id)
        rows = q.order_by(VideoProject.created_at.desc()).limit(100).all()
        return jsonify({"projects": [_project_dict(p) for p in rows]})
    finally:
        db.close()


@video_projects_api.route("/video-projects", methods=["POST"])
@require_auth
def create_project():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip()
    channel_id = data.get("channel_id")
    if not title:
        return jsonify({"error": "title is required"}), 400
    db = SessionLocal()
    try:
        c = _own_channel(db, int(channel_id or 0))
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        idea_id = data.get("idea_id")
        if idea_id:
            idea = db.query(ChannelIdea).filter_by(id=int(idea_id), channel_id=c.id).first()
            if not idea:
                return jsonify({"error": "Idea not found in this channel"}), 404
            idea.status = "converted"
        pillar = None
        pillar_id = data.get("content_pillar_id")
        if pillar_id:
            from app_models import ContentPillar
            pillar = db.query(ContentPillar).filter_by(id=int(pillar_id)).first()
            if not pillar:
                return jsonify({"error": "content_pillar_id does not exist"}), 400
            if c.niche_id and pillar.niche_id != c.niche_id:
                return jsonify({"error": "Pillar belongs to a different niche than the channel"}), 400
        from app_models import ContentNiche
        niche = db.query(ContentNiche).filter_by(id=c.niche_id).first() if c.niche_id else None
        snapshot = {
            "youtube_channel_id": c.youtube_channel_id,
            "channel_name": c.name,
            "niche_id": c.niche_id,
            "niche_name": niche.name if niche else (c.niche or None),
            "content_pillar_id": pillar.id if pillar else None,
            "content_pillar_name": pillar.name if pillar else None,
            "topic": str(data.get("topic") or "").strip() or None,
            "language": c.language,
            "target_audience": c.target_audience,
            "tone_of_voice": c.tone_of_voice or c.content_style,
            "visual_style": c.visual_style,
            "generation_profile_snapshot": {
                "default_voice": c.default_voice,
                "default_video_duration_seconds": c.default_video_duration_seconds,
                "default_visibility": c.default_visibility,
                "subtitle_template": c.subtitle_template_json,
                "snapshot_at": datetime.utcnow().isoformat(),
            },
        }
        p = VideoProject(
            channel_id=c.id,
            idea_id=int(idea_id) if idea_id else None,
            content_pillar_id=pillar.id if pillar else None,
            generation_profile_json=json.dumps(snapshot, ensure_ascii=False),
            title=title[:300],
            script_text=(str(data.get("script_text") or "").strip() or None),
            duration_target_seconds=int(c.default_video_duration_seconds or 45),
        )
        vm = str(data.get("voice_mode") or "").strip().lower()
        if vm:
            if vm not in VOICE_MODES:
                return jsonify({"error": f"voice_mode must be one of {sorted(VOICE_MODES)}"}), 400
            p.voice_mode = vm
        db.add(p)
        db.commit()
        db.refresh(p)
        return jsonify({"project": _project_dict(p, scenes=[])}), 201
    finally:
        db.close()


@video_projects_api.route("/video-projects/<int:project_id>", methods=["GET"])
@require_auth
def get_project(project_id: int):
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        scenes = (
            db.query(VideoScene).filter_by(project_id=p.id)
            .order_by(VideoScene.order_index.asc()).all()
        )
        jobs = (
            db.query(RenderJob).filter_by(project_id=p.id)
            .order_by(RenderJob.created_at.desc()).limit(10).all()
        )
        return jsonify({"project": _project_dict(p, scenes=scenes, jobs=jobs)})
    finally:
        db.close()


@video_projects_api.route("/video-projects/<int:project_id>", methods=["PATCH"])
@require_auth
def update_project(project_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        if "title" in data:
            title = str(data.get("title") or "").strip()
            if not title:
                return jsonify({"error": "title cannot be empty"}), 400
            p.title = title[:300]
        if "script_text" in data:
            p.script_text = str(data.get("script_text") or "").strip() or None
        if "voice_mode" in data:
            vm = str(data.get("voice_mode") or "").strip().lower()
            if vm not in VOICE_MODES:
                return jsonify({"error": f"voice_mode must be one of {sorted(VOICE_MODES)}"}), 400
            p.voice_mode = vm
        if "status" in data:
            st = str(data.get("status") or "").strip().lower()
            if st not in PROJECT_STATUSES:
                return jsonify({"error": f"status must be one of {sorted(PROJECT_STATUSES)}"}), 400
            p.status = st
        p.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(p)
        return jsonify({"project": _project_dict(p)})
    finally:
        db.close()


_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")


@video_projects_api.route("/video-projects/<int:project_id>/generate-script", methods=["POST"])
@require_auth
def generate_project_script(project_id: int):
    """Content Factory — station «Сценарий».

    Writes the script for a project from its idea/title with the AI script
    generator, so a project never opens with an empty script. After success the
    pipeline stops at the human checkpoint (state=needs_review) unless the
    channel has full autopilot enabled (state=done)."""
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        if (p.script_text or "").strip() and not data.get("replace"):
            return jsonify({"error": "Script already exists; pass replace=true to regenerate"}), 409
        topic = (p.title or "").strip()
        if not topic:
            return jsonify({"error": "Project has no idea to write about"}), 400
        ch = db.query(Channel).filter_by(id=p.channel_id).first()
        language = (getattr(ch, "language", None) or "ru")
        target_seconds = int(p.duration_target_seconds or getattr(ch, "default_video_duration_seconds", 45) or 45)
        style = (getattr(ch, "narration_style", None) or getattr(ch, "content_style", None) or "")
        # Channel persona (recurring narrator identity/values) — prepended to the
        # style so every video shares one authorial voice (authenticity signal).
        try:
            _gs = json.loads(getattr(ch, "generation_settings_json", None) or "{}")
            _persona = str(_gs.get("persona") or "").strip()
        except Exception:
            _persona = ""
        if _persona:
            style = (_persona + "\n" + style).strip()

        # Persist the resolved target + aspect on the project so every downstream
        # station (split-scenes, media, render, publish gate) agrees. Essential
        # for long-form, which those stations detect via duration_target_seconds.
        if not p.duration_target_seconds:
            p.duration_target_seconds = target_seconds
        _fmt = (getattr(ch, "default_video_format", "") or "").lower()
        if _fmt in ("16:9", "horizontal", "long", "longform", "long-form"):
            p.aspect_ratio = "16:9"
        db.commit()

        # CTA reserves ~4s of the target so main content + CTA stays in the band.
        import cta_generator as _cta
        cta_cfg = _cta.read_cta_settings(ch)
        cta_on = bool(cta_cfg.get("cta_enabled"))
        main_target = target_seconds
        if cta_on and target_seconds > (_cta.CTA_RESERVE_SECONDS + 8):
            main_target = int(round(target_seconds - _cta.CTA_RESERVE_SECONDS))

        p.pipeline_stage = "script"
        p.pipeline_state = "running"
        p.pipeline_error = None
        db.commit()

        import openai_quota_guard as _quotaguard
        try:
            from video_script_generator import LongformProviderBlockedError, generate as _generate_script
            # Hook-diversity history (Shorts only, this channel): last 50 or
            # last 14 days, whichever set is larger. See shorts_hook_diversity.py
            # — this only affects the opening 1-2 phrases, nothing else here.
            hook_recent_hooks: list[str] = []
            hook_recent_types: list[str] = []
            if main_target < 150:
                from datetime import timedelta as _hook_td
                _hook_cutoff = datetime.utcnow() - _hook_td(days=14)
                _hook_rows = (
                    db.query(VideoProject.script_text, VideoProject.hook_type, VideoProject.created_at)
                    .filter(VideoProject.channel_id == p.channel_id,
                            VideoProject.duration_target_seconds < 150,
                            VideoProject.script_text.isnot(None),
                            VideoProject.id != p.id)
                    .order_by(VideoProject.created_at.desc())
                    .limit(500)
                    .all()
                )
                _by_days = [r for r in _hook_rows if r.created_at and r.created_at >= _hook_cutoff]
                _by_count = _hook_rows[:50]
                _hook_history = _by_days if len(_by_days) > len(_by_count) else _by_count
                for _r in _hook_history:
                    _first_line = (_r.script_text or "").split("\n", 1)[0].strip()
                    if _first_line:
                        hook_recent_hooks.append(_first_line)
                    hook_recent_types.append(_r.hook_type)
            bundle = _generate_script(topic=topic, offer=None, language=language,
                                      target_seconds=main_target, style=style,
                                      recent_hooks=hook_recent_hooks, recent_types=hook_recent_types)
        except LongformProviderBlockedError as exc:
            # No safe long-form fallback exists -- block this project rather
            # than publish a low-quality short-style script padded to a
            # long-form duration. Does not touch any other project/job.
            p.pipeline_state = "blocked_external_provider"
            p.pipeline_error = str(exc)[:280]
            db.commit()
            _quotaguard.handle_quota_event(
                db, stage="script", project_id=p.id, channel_name=getattr(ch, "name", None),
                error_class="quota_billing", fallback_target="long-form blocked (no safe fallback)",
            )
            return jsonify({"error": "Генерация недоступна: закончилась квота OpenAI. "
                                     "Полноценный fallback для длинного видео небезопасен, проект остановлен.",
                            "pipeline_state": "blocked_external_provider"}), 503
        except Exception as exc:  # noqa: BLE001 — surface as a station error, don't 500
            p.pipeline_state = "error"
            p.pipeline_error = f"script: {str(exc)[:280]}"
            db.commit()
            return jsonify({"error": "Не удалось написать сценарий. Попробуйте ещё раз.",
                            "detail": str(exc)[:280], "pipeline_state": "error"}), 502

        if getattr(bundle, "used_fallback", False) and getattr(bundle, "openai_error_class", None) == "quota_billing":
            _quotaguard.handle_quota_event(
                db, stage="script", project_id=p.id, channel_name=getattr(ch, "name", None),
                error_class="quota_billing", fallback_target="Shorts diverse deterministic fallback",
            )
        elif not getattr(bundle, "used_fallback", False):
            _quotaguard.handle_recovery_event(db)

        phrases = [str(ph).strip() for ph in (getattr(bundle, "phrases", None) or []) if str(ph).strip()]
        script_text = "\n".join(phrases).strip()
        if not script_text:
            p.pipeline_state = "error"
            p.pipeline_error = "script: empty result"
            db.commit()
            return jsonify({"error": "Сгенерированный сценарий оказался пустым.",
                            "pipeline_state": "error"}), 502

        p.script_text = script_text
        p.hook_type = getattr(bundle, "hook_type", None)
        # --- final subscribe CTA (optional; never blocks the script station) ---
        if cta_on:
            try:
                window = int(cta_cfg.get("cta_history_window") or 20)
                recent_rows = (db.query(VideoProject.cta_text, VideoProject.cta_type)
                               .filter(VideoProject.channel_id == p.channel_id,
                                       VideoProject.cta_text.isnot(None))
                               .order_by(VideoProject.id.desc()).limit(window).all())
                recent_ctas = [r[0] for r in recent_rows if r[0]]
                recent_types = [r[1] for r in recent_rows if r[1]]
                cta = _cta.generate_cta({
                    "language": language,
                    "niche": getattr(ch, "niche", None),
                    "project_title": p.title,
                    "topic": topic,
                    "last_line": phrases[-1] if phrases else "",
                    "channel_promise": (cta_cfg.get("cta_fallback_text") or ""),
                    "recent_ctas": recent_ctas,
                    "recent_types": recent_types,
                    "min_words": cta_cfg.get("cta_min_words"),
                    "max_words": cta_cfg.get("cta_max_words"),
                    "max_same_type_streak": cta_cfg.get("cta_max_same_type_streak"),
                })
                p.cta_enabled = True
                p.cta_text = cta["text"]
                p.cta_type = cta["type"]
                p.cta_language = cta["language"]
                p.cta_source = cta["source"]
                p.cta_fallback_used = bool(cta["fallback_used"])
            except Exception as exc:  # CTA is optional — log and continue
                p.cta_enabled = True
                p.cta_source = "fallback"
                p.pipeline_error = None
                logging.getLogger("factory.cta").warning("cta gen failed: %s", str(exc)[:200])
        else:
            p.cta_enabled = False
            p.cta_source = "disabled"

        autopilot = bool(getattr(ch, "autopilot_enabled", False))
        p.pipeline_stage = "script"
        p.pipeline_state = "done" if autopilot else "needs_review"
        db.commit()
        db.refresh(p)
        return jsonify({
            "script_text": p.script_text,
            "title": getattr(bundle, "title", None) or p.title,
            "pipeline_stage": p.pipeline_stage,
            "pipeline_state": p.pipeline_state,
            "checkpoint": (not autopilot),
        }), 200
    finally:
        db.close()


@video_projects_api.route("/video-projects/<int:project_id>/split-scenes", methods=["POST"])
@require_auth
def split_scenes(project_id: int):
    """Split script_text into scenes by sentences (~2 sentences / scene).
    Refuses to overwrite existing scenes unless {"replace": true}."""
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        script = (p.script_text or "").strip()
        if not script:
            return jsonify({"error": "Project has no script_text"}), 400
        existing = db.query(VideoScene).filter_by(project_id=p.id).count()
        if existing and not data.get("replace"):
            return jsonify({"error": "Scenes already exist; pass replace=true to overwrite"}), 409
        if existing:
            db.query(VideoScene).filter_by(project_id=p.id).delete()
        sentences = [s.strip() for s in _SENTENCE_RE.split(script) if s.strip()]
        if not sentences:
            return jsonify({"error": "Could not split script into sentences"}), 400
        # Long-form (calm narration) → fewer, longer scenes; Shorts stay punchy.
        _tgt = int(p.duration_target_seconds or 0)
        per_scene = 4 if _tgt >= 150 else 2
        chunks = [" ".join(sentences[i:i + per_scene]) for i in range(0, len(sentences), per_scene)]
        # ~2.5 words/second speaking pace, clamped to sane shot lengths.
        scenes = []
        for idx, chunk in enumerate(chunks):
            words = max(1, len(chunk.split()))
            dur = max(2.0, min(12.0, round(words / 2.5, 1)))
            s = VideoScene(
                project_id=p.id,
                order_index=idx,
                voiceover_text=chunk,
                on_screen_text=chunk if len(chunk) <= 90 else None,
                estimated_duration=dur,
                status="draft",
            )
            db.add(s)
            scenes.append(s)
        # Long-form: the last content beat is the authorial synthesis (the script
        # generator writes it there) — mark it so the render shows an insight card.
        if _tgt >= 150 and scenes:
            scenes[-1].visual_type = "insight"
        # Append the final subscribe CTA as its own scene, so it flows through
        # the same TTS / subtitles / render path (voiced last, own subtitle cue).
        if getattr(p, "cta_enabled", False) and (p.cta_text or "").strip():
            import cta_generator as _cta
            db.add(VideoScene(
                project_id=p.id,
                order_index=len(scenes),
                voiceover_text=p.cta_text.strip(),
                on_screen_text=None,
                estimated_duration=_cta.CTA_RESERVE_SECONDS,
                status="draft",
                is_cta=True,
            ))
        db.commit()
        scenes = (db.query(VideoScene).filter_by(project_id=p.id)
                  .order_by(VideoScene.order_index.asc()).all())
        for s in scenes:
            db.refresh(s)
        return jsonify({"scenes": [_scene_dict(s) for s in scenes]}), 201
    finally:
        db.close()


# ---------------------------------------------------------------- scenes

@video_projects_api.route("/video-projects/<int:project_id>/scenes", methods=["POST"])
@require_auth
def create_scene(project_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        max_order = (
            db.query(VideoScene).filter_by(project_id=p.id)
            .order_by(VideoScene.order_index.desc()).first()
        )
        s = VideoScene(
            project_id=p.id,
            order_index=(max_order.order_index + 1) if max_order else 0,
            voiceover_text=str(data.get("voiceover_text") or "").strip() or None,
            on_screen_text=str(data.get("on_screen_text") or "").strip() or None,
            estimated_duration=float(data.get("estimated_duration") or 4.0),
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        return jsonify({"scene": _scene_dict(s)}), 201
    finally:
        db.close()


def _own_scene(db, scene_id: int) -> VideoScene | None:
    return (
        db.query(VideoScene)
        .join(VideoProject, VideoProject.id == VideoScene.project_id)
        .join(Channel, Channel.id == VideoProject.channel_id)
        .filter(VideoScene.id == scene_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


@video_projects_api.route("/scenes/<int:scene_id>", methods=["PATCH"])
@require_auth
def update_scene(scene_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        s = _own_scene(db, scene_id)
        if not s:
            return jsonify({"error": "Scene not found"}), 404
        for f in ("voiceover_text", "on_screen_text", "visual_prompt", "stock_search_query", "transition"):
            if f in data:
                setattr(s, f, str(data.get(f) or "").strip() or None)
        if "estimated_duration" in data:
            try:
                dur = float(data["estimated_duration"])
            except (TypeError, ValueError):
                return jsonify({"error": "estimated_duration must be a number"}), 400
            if not (0.8 <= dur <= 40.0):
                return jsonify({"error": "estimated_duration must be between 0.8 and 40"}), 400
            s.estimated_duration = dur
        if "order_index" in data:
            try:
                s.order_index = int(data["order_index"])
            except (TypeError, ValueError):
                return jsonify({"error": "order_index must be an integer"}), 400
        if "selected_media_path" in data:
            raw = str(data.get("selected_media_path") or "").strip()
            if raw:
                resolved = _media_path_ok(raw)
                if not resolved or not resolved.exists():
                    return jsonify({"error": "selected_media_path is outside allowed media directories or does not exist"}), 400
                s.selected_media_path = str(resolved)
                s.status = "ready"
            else:
                s.selected_media_path = None
        db.commit()
        db.refresh(s)
        return jsonify({"scene": _scene_dict(s)})
    finally:
        db.close()


@video_projects_api.route("/scenes/<int:scene_id>", methods=["DELETE"])
@require_auth
def delete_scene(scene_id: int):
    db = SessionLocal()
    try:
        s = _own_scene(db, scene_id)
        if not s:
            return jsonify({"error": "Scene not found"}), 404
        db.delete(s)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


def _generate_fixture_clip(s: "VideoScene") -> tuple[str | None, str | None]:
    """Generate (if needed) a local synthetic placeholder clip for a scene, no
    stock API involved. Returns (path, None) on success or (None, error)."""
    fixtures_dir = (settings.CACHE_DIR / "fixture_clips").resolve()
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    colors = ["0x1a1a2e", "0x16213e", "0x0f3460", "0x1f1d36", "0x2a2438"]
    color = colors[s.order_index % len(colors)]
    dur = max(2.0, min(15.0, float(s.estimated_duration or 4.0)))
    out = fixtures_dir / f"fixture_{color[2:]}_{int(dur * 10)}.mp4"
    if not out.exists():
        proc = subprocess.run(
            [settings.FFMPEG_BIN, "-y", "-f", "lavfi",
             "-i", f"color=c={color}:s=640x1136:d={dur}:r=30",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            return None, f"ffmpeg fixture generation failed: {(proc.stderr or '')[:300]}"
    return str(out), None


@video_projects_api.route("/scenes/<int:scene_id>/fixture-media", methods=["POST"])
@require_auth
def scene_fixture_media(scene_id: int):
    """Generate a local synthetic placeholder clip for a scene (no stock API).
    Honest fixture: visual_type is set to 'fixture' so the UI can label it."""
    db = SessionLocal()
    try:
        s = _own_scene(db, scene_id)
        if not s:
            return jsonify({"error": "Scene not found"}), 404
        out, err = _generate_fixture_clip(s)
        if err:
            return jsonify({"error": err}), 500
        s.selected_media_path = out
        s.visual_type = "fixture"
        s.status = "ready"
        db.commit()
        db.refresh(s)
        return jsonify({"scene": _scene_dict(s)})
    finally:
        db.close()


# ---------------------------------------------------------------- render jobs

def _build_srt(scenes) -> str:
    def ts(t: float) -> str:
        ms = int(round(t * 1000))
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        sec, ms = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    lines = []
    cursor = 0.0
    n = 0
    for s in scenes:
        text = (s.on_screen_text or s.voiceover_text or "").strip()
        dur = float(s.estimated_duration or 4.0)
        if text:
            n += 1
            lines.append(f"{n}\n{ts(cursor + 0.1)} --> {ts(cursor + dur - 0.1)}\n{text}\n")
        cursor += dur
    return "\n".join(lines)


def _set_job(db, job_id: int, **fields):
    j = db.query(RenderJob).filter_by(id=job_id).first()
    if j is None:
        return None
    for k, v in fields.items():
        setattr(j, k, v)
    db.commit()
    return j


def run_render_job(job_id: int) -> None:
    """Executes one render job. Progress values mark real stages:
    5 acquired, 15 audio ready, 30 subtitles ready, 40 rendering, 100 done."""
    db = SessionLocal()
    try:
        job = db.query(RenderJob).filter_by(id=job_id).first()
        if not job or job.status == "cancelled":
            return
        if job.status not in JOB_ACTIVE:
            return
        job.status = "processing"
        job.attempts = (job.attempts or 0) + 1
        job.started_at = datetime.utcnow()
        job.worker = f"{socket.gethostname()}:{threading.get_ident()}"
        job.progress = 0
        job.error = None
        db.commit()
        project = db.query(VideoProject).filter_by(id=job.project_id).first()
        scenes = (
            db.query(VideoScene).filter_by(project_id=job.project_id)
            .order_by(VideoScene.order_index.asc()).all()
        )
        try:
            if not project:
                raise RuntimeError("project_missing")
            if not scenes:
                raise RuntimeError("no_scenes: add scenes before rendering")
            missing = [s.order_index for s in scenes if not s.selected_media_path or not Path(s.selected_media_path).exists()]
            if missing:
                raise RuntimeError(f"scenes_missing_media: scenes {missing} have no attached media file")

            with _RENDER_SEMAPHORE:
                _set_job(db, job_id, progress=5)
                total_dur = sum(float(s.estimated_duration or 4.0) for s in scenes)

                # --- voiceover ---
                audio_dir = settings.OUTPUT_AUDIO_DIR
                audio_dir.mkdir(parents=True, exist_ok=True)
                if project.voice_mode == "file":
                    if not project.voiceover_path or not Path(project.voiceover_path).exists():
                        raise RuntimeError("voiceover_file_missing: voice_mode=file but no voiceover_path")
                    voice_path = Path(project.voiceover_path)
                elif project.voice_mode == "silent":
                    voice_path = audio_dir / f"project_{project.id}_silence.wav"
                    proc = subprocess.run(
                        [settings.FFMPEG_BIN, "-y", "-f", "lavfi",
                         "-i", f"anullsrc=r=44100:cl=mono:d={total_dur:.2f}", str(voice_path)],
                        capture_output=True, text=True,
                    )
                    if proc.returncode != 0:
                        raise RuntimeError(f"silence_generation_failed: {(proc.stderr or '')[:300]}")
                else:  # tts
                    from video.tts import synthesize_voiceover
                    phrases = [(s.voiceover_text or "").strip() for s in scenes]
                    if not any(phrases):
                        raise RuntimeError("tts_no_text: scenes have no voiceover_text")
                    # 0.3s pause before the final CTA (same voice, natural break).
                    gap_before = [0.3 if getattr(s, "is_cta", False) else 0.0 for s in scenes]
                    # Clamp the combined voiceover (main + CTA) to the target so the
                    # finished Short stays inside the 27–33s publish band even with
                    # the appended CTA. TTS speeds up/pads to fit.
                    _ch = db.query(Channel).filter_by(id=project.channel_id).first()
                    _raw_tgt = float(project.duration_target_seconds
                                     or getattr(_ch, "default_video_duration_seconds", 0) or 0)
                    # Clamp only short-form to an exact target; long-form keeps its
                    # natural length (a wide publish band applies instead).
                    _tgt = _raw_tgt if (0 < _raw_tgt < 120) else None
                    voice_str, durations = synthesize_voiceover(
                        phrases, audio_dir, f"project_{project.id}",
                        # Unified with long-form's narrator (longform_pipeline.py)
                        # by explicit request -- same voice everywhere, regardless
                        # of any per-channel default_voice setting. That setting
                        # still exists and is editable in channel settings, but no
                        # longer affects what's actually synthesized here.
                        voice_name="onyx",
                        voice_tone="calm",
                        instructions=("Читай спокойно, тепло и размеренно, как опытный "
                                      "рассказчик-документалист. Естественные паузы между "
                                      "мыслями, живая интонация, без спешки и без монотонности."),
                        gap_before=gap_before,
                        target_total_seconds=_tgt,
                    )
                    voice_path = Path(voice_str)
                    for s, d in zip(scenes, durations):
                        if d and d > 0:
                            s.actual_duration = float(d)
                            s.estimated_duration = float(d)
                            if getattr(s, "is_cta", False):
                                # slot includes the 0.3s pause; spoken audio is the rest
                                project.cta_audio_duration_seconds = round(max(0.1, float(d) - 0.3), 2)
                    db.commit()
                _set_job(db, job_id, progress=15)

                # --- subtitles (professional ASS, safe-zone, smart splitting) ---
                from subtitle_builder import build_cues, write_ass
                subs_dir = settings.OUTPUT_SUBTITLES_DIR
                subs_dir.mkdir(parents=True, exist_ok=True)
                cursor = 0.0
                cue_scenes = []
                for s in scenes:
                    sdur = float(s.estimated_duration or 4.0)
                    c_start, c_dur = cursor, sdur
                    if getattr(s, "is_cta", False):
                        # CTA subtitle starts after the 0.3s pause, with the speech
                        c_start, c_dur = cursor + 0.3, max(0.1, sdur - 0.3)
                    cue_scenes.append({
                        "text": (s.on_screen_text or s.voiceover_text or "").strip(),
                        "start": c_start,
                        "duration": c_dur,
                    })
                    cursor += sdur
                cues = build_cues(cue_scenes)
                ass_path = subs_dir / f"project_{project.id}.ass"
                if cues:
                    write_ass(cues, ass_path)
                # Optional visual CTA badge: a positioned libass line over the CTA
                # window (Cyrillic-safe, top-center, clear of bottom subtitles).
                # Non-blocking: never fails the render.
                try:
                    import cta_generator as _cta
                    _ccfg = _cta.read_cta_settings(_channel_for_cta := db.query(Channel).filter_by(id=project.channel_id).first())
                    cta_scene = next((s for s in scenes if getattr(s, "is_cta", False)), None)
                    if cues and cta_scene and _ccfg.get("cta_visual_enabled"):
                        st = sum(float(x.estimated_duration or 4.0) for x in scenes
                                 if x.order_index < cta_scene.order_index) + 0.3
                        en = st + max(0.1, float(cta_scene.estimated_duration or 4.0) - 0.3)
                        def _ass_t(t):
                            h = int(t // 3600); m = int((t % 3600) // 60); s2 = t % 60
                            return f"{h}:{m:02d}:{s2:05.2f}"
                        label = {"ru": "Подпишись", "en": "Subscribe", "uk": "Підпишись"}.get(
                            (project.cta_language or "ru"), "Подпишись")
                        with open(ass_path, "a", encoding="utf-8") as _fh:
                            _fh.write(f"Dialogue: 0,{_ass_t(st)},{_ass_t(en)},Default,,0,0,0,,"
                                      f"{{\\an8\\fs44\\bord3\\shad1}}{label}\n")
                except Exception:
                    pass
                _set_job(db, job_id, progress=30)

                # --- footage segmentation with repeat protection ---
                from footage_library import (
                    commit_usage, register_asset,
                    release_job_reservations, segment_plan,
                )
                clips = []
                timeline = []
                used_asset_ids: set[int] = set()
                used_hashes: set[str] = set()
                t_cursor = 0.0
                seg_index = 0
                _channel = db.query(Channel).filter_by(id=project.channel_id).first()
                _niche = None
                _pillar = None
                try:
                    from app_models import ContentNiche, ContentPillar
                    if _channel and _channel.niche_id:
                        _niche = db.query(ContentNiche).filter_by(id=_channel.niche_id).first()
                    if project.content_pillar_id:
                        _pillar = db.query(ContentPillar).filter_by(id=project.content_pillar_id).first()
                except Exception:
                    pass
                from visual_validation import build_visual_intent
                for s in scenes:
                    sdur = float(s.estimated_duration or 4.0)
                    plan = segment_plan(sdur)
                    scene_query = (s.stock_search_query or s.visual_prompt or "").strip()
                    scene_intent = build_visual_intent(
                        scene_text=(s.voiceover_text or ""),
                        niche_slug=(_niche.slug if _niche else ""),
                        pillar={
                            "slug": _pillar.slug, "name": _pillar.name,
                            "visual_keywords": _pillar.visual_keywords,
                            "forbidden_visual_keywords": _pillar.forbidden_visual_keywords,
                        } if _pillar else None,
                        channel_visual_style=(_channel.visual_style if _channel else ""),
                    )
                    # register the scene's primary media in the library
                    primary_meta = json.loads(s.media_meta_json) if s.media_meta_json else {}
                    primary_asset = register_asset(
                        db,
                        provider=primary_meta.get("provider") or ("local" if s.visual_type == "fixture" else "manual"),
                        provider_asset_id=str(primary_meta.get("video_id") or Path(s.selected_media_path).name),
                        local_path=Path(s.selected_media_path),
                        download_url=primary_meta.get("preview_url") or "",
                        original_url=primary_meta.get("page_url") or "",
                        search_query=scene_query,
                        author=primary_meta.get("author") or "",
                        license_note=primary_meta.get("license") or "",
                    )
                    db.commit()
                    for i, seg_dur in enumerate(plan):
                        chosen = None
                        reuse_reason = None
                        search_stats = {}
                        if i == 0 and primary_asset.id not in used_asset_ids and (primary_asset.file_hash or "") not in used_hashes:
                            chosen = primary_asset
                        else:
                            from footage_library import acquire_segment_asset
                            chosen, search_stats = acquire_segment_asset(
                                db, query=scene_query, channel_id=project.channel_id,
                                project_id=project.id, job_id=job_id,
                                min_duration=seg_dur,
                                used_asset_ids=used_asset_ids,
                                used_hashes=used_hashes,
                                allow_network=not settings.USE_MOCK_PROVIDERS,
                                visual_intent=scene_intent,
                            )
                            if chosen and search_stats.get("reuse_was_unavoidable"):
                                reuse_reason = "cooldown_reuse_after_exhausted_search"
                            if chosen is None:
                                # absolute last resort: repeat scene primary
                                # (only after the whole search budget ran dry)
                                chosen = primary_asset
                                reuse_reason = "insufficient_unique_candidates_after_exhausted_search"
                                search_stats["reuse_was_unavoidable"] = True
                        used_asset_ids.add(chosen.id)
                        if chosen.file_hash:
                            used_hashes.add(chosen.file_hash)
                        motion = "in" if seg_index % 2 == 0 else "out"
                        clips.append({
                            "clip_path": chosen.local_path,
                            "duration_target": seg_dur,
                            "motion": motion,
                        })
                        timeline.append({
                            "segment": seg_index,
                            "scene_id": s.id,
                            "start": round(t_cursor, 2),
                            "duration": seg_dur,
                            "asset_id": chosen.id,
                            "provider_asset_id": chosen.provider_asset_id,
                            "file_hash": (chosen.file_hash or "")[:12],
                            "motion": motion,
                            "footage_reuse_reason": reuse_reason,
                            "footage_reuse_age_days": (
                                (datetime.utcnow() - chosen.last_used_at).days
                                if reuse_reason and chosen.last_used_at else None
                            ),
                            "footage_candidate_count": search_stats.get("candidates_examined", 0),
                            "search_queries_attempted": search_stats.get("search_queries_attempted", 0),
                            "pages_attempted": search_stats.get("pages_attempted", 0),
                            "candidates_examined": search_stats.get("candidates_examined", 0),
                            "candidates_rejected_cooldown": search_stats.get("candidates_rejected_cooldown", 0),
                            "candidates_rejected_duplicate": search_stats.get("candidates_rejected_duplicate", 0),
                            "reuse_was_unavoidable": search_stats.get("reuse_was_unavoidable", False),
                            "candidates_rejected_visual": search_stats.get("candidates_rejected_visual", 0),
                            "visual_checks": search_stats.get("visual_checks", 0),
                            "visual_degraded": search_stats.get("visual_degraded", False),
                            "source": search_stats.get("source"),
                        })
                        t_cursor += seg_dur
                        seg_index += 1

                # --- render ---
                from video.render.render_video import render_video
                out_rel = f"output/videos/project_{project.id}_job_{job.id}.mp4"
                out_abs = settings.BASE_DIR / out_rel
                _set_job(db, job_id, progress=40)
                try:
                    render_video(
                        clips=clips,
                        voiceover_path=str(voice_path),
                        subtitles_path=str(ass_path) if cues else None,
                        out_path=str(out_abs),
                        orientation="vertical" if project.aspect_ratio == "9:16" else "horizontal",
                        fps=30,
                        resolution="1080x1920" if project.aspect_ratio == "9:16" else "1920x1080",
                    )
                except Exception:
                    release_job_reservations(db, job_id)
                    raise
                if not out_abs.exists() or out_abs.stat().st_size < 10_000:
                    release_job_reservations(db, job_id)
                    raise RuntimeError("render_output_invalid: output file missing or too small")

                # --- quiet background music bed (never breaks render) ---
                try:
                    from music_mix import add_music_bed
                    add_music_bed(project, out_abs, db)
                except Exception:
                    project.music_status = "no_music"

                # --- commit footage usage history + manifest ---
                assets_by_id = {}
                for seg in timeline:
                    a = assets_by_id.get(seg["asset_id"])
                    if a is None:
                        from app_models import FootageAsset
                        a = db.query(FootageAsset).filter_by(id=seg["asset_id"]).first()
                        assets_by_id[seg["asset_id"]] = a
                    if a:
                        commit_usage(
                            db, asset=a, project_id=project.id,
                            channel_id=project.channel_id, scene_id=seg["scene_id"],
                            start_time=seg["start"], duration=seg["duration"],
                            search_query="", reuse_reason=seg["footage_reuse_reason"],
                        )
                release_job_reservations(db, job_id)
                manifest_path = settings.OUTPUT_MANIFESTS_DIR / f"project_{project.id}_job_{job.id}.json"
                manifest_path.parent.mkdir(parents=True, exist_ok=True)
                manifest_path.write_text(
                    json.dumps({"timeline": timeline, "cues": len(cues)}, ensure_ascii=False, indent=1),
                    encoding="utf-8",
                )
                db.commit()

            job = _set_job(
                db, job_id, status="completed", progress=100,
                output_path=out_rel, finished_at=datetime.utcnow(),
            )
            from ai_pricing import record_cost
            record_cost(provider="local", model="ffmpeg", operation_type="render",
                        channel_id=project.channel_id, project_id=project.id,
                        video_seconds=sum(float(s.estimated_duration or 0) for s in scenes),
                        request_id=f"render:{job_id}", db=db)
            project.status = "rendered"
            project.output_path = out_rel
            project.error = None
            db.commit()
            # Content Factory: auto-continue the line render → AI Publisher.
            try:
                from auth import create_token
                _owner = db.query(Channel.owner_user_id).filter(Channel.id == project.channel_id).scalar()
                if _owner:
                    _enqueue_factory(project.id, create_token(_owner))
            except Exception:
                pass
        except Exception as exc:
            err = str(exc)[:1500]
            try:
                db.rollback()
            except Exception:
                pass
            try:
                from footage_library import release_job_reservations
                release_job_reservations(db, job_id)
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
            job = db.query(RenderJob).filter_by(id=job_id).first()
            if job and job.status != "cancelled":
                job.status = "failed"
                job.error = err
                job.finished_at = datetime.utcnow()
            if project:
                project.status = "failed"
                project.error = err
                project.pipeline_stage = "render"
                project.pipeline_state = "error"
                project.pipeline_error = f"Рендер: {err}"
            db.commit()
    finally:
        db.close()


def _enqueue_render(job_id: int):
    if settings.SYNC_JOBS:
        run_render_job(job_id)
        return "sync"
    try:
        from redis import Redis
        from rq import Queue
        redis_conn = Redis.from_url(settings.REDIS_URL)
        redis_conn.ping()
        Queue("render", connection=redis_conn).enqueue(run_render_job, job_id, job_timeout=1800)
        return "rq"
    except Exception:
        t = threading.Thread(target=run_render_job, args=(job_id,), daemon=True)
        t.start()
        return "thread"


@video_projects_api.route("/video-projects/<int:project_id>/render", methods=["POST"])
@require_auth
def start_render(project_id: int):
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        active = (
            db.query(RenderJob)
            .filter(RenderJob.project_id == p.id, RenderJob.status.in_(JOB_ACTIVE))
            .first()
        )
        if active:
            return jsonify({"error": "A render job is already active for this project", "job": _job_dict(active)}), 409
        scene_count = db.query(VideoScene).filter_by(project_id=p.id).count()
        if not scene_count:
            return jsonify({"error": "Project has no scenes"}), 400
        job = RenderJob(project_id=p.id, channel_id=p.channel_id, status="pending")
        p.status = "rendering"
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
        payload = _job_dict(job)
    finally:
        db.close()
    mode = _enqueue_render(job_id)
    payload["queue_mode"] = mode
    return jsonify({"job": payload}), 202


# ============================================================ Content Factory
# Pipeline orchestrator: drives a project script→scenes→media→render, honouring
# the human checkpoint after the script. The heavy work runs on the worker
# (factory_pipeline.run) which reuses the station endpoints above.

def _enqueue_factory(project_id: int, token: str) -> str:
    import factory_pipeline
    if settings.SYNC_JOBS:
        factory_pipeline.run(project_id, token)
        return "sync"
    try:
        from redis import Redis
        from rq import Queue
        redis_conn = Redis.from_url(settings.REDIS_URL)
        redis_conn.ping()
        Queue("render", connection=redis_conn).enqueue(
            factory_pipeline.run, project_id, token, job_timeout=1800)
        return "rq"
    except Exception:
        t = threading.Thread(target=factory_pipeline.run, args=(project_id, token), daemon=True)
        t.start()
        return "thread"


def _pipeline_state_dict(db, p) -> dict:
    ch = db.query(Channel).filter_by(id=p.channel_id).first()
    scenes = db.query(VideoScene).filter_by(project_id=p.id).all()
    n = len(scenes)
    with_media = sum(1 for s in scenes if s.selected_media_path)
    job = (db.query(RenderJob).filter_by(project_id=p.id)
           .order_by(RenderJob.created_at.desc()).first())
    has_script = bool((p.script_text or "").strip())
    stg, stt = (p.pipeline_stage or ""), (p.pipeline_state or "")

    def station(key, done, running=False):
        if stg == key and stt in ("error", "needs_review"):
            return stt
        if stg == key and stt == "running":
            return "running"
        return "done" if done else ("running" if running else "waiting")

    render_state = "waiting"
    if p.output_path:
        render_state = "done"
    elif job:
        js = (job.status or "").lower()
        if js in ("done", "completed", "success"):
            render_state = "done"
        elif js in ("failed", "error"):
            render_state = "error"
        elif js in JOB_ACTIVE:
            render_state = "running"

    pub = (db.query(Publication).filter_by(project_id=p.id)
           .order_by(Publication.id.desc()).first())
    publish_state = "waiting"
    if pub:
        ps = (pub.status or "").lower()
        publish_state = {"published": "done", "uploading": "running",
                         "failed": "error", "needs_review": "needs_review"}.get(ps, "waiting")
    has_meta = bool((p.youtube_meta_json or "").strip())
    stages = [
        {"key": "script", "name": "Сценарий",
         "state": station("script", has_script)},
        {"key": "scenes", "name": "Сцены",
         "state": station("scenes", n > 0)},
        {"key": "media", "name": "Медиа",
         "state": station("media", n > 0 and with_media == n)},
        {"key": "render", "name": "Рендер", "state": render_state},
        {"key": "ai_publisher", "name": "AI Publisher",
         "state": station("ai_publisher", has_meta)},
        {"key": "publish", "name": "Публикация", "state": publish_state},
    ]
    youtube_meta = None
    if has_meta:
        try:
            youtube_meta = json.loads(p.youtube_meta_json)
        except Exception:
            youtube_meta = None
    from factory_pipeline import effective_mode
    return {
        "youtube_meta": youtube_meta,
        "project_id": p.id, "title": p.title,
        "pipeline_stage": p.pipeline_stage, "pipeline_state": p.pipeline_state,
        "pipeline_error": p.pipeline_error,
        "stages": stages,
        "scenes_total": n, "scenes_with_media": with_media,
        "render_job": _job_dict(job) if job else None,
        "publishing_override": p.publishing_override,
        "channel_publishing_mode": (ch.publishing_mode if ch else "manual"),
        "effective_mode": effective_mode(p, ch),
        "publication_status": (pub.status if pub else None),
        "youtube_url": (pub.youtube_url if pub and pub.status == "published" else None),
    }


@video_projects_api.route("/video-projects/<int:project_id>/pipeline/state", methods=["GET"])
@require_auth
def pipeline_state(project_id: int):
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        return jsonify(_pipeline_state_dict(db, p))
    finally:
        db.close()


@video_projects_api.route("/video-projects/<int:project_id>/pipeline/approve", methods=["POST"])
@require_auth
def pipeline_approve(project_id: int):
    """Pass the script checkpoint and launch the rest of the line."""
    from auth import create_token
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        if not (p.script_text or "").strip():
            return jsonify({"error": "Сначала сгенерируйте сценарий"}), 400
        p.pipeline_stage = "script"
        p.pipeline_state = "done"
        p.pipeline_error = None
        db.commit()
        mode = _enqueue_factory(p.id, create_token(g.current_user.id))
        return jsonify({"ok": True, "queue_mode": mode}), 202
    finally:
        db.close()


@video_projects_api.route("/video-projects/<int:project_id>/pipeline/run", methods=["POST"])
@require_auth
def pipeline_run(project_id: int):
    """Advance the line as far as it can (stops at the checkpoint if the script
    isn't approved and the channel isn't on full autopilot)."""
    from auth import create_token
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        mode = _enqueue_factory(p.id, create_token(g.current_user.id))
        return jsonify({"ok": True, "queue_mode": mode}), 202
    finally:
        db.close()


@video_projects_api.route("/video-projects/<int:project_id>/pipeline/retry", methods=["POST"])
@require_auth
def pipeline_retry(project_id: int):
    """Retry the current (failed) station without recreating the video."""
    from auth import create_token
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        p.pipeline_error = None
        if (p.pipeline_state or "") == "error":
            p.pipeline_state = "running"
        db.commit()
        mode = _enqueue_factory(p.id, create_token(g.current_user.id))
        return jsonify({"ok": True, "queue_mode": mode}), 202
    finally:
        db.close()


@video_projects_api.route("/video-projects/<int:project_id>/publishing-override", methods=["POST"])
@require_auth
def set_publishing_override(project_id: int):
    """Per-video publishing override: null (use channel default) | manual | automatic."""
    data = request.get_json(silent=True) or {}
    raw = data.get("override")
    ov = (str(raw).strip().lower() if raw not in (None, "", "default") else None)
    if ov not in (None, "manual", "automatic"):
        return jsonify({"error": "override must be null, 'manual' or 'automatic'"}), 400
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        p.publishing_override = ov
        db.commit()
        return jsonify({"project_id": p.id, "publishing_override": ov})
    finally:
        db.close()


@video_projects_api.route("/video-projects/<int:project_id>/ai-publisher", methods=["POST"])
@require_auth
def ai_publisher_run(project_id: int):
    """Station «AI Publisher»: prepare YouTube metadata (title/description
    alternatives, tags, hashtags, pinned comment, privacy) + a thumbnail from
    the best frame. Manual → stops at needs_review; automatic → marks done."""
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        ch = db.query(Channel).filter_by(id=p.channel_id).first()
        if not (p.script_text or "").strip():
            return jsonify({"error": "Нет сценария — сначала пройдите станцию «Сценарий»."}), 400
        p.pipeline_stage = "ai_publisher"
        p.pipeline_state = "running"
        p.pipeline_error = None
        db.commit()
        import ai_publisher
        import factory_pipeline
        try:
            pkg = ai_publisher.generate_publish_package(
                topic=p.title, script_text=(p.script_text or ""),
                language=(getattr(ch, "language", None) or "ru"),
                style=(getattr(ch, "narration_style", None) or getattr(ch, "content_style", None) or ""),
                niche=(getattr(ch, "niche", None) or ""),
                privacy=(getattr(ch, "default_visibility", None) or "public"),
            )
        except Exception as exc:  # noqa: BLE001
            p.pipeline_state = "error"
            p.pipeline_error = f"ai_publisher: {str(exc)[:280]}"
            db.commit()
            return jsonify({"error": "Не удалось подготовить публикацию.", "detail": str(exc)[:280]}), 502
        if p.output_path:
            try:
                thumb = ai_publisher.build_thumbnail(p.output_path, p.id)
                if thumb:
                    pkg["thumbnail"] = thumb
            except Exception:
                pass
        p.youtube_meta_json = json.dumps(pkg, ensure_ascii=False)
        mode = factory_pipeline.effective_mode(p, ch)
        p.pipeline_stage = "ai_publisher"
        p.pipeline_state = "done" if mode == "automatic" else "needs_review"
        db.commit()
        db.refresh(p)
        return jsonify({"meta": pkg, "effective_mode": mode,
                        "pipeline_stage": p.pipeline_stage, "pipeline_state": p.pipeline_state}), 200
    finally:
        db.close()


@video_projects_api.route("/video-projects/<int:project_id>/ai-publisher/save", methods=["POST"])
@require_auth
def ai_publisher_save(project_id: int):
    """Persist the user's edits to the AI Publisher package (selection + fields)."""
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        if not (p.youtube_meta_json or "").strip():
            return jsonify({"error": "Нет метаданных — сначала запустите AI Publisher."}), 400
        try:
            meta = json.loads(p.youtube_meta_json)
        except Exception:
            meta = {}
        if isinstance(data.get("title_options"), list):
            opts = [str(x)[:95] for x in data["title_options"] if str(x).strip()][:6]
            if opts:
                meta["title_options"] = opts
        if isinstance(data.get("description_options"), list):
            opts = [str(x)[:4900] for x in data["description_options"] if str(x).strip()][:4]
            if opts:
                meta["description_options"] = opts
        if "selected_title" in data:
            meta["selected_title"] = max(0, min(int(data.get("selected_title") or 0), len(meta.get("title_options", [1])) - 1))
        if "selected_description" in data:
            meta["selected_description"] = max(0, min(int(data.get("selected_description") or 0), len(meta.get("description_options", [1])) - 1))
        for k in ("tags", "hashtags"):
            if isinstance(data.get(k), list):
                meta[k] = [str(x).strip() for x in data[k] if str(x).strip()][:20]
        for k in ("pinned_comment", "overlay_text", "privacy"):
            if k in data:
                meta[k] = str(data.get(k) or "").strip()
        p.youtube_meta_json = json.dumps(meta, ensure_ascii=False)
        db.commit()
        return jsonify({"ok": True, "meta": meta})
    finally:
        db.close()


@video_projects_api.route("/render-jobs", methods=["GET"])
@require_auth
def list_render_jobs():
    db = SessionLocal()
    try:
        q = (
            db.query(RenderJob)
            .join(Channel, Channel.id == RenderJob.channel_id)
            .filter(Channel.owner_user_id == g.current_user.id)
        )
        status = (request.args.get("status") or "").strip().lower()
        if status:
            q = q.filter(RenderJob.status == status)
        rows = q.order_by(RenderJob.created_at.desc()).limit(100).all()
        return jsonify({"jobs": [_job_dict(j) for j in rows]})
    finally:
        db.close()


def _own_job(db, job_id: int) -> RenderJob | None:
    return (
        db.query(RenderJob)
        .join(Channel, Channel.id == RenderJob.channel_id)
        .filter(RenderJob.id == job_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


@video_projects_api.route("/render-jobs/<int:job_id>", methods=["GET"])
@require_auth
def get_render_job(job_id: int):
    db = SessionLocal()
    try:
        j = _own_job(db, job_id)
        if not j:
            return jsonify({"error": "Job not found"}), 404
        return jsonify({"job": _job_dict(j)})
    finally:
        db.close()


@video_projects_api.route("/render-jobs/<int:job_id>/retry", methods=["POST"])
@require_auth
def retry_render_job(job_id: int):
    db = SessionLocal()
    try:
        j = _own_job(db, job_id)
        if not j:
            return jsonify({"error": "Job not found"}), 404
        if j.status != "failed":
            return jsonify({"error": f"Only failed jobs can be retried (status={j.status})"}), 409
        if j.attempts >= j.max_attempts:
            return jsonify({"error": f"Max attempts reached ({j.attempts}/{j.max_attempts})"}), 409
        j.status = "pending"
        j.progress = 0
        j.error = None
        j.finished_at = None
        db.commit()
        jid = j.id
        payload = _job_dict(j)
    finally:
        db.close()
    mode = _enqueue_render(jid)
    payload["queue_mode"] = mode
    return jsonify({"job": payload}), 202


@video_projects_api.route("/render-jobs/<int:job_id>/cancel", methods=["POST"])
@require_auth
def cancel_render_job(job_id: int):
    db = SessionLocal()
    try:
        j = _own_job(db, job_id)
        if not j:
            return jsonify({"error": "Job not found"}), 404
        if j.status != "pending":
            return jsonify({"error": f"Only pending jobs can be cancelled (status={j.status})"}), 409
        j.status = "cancelled"
        j.finished_at = datetime.utcnow()
        db.commit()
        return jsonify({"job": _job_dict(j)})
    finally:
        db.close()


# ---------------------------------------------------------------- TTS

TTS_VOICES = [
    {"provider": "edge", "name": "ru-RU-DmitryNeural", "label": "Дмитрий (муж., Edge)"},
    {"provider": "edge", "name": "ru-RU-SvetlanaNeural", "label": "Светлана (жен., Edge)"},
    {"provider": "openai", "name": "alloy", "label": "Alloy (OpenAI)"},
    {"provider": "openai", "name": "onyx", "label": "Onyx (муж., OpenAI)"},
    {"provider": "openai", "name": "nova", "label": "Nova (жен., OpenAI)"},
]


def _tts_provider_for_voice(voice_name: str) -> str:
    for v in TTS_VOICES:
        if v["name"] == voice_name:
            return v["provider"]
    return "edge" if "neural" in (voice_name or "").lower() else "openai"


def _tts_preflight(voice_name: str) -> str | None:
    """Synthesize a tiny phrase with the *specific* provider (no silent fallback).
    Returns None on success or an honest error string."""
    import tempfile
    from video.tts import _tts_phrase_edge, _tts_phrase_openai, probe_duration

    provider = _tts_provider_for_voice(voice_name)
    try:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "preflight.mp3"
            if provider == "edge":
                _tts_phrase_edge("Проверка голоса.", p, voice_name=voice_name)
            else:
                import os as _os
                if not (_os.getenv("OPENAI_API_KEY") or "").strip():
                    return "OPENAI_API_KEY is not configured"
                _tts_phrase_openai("Проверка голоса.", p, voice_name=voice_name)
            if probe_duration(str(p)) < 0.2:
                return f"{provider} TTS produced empty audio"
    except Exception as exc:
        return f"{provider} TTS unavailable: {str(exc)[:300]}"
    return None


@video_projects_api.route("/tts/voices", methods=["GET"])
@require_auth
def tts_voices():
    import os as _os
    openai_ready = bool((_os.getenv("OPENAI_API_KEY") or "").strip())
    voices = [
        {**v, "requires_key": v["provider"] == "openai" and not openai_ready}
        for v in TTS_VOICES
    ]
    return jsonify({"voices": voices, "default": "ru-RU-DmitryNeural"})


@video_projects_api.route("/tts/preview", methods=["POST"])
@require_auth
def tts_preview():
    from video.tts import _tts_phrase_edge, _tts_phrase_openai, probe_duration

    data = request.get_json(silent=True) or {}
    voice_name = str(data.get("voice_name") or "ru-RU-DmitryNeural").strip()
    text = str(data.get("text") or "Тайны древних символов ждут вас.").strip()[:200]
    provider = _tts_provider_for_voice(voice_name)
    out_dir = settings.OUTPUT_AUDIO_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_voice = re.sub(r"[^A-Za-z0-9_-]", "", voice_name)[:60]
    out = out_dir / f"tts_preview_{safe_voice}.mp3"
    try:
        if provider == "edge":
            _tts_phrase_edge(text, out, voice_name=voice_name)
        else:
            import os as _os
            if not (_os.getenv("OPENAI_API_KEY") or "").strip():
                return jsonify({"error": "OPENAI_API_KEY is not configured"}), 503
            _tts_phrase_openai(text, out, voice_name=voice_name)
    except Exception as exc:
        return jsonify({"error": f"{provider} TTS failed: {str(exc)[:300]}"}), 502
    duration = probe_duration(str(out))
    if duration < 0.2:
        return jsonify({"error": f"{provider} TTS produced empty audio"}), 502
    rel = out.relative_to(settings.BASE_DIR)
    return jsonify({
        "provider": provider,
        "voice": voice_name,
        "duration": round(duration, 2),
        "audio_url": f"/api/media/{rel.as_posix()}",
    })


@video_projects_api.route("/video-projects/<int:project_id>/tts", methods=["POST"])
@require_auth
def generate_project_tts(project_id: int):
    """Explicit user action: synthesize the full voiceover per scene, update
    real scene durations, save the file and switch voice_mode to 'file'."""
    from video.tts import probe_duration, synthesize_voiceover

    data = request.get_json(silent=True) or {}
    voice_name = str(data.get("voice_name") or "ru-RU-DmitryNeural").strip()
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        scenes = (
            db.query(VideoScene).filter_by(project_id=p.id)
            .order_by(VideoScene.order_index.asc()).all()
        )
        phrases = [(s.voiceover_text or "").strip() for s in scenes]
        if not any(phrases):
            return jsonify({"error": "Scenes have no voiceover_text"}), 400

        err = _tts_preflight(voice_name)
        if err:
            return jsonify({"error": err}), 502

        out_dir = settings.OUTPUT_AUDIO_DIR
        try:
            voice_str, durations = synthesize_voiceover(
                phrases, out_dir, f"project_{p.id}", voice_name=voice_name,
            )
        except Exception as exc:
            return jsonify({"error": f"TTS failed: {str(exc)[:400]}"}), 502
        total = probe_duration(voice_str)
        if total < 0.5:
            return jsonify({"error": "TTS produced empty audio"}), 502
        from ai_pricing import record_cost
        provider = _tts_provider_for_voice(voice_name)
        chars = sum(len(ph) for ph in phrases)
        record_cost(
            provider=provider,
            model="edge-tts" if provider == "edge" else "gpt-4o-mini-tts",
            operation_type="TTS",
            channel_id=p.channel_id, project_id=p.id,
            audio_characters=chars,
            input_units=float(chars) if provider == "openai" else None,
            request_id=f"tts:{p.id}:{voice_name}:{chars}",
            db=db,
        )
        for s, d in zip(scenes, durations):
            if d and d > 0:
                s.actual_duration = float(d)
                s.estimated_duration = round(float(d), 2)
        p.voiceover_path = voice_str
        p.voice_mode = "file"
        p.updated_at = datetime.utcnow()
        db.commit()
        rel = Path(voice_str).relative_to(settings.BASE_DIR)
        return jsonify({
            "voiceover_path": voice_str,
            "audio_url": f"/api/media/{rel.as_posix()}",
            "voice": voice_name,
            "total_duration": round(total, 2),
            "scene_durations": [round(float(d), 2) for d in durations],
        })
    finally:
        db.close()


# ---------------------------------------------------------------- stock media

def _stock_result_dict(r) -> dict:
    return {
        "provider": r.provider,
        "video_id": str(r.video_id),
        "duration": r.duration,
        "width": r.width,
        "height": r.height,
        "orientation": r.orientation,
        "page_url": r.page_url,
        "preview_url": r.download_url,
        "author": r.author,
        "title": r.title,
        "license": "Pexels License (free to use)" if r.provider == "pexels" else r.provider,
    }


def _pexels_search(query: str, page: int = 1, limit: int = 8):
    """Despite the name (kept for compatibility with existing call sites),
    this searches Pexels AND Pixabay together and returns the merged pool --
    see media_diversity.search_both_providers. Previously Pixabay was only
    ever reached if Pexels raised an exception, which in practice meant it
    was almost never used."""
    from media_diversity import search_both_providers

    results = search_both_providers(
        query, orientation="vertical", min_duration=3, max_duration=60,
        limit=limit, page=page,
    )
    if not results:
        results = search_both_providers(
            query, orientation="horizontal", min_duration=3, max_duration=60,
            limit=limit, page=page,
        )
    return results[:limit]


def _pexels_search_diverse(query: str, *, limit: int = 12, exclude_ids: set | None = None):
    """Query variants + randomized pagination so we don't always consume the
    first page of the same search. Dedupes by video_id."""
    import random as _random
    from footage_library import query_variants

    exclude = {str(x) for x in (exclude_ids or set())}
    out, seen = [], set()
    for variant in query_variants(query)[:5]:
        page = _random.randint(1, 3)
        try:
            batch = _pexels_search(variant, page=page, limit=limit)
        except Exception:
            continue
        if not batch and page > 1:
            try:
                batch = _pexels_search(variant, page=1, limit=limit)
            except Exception:
                batch = []
        for r in batch:
            vid = str(r.video_id)
            if vid in seen or vid in exclude:
                continue
            seen.add(vid)
            out.append(r)
        if len(out) >= limit:
            break
    return out[:limit]


@video_projects_api.route("/scenes/<int:scene_id>/stock-search", methods=["POST"])
@require_auth
def scene_stock_search(scene_id: int):
    import os as _os
    if not (_os.getenv("PEXELS_API_KEY") or "").strip():
        return jsonify({"error": "PEXELS_API_KEY is not configured"}), 503
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        s = _own_scene(db, scene_id)
        if not s:
            return jsonify({"error": "Scene not found"}), 404
        query = str(data.get("query") or s.stock_search_query or s.visual_prompt or "").strip()
        if not query:
            return jsonify({"error": "query is required (or set stock_search_query on the scene)"}), 400
        page = max(1, int(data.get("page") or 1))
        try:
            results = _pexels_search(query, page=page)
        except Exception as exc:
            return jsonify({"error": f"Pexels search failed: {str(exc)[:300]}"}), 502
        if query != s.stock_search_query:
            s.stock_search_query = query[:300]
            db.commit()
        return jsonify({"query": query, "results": [_stock_result_dict(r) for r in results]})
    finally:
        db.close()


def _persist_scene_media(db, s: VideoScene, query: str, match, extra_meta: dict | None = None):
    """Download a resolved (server-side, trusted) Pexels result, attach it to the
    scene, register it in the footage library and record cost. Shared by the
    manual selection path and the auto matcher."""
    from footage.providers.pexels import download_video

    stock_dir = (settings.FOOTAGE_CACHE_DIR / "stock").resolve()
    stock_dir.mkdir(parents=True, exist_ok=True)
    try:
        saved = Path(download_video(match, stock_dir / f"pexels_{match.video_id}.mp4"))
    except Exception as exc:
        return None, f"Download failed: {str(exc)[:300]}"
    if not saved.exists() or saved.stat().st_size < 10_000:
        return None, "Downloaded file is missing or too small"
    s.selected_media_path = str(saved)
    s.visual_type = "stock"
    s.status = "ready"
    meta = _stock_result_dict(match)
    if extra_meta:
        meta = {**meta, **extra_meta}
    s.media_meta_json = json.dumps(meta, ensure_ascii=False)
    from footage_library import register_asset
    register_asset(
        db, provider=match.provider, provider_asset_id=str(match.video_id),
        local_path=saved, download_url=match.download_url or "",
        original_url=match.page_url or "", search_query=query,
        author=match.author or "", license_note="Pexels License (free to use)",
    )
    from ai_pricing import record_cost
    record_cost(provider="pexels", model="stock", operation_type="stock_download",
                project_id=s.project_id, image_count=1,
                request_id=f"stock:{match.provider}:{match.video_id}:{s.id}", db=db)
    return match, None


def _download_stock_for_scene(db, s: VideoScene, query: str, video_id: str):
    """SSRF-safe selection: re-search Pexels server-side and match by video_id;
    the client never supplies a download URL."""
    match = None
    for page in (1, 2, 3):
        for r in _pexels_search(query, page=page, limit=20):
            if str(r.video_id) == str(video_id):
                match = r
                break
        if match:
            break
    if not match:
        # the id may have come from a query variant / random page
        for r in _pexels_search_diverse(query, limit=40):
            if str(r.video_id) == str(video_id):
                match = r
                break
    if not match:
        return None, "Selected video not found in Pexels results; search again"
    return _persist_scene_media(db, s, query, match)


@video_projects_api.route("/scenes/<int:scene_id>/stock-select", methods=["POST"])
@require_auth
def scene_stock_select(scene_id: int):
    data = request.get_json(silent=True) or {}
    video_id = str(data.get("video_id") or "").strip()
    if not video_id:
        return jsonify({"error": "video_id is required"}), 400
    db = SessionLocal()
    try:
        s = _own_scene(db, scene_id)
        if not s:
            return jsonify({"error": "Scene not found"}), 404
        query = str(data.get("query") or s.stock_search_query or "").strip()
        if not query:
            return jsonify({"error": "query is required"}), 400
        match, err = _download_stock_for_scene(db, s, query, video_id)
        if err:
            return jsonify({"error": err}), 502
        db.commit()
        db.refresh(s)
        return jsonify({"scene": _scene_dict(s), "media": _stock_result_dict(match)})
    finally:
        db.close()


def _auto_media_fixtures(project_id: int, overwrite: bool):
    """Local/CI counterpart of project_auto_media for USE_MOCK_PROVIDERS=true:
    every scene missing media (or all, if overwrite) gets a synthetic fixture
    clip instead of a real stock-footage lookup. Only ever runs when mock
    providers are enabled -- the real Pexels path below is untouched and still
    requires a configured PEXELS_API_KEY when USE_MOCK_PROVIDERS=false."""
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        scenes = (
            db.query(VideoScene).filter_by(project_id=p.id)
            .order_by(VideoScene.order_index.asc()).all()
        )
        if not scenes:
            return jsonify({"error": "Project has no scenes"}), 400
        report = []
        for s in scenes:
            if s.selected_media_path and not overwrite:
                report.append({"scene_id": s.id, "skipped": "already has media"})
                continue
            out, err = _generate_fixture_clip(s)
            if err:
                report.append({"scene_id": s.id, "error": err})
                continue
            s.selected_media_path = out
            s.visual_type = "fixture"
            s.status = "ready"
            report.append({"scene_id": s.id, "fixture": True})
        db.commit()
        missing = [s.id for s in scenes if not s.selected_media_path]
        return jsonify({"report": report, "scenes_needing_review": missing,
                        "plan_source": "mock_fixture"})
    finally:
        db.close()


@video_projects_api.route("/video-projects/<int:project_id>/auto-media", methods=["POST"])
@require_auth
def project_auto_media(project_id: int):
    """Pick real stock media for every scene missing media (or all with
    overwrite=true, which still skips manually attached files unless forced).
    Local/CI only: when USE_MOCK_PROVIDERS=true, uses synthetic fixture clips
    instead (see _auto_media_fixtures) -- never reached when
    USE_MOCK_PROVIDERS=false, so production behavior is unchanged."""
    import os as _os
    data = request.get_json(silent=True) or {}
    overwrite = bool(data.get("overwrite"))
    if settings.USE_MOCK_PROVIDERS:
        return _auto_media_fixtures(project_id, overwrite)
    if not (_os.getenv("PEXELS_API_KEY") or "").strip():
        return jsonify({"error": "PEXELS_API_KEY is not configured"}), 503
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        scenes = (
            db.query(VideoScene).filter_by(project_id=p.id)
            .order_by(VideoScene.order_index.asc()).all()
        )
        if not scenes:
            return jsonify({"error": "Project has no scenes"}), 400
        channel = db.query(Channel).filter_by(id=p.channel_id).first()
        report = []

        # Semantic query plan (concrete English b-roll per scene). Built once for
        # the whole project. Uses the LLM when available, deterministic fallback
        # otherwise — see media_matcher for the reasoning.
        import media_matcher as _mm
        pending = [s for s in scenes if overwrite or not s.selected_media_path]
        plan = _mm.plan_project_queries(
            pending or scenes,
            (channel.niche if channel else "") or "",
            (channel.language if channel else "") or "ru",
        )

        # Global cooldown blacklist (recently used provider ids) computed once.
        from datetime import timedelta as _td
        from app_models import FootageAsset, FootageUsage
        recent_cutoff = datetime.utcnow() - _td(days=settings.FOOTAGE_GLOBAL_COOLDOWN_DAYS)
        recent_ids = {
            str(pid) for (pid,) in (
                db.query(FootageAsset.provider_asset_id)
                .join(FootageUsage, FootageUsage.footage_asset_id == FootageAsset.id)
                .filter(FootageUsage.used_at >= recent_cutoff)
                .all()
            )
        }
        # Media Diversity Engine long-term rule: a clip stays excluded until
        # BOTH the day threshold and the usage-count threshold clear, not
        # whichever comes first. Cheap approximation at this scene-level
        # granularity (the precise per-asset check lives in
        # footage_library.score_candidates for the segment-level picker):
        # if fewer than FOOTAGE_LONG_TERM_COOLDOWN_USES usages have happened
        # globally in the last FOOTAGE_LONG_TERM_COOLDOWN_DAYS days, nothing
        # used before that window is eligible yet either.
        long_term_cutoff = datetime.utcnow() - _td(days=settings.FOOTAGE_LONG_TERM_COOLDOWN_DAYS)
        uses_in_long_term_window = (
            db.query(FootageUsage).filter(FootageUsage.used_at >= long_term_cutoff).count()
        )
        if uses_in_long_term_window < settings.FOOTAGE_LONG_TERM_COOLDOWN_USES:
            recent_ids |= {
                str(pid) for (pid,) in (
                    db.query(FootageAsset.provider_asset_id)
                    .join(FootageUsage, FootageUsage.footage_asset_id == FootageAsset.id)
                    .filter(FootageUsage.used_at < long_term_cutoff)
                    .all()
                )
            }
        used_in_project: set[str] = set()  # never reuse a clip within one video
        # Long-form needs dozens of scenes — allow calm clips to cycle/repeat
        # (a curated serene set) instead of failing on Pexels uniqueness.
        _longform = int(p.duration_target_seconds or 0) >= 150

        from footage_library import segment_plan
        for s in scenes:
            if s.selected_media_path and not overwrite:
                report.append({"scene_id": s.id, "skipped": "already has media"})
                try:
                    vid = (json.loads(s.media_meta_json) or {}).get("video_id") if s.media_meta_json else None
                    if vid:
                        used_in_project.add(str(vid))
                except Exception:
                    pass
                continue

            # The final CTA scene reuses the previous clip (visual continuity) —
            # handled after the loop, once main scenes have their media.
            if getattr(s, "is_cta", False):
                continue

            sp = plan.scenes.get(s.id) or _mm.ScenePlan(
                scene_id=s.id, queries=[(channel.niche if channel else "") or "abstract"],
                simple="abstract", keywords=[],
            )
            # A manually set query on the scene takes priority as the top concrete stage.
            manual_q = (s.stock_search_query or s.visual_prompt or "").strip()
            if manual_q and manual_q not in sp.queries:
                sp = _mm.ScenePlan(scene_id=s.id, queries=[manual_q, *sp.queries][:3],
                                   simple=sp.simple or manual_q, keywords=sp.keywords)

            needed = len(segment_plan(float(s.estimated_duration or 4.0)))
            exclude = recent_ids if _longform else (recent_ids | used_in_project)

            def _search(q, excl, _needed=needed):
                return _pexels_search_diverse(q, limit=max(6, _needed * 2), exclude_ids=excl)

            pick = _mm.pick_media(sp, plan.atmospheric, search_fn=_search, exclude_ids=exclude)
            diag = {"stage": pick.stage, "confidence": pick.confidence,
                    "plan_source": plan.source, **pick.diagnostics}

            if pick.candidate is None:
                # Honest: no relevant footage found — leave the scene for review
                # instead of attaching something irrelevant. Persist diagnostics.
                s.media_meta_json = json.dumps({"video_id": None, "needs_review": True,
                                                "matcher": diag}, ensure_ascii=False)
                report.append({"scene_id": s.id, "confidence": "needs_review",
                               "queries_tried": [t.get("query") for t in pick.diagnostics.get("stages_tried", [])]})
                continue

            chosen_q = pick.diagnostics.get("chosen_query", sp.queries[0])
            match, err = _persist_scene_media(db, s, chosen_q, pick.candidate,
                                              extra_meta={"matcher": diag})
            if err:
                report.append({"scene_id": s.id, "error": err})
                continue
            used_in_project.add(str(match.video_id))
            report.append({"scene_id": s.id, "query": chosen_q, "video_id": str(match.video_id),
                           "orientation": match.orientation, "author": match.author,
                           "stage": pick.stage, "confidence": pick.confidence,
                           "relevance": pick.diagnostics.get("chosen_score"),
                           "segments_planned": needed})
        # CTA scene(s): reuse the preceding scene's clip (visual continuity).
        ordered = sorted(scenes, key=lambda x: x.order_index)
        for i, s in enumerate(ordered):
            if getattr(s, "is_cta", False) and not s.selected_media_path and i > 0:
                prev = ordered[i - 1]
                if prev.selected_media_path:
                    s.selected_media_path = prev.selected_media_path
                    s.visual_type = prev.visual_type
                    s.media_meta_json = prev.media_meta_json
                    s.status = "ready"
                    report.append({"scene_id": s.id, "cta": True, "reused_previous_clip": True})
        db.commit()
        # Scenes still without media after matching → the station needs review.
        missing = [s.id for s in scenes if not s.selected_media_path]
        return jsonify({"report": report, "scenes_needing_review": missing,
                        "plan_source": plan.source})
    finally:
        db.close()


# ---------------------------------------------------------------- media library

@video_projects_api.route("/media-library/stats", methods=["GET"])
@require_auth
def media_library_stats():
    from datetime import timedelta as _td

    from sqlalchemy import func

    from app_models import FootageAsset, FootageUsage

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        total_assets = db.query(func.count(FootageAsset.id)).scalar() or 0
        used_today = (
            db.query(func.count(func.distinct(FootageUsage.footage_asset_id)))
            .filter(FootageUsage.used_at >= now - _td(days=1)).scalar() or 0
        )
        top_used = (
            db.query(FootageAsset)
            .filter(FootageAsset.total_use_count > 0)
            .order_by(FootageAsset.total_use_count.desc()).limit(10).all()
        )
        recent = (
            db.query(FootageAsset)
            .filter(FootageAsset.last_used_at.isnot(None))
            .order_by(FootageAsset.last_used_at.desc()).limit(10).all()
        )
        # duplicates: same file_hash appearing under multiple provider ids is
        # prevented at registration; report hash collisions if any slipped in
        dup_hashes = (
            db.query(FootageAsset.file_hash, func.count(FootageAsset.id))
            .filter(FootageAsset.file_hash.isnot(None))
            .group_by(FootageAsset.file_hash)
            .having(func.count(FootageAsset.id) > 1).all()
        )
        channel_id = request.args.get("channel_id", type=int)
        cooldown_cutoff = now - _td(days=settings.FOOTAGE_SAME_CHANNEL_COOLDOWN_DAYS)
        cd_q = (
            db.query(func.count(func.distinct(FootageUsage.footage_asset_id)))
            .filter(FootageUsage.used_at >= cooldown_cutoff)
        )
        if channel_id:
            cd_q = cd_q.filter(FootageUsage.channel_id == channel_id)
        on_cooldown = cd_q.scalar() or 0

        def _a(a):
            return {
                "id": a.id, "provider": a.provider, "provider_asset_id": a.provider_asset_id,
                "search_query": a.search_query, "orientation": a.orientation,
                "duration": a.duration, "use_count": a.total_use_count,
                "last_used_at": a.last_used_at.isoformat() if a.last_used_at else None,
            }

        return jsonify({
            "total_assets": total_assets,
            "used_today": used_today,
            "on_cooldown": on_cooldown,
            "duplicate_hashes": len(dup_hashes),
            "top_used": [_a(a) for a in top_used],
            "recently_used": [_a(a) for a in recent],
            "settings": {
                "segment_seconds": settings.FOOTAGE_SEGMENT_SECONDS,
                "segment_min": settings.FOOTAGE_SEGMENT_MIN_SECONDS,
                "segment_max": settings.FOOTAGE_SEGMENT_MAX_SECONDS,
                "same_channel_cooldown_days": settings.FOOTAGE_SAME_CHANNEL_COOLDOWN_DAYS,
                "global_cooldown_days": settings.FOOTAGE_GLOBAL_COOLDOWN_DAYS,
                "allow_reuse_fallback": settings.FOOTAGE_ALLOW_REUSE_FALLBACK,
                "subtitle_max_line_chars": settings.SUBTITLE_MAX_LINE_CHARS,
                "subtitle_margin_bottom_px": settings.SUBTITLE_MARGIN_BOTTOM_PX,
                "subtitle_highlight_keyword": settings.SUBTITLE_HIGHLIGHT_KEYWORD,
            },
        })
    finally:
        db.close()
