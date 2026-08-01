"""Channel management API for private YouTube-factory mode.

Registered under /api alongside api. All endpoints require auth and
enforce per-owner isolation (owner_user_id == current user).
"""
import json
import re
import unicodedata
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from database import SessionLocal
from auth import require_auth
from app_models import Channel, ChannelIdea

channels_api = Blueprint("channels_api", __name__, url_prefix="/api")

MAX_CHANNELS = 10
CHANNEL_STATUSES = {"testing", "active", "paused", "archived"}
IDEA_STATUSES = {"new", "saved", "deferred", "rejected", "converted"}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    norm = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_RE.sub("-", norm.lower()).strip("-")
    return slug or "channel"


def _scheduler_status(c: Channel) -> dict:
    """Honest, UI-facing view of the auto-generation scheduler for this channel.

    Mirrors scheduler._due: the scheduler is active when the channel has
    auto-generation on, a niche, active status and a positive daily limit; it
    produces one video every (24h / daily_limit). Fields are derived from
    channel columns only (no query) so the serializer stays cheap and pure.
    """
    from datetime import timedelta

    limit = int(c.daily_video_limit or 0)
    active = bool(c.automatic_generation_enabled and c.niche_id
                  and c.status == "active" and limit > 0)
    interval_min = (24 * 60 // limit) if limit > 0 else None
    next_at = None
    if active:
        if c.last_generated_at:
            next_at = c.last_generated_at + timedelta(minutes=interval_min)
        else:
            next_at = datetime.utcnow()  # never generated → due now
    return {
        "scheduler_active": active,
        "generation_interval_minutes": interval_min,
        "next_generation_at": next_at.isoformat() if next_at else None,
    }


def _channel_dict(c: Channel) -> dict:
    def _j(raw):
        try:
            return json.loads(raw) if raw else None
        except Exception:
            return None

    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "niche": c.niche,
        "description": c.description,
        "language": c.language,
        "target_audience": c.target_audience,
        "content_style": c.content_style,
        "narration_style": c.narration_style,
        "default_voice": c.default_voice,
        "visual_style": c.visual_style,
        "categories": _j(c.categories_json) or [],
        "allowed_topics": c.allowed_topics,
        "prohibited_topics": c.prohibited_topics,
        "default_video_duration_seconds": c.default_video_duration_seconds,
        "default_video_format": c.default_video_format,
        "publication_frequency": c.publication_frequency,
        "timezone": c.timezone,
        "status": c.status,
        "niche_id": c.niche_id,
        "target_country": c.target_country,
        "tone_of_voice": c.tone_of_voice,
        "daily_video_limit": c.daily_video_limit,
        "default_visibility": c.default_visibility,
        "automatic_generation_enabled": bool(c.automatic_generation_enabled),
        "automatic_publishing_enabled": bool(c.automatic_publishing_enabled),
        "publishing_mode": (getattr(c, "publishing_mode", None) or "manual"),
        "last_generated_at": c.last_generated_at.isoformat() if c.last_generated_at else None,
        **_scheduler_status(c),
        "youtube_channel_id": c.youtube_channel_id,
        "connected_account_id": c.connected_account_id,
        "generation_settings": _j(c.generation_settings_json) or {},
        "video_template": _j(c.video_template_json) or {},
        "subtitle_template": _j(c.subtitle_template_json) or {},
        "music_settings": _j(c.music_settings_json) or {},
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _idea_dict(i: ChannelIdea) -> dict:
    return {
        "id": i.id,
        "channel_id": i.channel_id,
        "title": i.title,
        "topic": i.topic,
        "category": i.category,
        "hook_concept": i.hook_concept,
        "summary": i.summary,
        "source": i.source,
        "status": i.status,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


def _own_channel(db, channel_id: int) -> Channel | None:
    return (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


_TEXT_FIELDS = {
    "name", "niche", "description", "language", "target_audience", "content_style",
    "narration_style", "default_voice", "visual_style", "allowed_topics",
    "prohibited_topics", "default_video_format", "publication_frequency",
    "timezone", "youtube_channel_id", "target_country", "tone_of_voice",
    "default_visibility",
}
_JSON_FIELDS = {
    "categories": "categories_json",
    "generation_settings": "generation_settings_json",
    "video_template": "video_template_json",
    "subtitle_template": "subtitle_template_json",
    "music_settings": "music_settings_json",
}


def _apply_channel_fields(c: Channel, data: dict) -> str | None:
    for f in _TEXT_FIELDS:
        if f in data:
            val = data.get(f)
            if val is not None and not isinstance(val, str):
                return f"Field '{f}' must be a string"
            setattr(c, f, (val or "").strip() or None if f != "name" else (val or "").strip())
    if "default_video_duration_seconds" in data:
        try:
            dur = int(data["default_video_duration_seconds"])
        except (TypeError, ValueError):
            return "default_video_duration_seconds must be an integer"
        if not (5 <= dur <= 3600):
            return "default_video_duration_seconds must be between 5 and 3600"
        c.default_video_duration_seconds = dur
    for public, col in _JSON_FIELDS.items():
        if public in data:
            try:
                setattr(c, col, json.dumps(data[public], ensure_ascii=False))
            except (TypeError, ValueError):
                return f"Field '{public}' must be JSON-serializable"
    if "status" in data:
        status = str(data["status"] or "").strip().lower()
        if status not in CHANNEL_STATUSES:
            return f"status must be one of {sorted(CHANNEL_STATUSES)}"
        c.status = status
    if "niche_id" in data:
        raw = data.get("niche_id")
        if raw in (None, "", 0, "0"):
            c.niche_id = None
        else:
            from app_models import ContentNiche
            from database import SessionLocal as _SL
            _db = _SL()
            try:
                if not _db.query(ContentNiche).filter_by(id=int(raw)).first():
                    return "niche_id does not exist"
            finally:
                _db.close()
            c.niche_id = int(raw)
    if "daily_video_limit" in data:
        try:
            c.daily_video_limit = max(0, int(data["daily_video_limit"]))
        except (TypeError, ValueError):
            return "daily_video_limit must be an integer"
    for flag in ("automatic_generation_enabled", "automatic_publishing_enabled"):
        if flag in data:
            setattr(c, flag, bool(data[flag]))
    if not (c.language or "").strip():
        c.language = "ru"
    if not (c.timezone or "").strip():
        c.timezone = "Europe/Berlin"
    if not (c.default_video_format or "").strip():
        c.default_video_format = "shorts"
    return None


@channels_api.route("/channels/<int:channel_id>/publishing-mode", methods=["POST"])
@require_auth
def set_publishing_mode(channel_id: int):
    """Set the channel publishing mode. Enabling 'automatic' (full autopilot)
    requires explicit confirmation and a connected YouTube channel."""
    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode") or "").strip().lower()
    if mode not in ("manual", "automatic"):
        return jsonify({"error": "mode must be 'manual' or 'automatic'"}), 400
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        if mode == "automatic":
            if not data.get("confirm"):
                return jsonify({
                    "error": "confirmation_required",
                    "message": "AutoSocial сможет публиковать видео на этот YouTube-канал без индивидуального подтверждения.",
                }), 409
            if (c.youtube_connection_status or "") != "connected":
                return jsonify({
                    "error": "youtube_not_connected",
                    "message": "Сначала подключите YouTube-канал, затем включайте автопилот.",
                }), 409
        c.publishing_mode = mode
        c.autopilot_enabled = (mode == "automatic")  # keep the legacy flag in sync
        db.commit()
        return jsonify({"channel_id": c.id, "publishing_mode": c.publishing_mode})
    finally:
        db.close()


@channels_api.route("/channels/<int:channel_id>/cta-settings", methods=["GET", "POST"])
@require_auth
def cta_settings(channel_id: int):
    """Get or update the final-CTA settings for a channel. Stored in the existing
    channel.generation_settings_json under the 'cta' key (no parallel config)."""
    import cta_generator as _cta
    from app_models import VideoProject
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            cur = _cta.read_cta_settings(c)
            bools = ("cta_enabled", "cta_voice_enabled", "cta_visual_enabled")
            ints = {"cta_min_words": (1, 30), "cta_max_words": (2, 40),
                    "cta_history_window": (0, 200), "cta_max_same_type_streak": (1, 20)}
            for k in bools:
                if k in data:
                    cur[k] = bool(data[k])
            for k, (lo, hi) in ints.items():
                if k in data:
                    try:
                        cur[k] = max(lo, min(hi, int(data[k])))
                    except (TypeError, ValueError):
                        return jsonify({"error": f"{k} must be an integer"}), 400
            if "cta_fallback_text" in data:
                cur["cta_fallback_text"] = str(data.get("cta_fallback_text") or "").strip()[:300]
            if int(cur["cta_min_words"]) > int(cur["cta_max_words"]):
                return jsonify({"error": "cta_min_words cannot exceed cta_max_words"}), 400
            cfg = _j(c.generation_settings_json) or {}
            cfg["cta"] = cur
            c.generation_settings_json = json.dumps(cfg, ensure_ascii=False)
            db.commit()
        settings_out = _cta.read_cta_settings(c)
        last = (db.query(VideoProject.cta_text, VideoProject.cta_type, VideoProject.cta_source)
                .filter(VideoProject.channel_id == c.id, VideoProject.cta_text.isnot(None))
                .order_by(VideoProject.id.desc()).first())
        return jsonify({
            "channel_id": c.id,
            "cta_settings": settings_out,
            "last_cta": ({"text": last[0], "type": last[1], "source": last[2]} if last else None),
        })
    finally:
        db.close()


def _j(raw):
    try:
        return json.loads(raw) if raw else None
    except Exception:
        return None


@channels_api.route("/channels", methods=["GET"])
@require_auth
def list_channels():
    db = SessionLocal()
    try:
        rows = (
            db.query(Channel)
            .filter(Channel.owner_user_id == g.current_user.id)
            .order_by(Channel.created_at.asc())
            .all()
        )
        return jsonify({"channels": [_channel_dict(c) for c in rows]})
    finally:
        db.close()


@channels_api.route("/channels", methods=["POST"])
@require_auth
def create_channel():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Channel name is required"}), 400
    db = SessionLocal()
    try:
        count = (
            db.query(Channel)
            .filter(Channel.owner_user_id == g.current_user.id, Channel.status != "archived")
            .count()
        )
        if count >= MAX_CHANNELS:
            return jsonify({"error": f"Channel limit reached ({MAX_CHANNELS})"}), 409
        base_slug = _slugify(name)
        slug = base_slug
        n = 2
        while db.query(Channel).filter_by(slug=slug).first():
            slug = f"{base_slug}-{n}"
            n += 1
        c = Channel(owner_user_id=g.current_user.id, name=name, slug=slug)
        err = _apply_channel_fields(c, data)
        if err:
            return jsonify({"error": err}), 400
        db.add(c)
        db.commit()
        db.refresh(c)
        return jsonify({"channel": _channel_dict(c)}), 201
    finally:
        db.close()


@channels_api.route("/channels/<int:channel_id>", methods=["GET"])
@require_auth
def get_channel(channel_id: int):
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        ideas = (
            db.query(ChannelIdea)
            .filter(ChannelIdea.channel_id == c.id)
            .order_by(ChannelIdea.created_at.desc())
            .limit(100)
            .all()
        )
        payload = _channel_dict(c)
        payload["ideas"] = [_idea_dict(i) for i in ideas]
        return jsonify({"channel": payload})
    finally:
        db.close()


@channels_api.route("/channels/<int:channel_id>", methods=["PATCH"])
@require_auth
def update_channel(channel_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        if "name" in data and not str(data.get("name") or "").strip():
            return jsonify({"error": "Channel name cannot be empty"}), 400
        err = _apply_channel_fields(c, data)
        if err:
            return jsonify({"error": err}), 400
        c.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(c)
        return jsonify({"channel": _channel_dict(c)})
    finally:
        db.close()


@channels_api.route("/channels/<int:channel_id>", methods=["DELETE"])
@require_auth
def delete_channel(channel_id: int):
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        idea_count = db.query(ChannelIdea).filter(ChannelIdea.channel_id == c.id).count()
        if idea_count:
            return jsonify({
                "error": "Channel has dependent records; archive it instead",
                "ideas": idea_count,
            }), 409
        db.delete(c)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


@channels_api.route("/channels/<int:channel_id>/ideas", methods=["GET"])
@require_auth
def list_ideas(channel_id: int):
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        status = (request.args.get("status") or "").strip().lower()
        q = db.query(ChannelIdea).filter(ChannelIdea.channel_id == c.id)
        if status:
            if status not in IDEA_STATUSES:
                return jsonify({"error": f"status must be one of {sorted(IDEA_STATUSES)}"}), 400
            q = q.filter(ChannelIdea.status == status)
        rows = q.order_by(ChannelIdea.created_at.desc()).limit(200).all()
        return jsonify({"ideas": [_idea_dict(i) for i in rows]})
    finally:
        db.close()


@channels_api.route("/channels/<int:channel_id>/ideas", methods=["POST"])
@require_auth
def create_idea(channel_id: int):
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Idea title is required"}), 400
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        idea = ChannelIdea(
            channel_id=c.id,
            title=title[:300],
            topic=(str(data.get("topic") or "").strip() or None),
            category=(str(data.get("category") or "").strip() or None),
            hook_concept=(str(data.get("hook_concept") or "").strip() or None),
            summary=(str(data.get("summary") or "").strip() or None),
            source="manual",
            status="new",
        )
        db.add(idea)
        db.commit()
        db.refresh(idea)
        return jsonify({"idea": _idea_dict(idea)}), 201
    finally:
        db.close()


@channels_api.route("/ideas/<int:idea_id>", methods=["PATCH"])
@require_auth
def update_idea(idea_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        idea = (
            db.query(ChannelIdea)
            .join(Channel, Channel.id == ChannelIdea.channel_id)
            .filter(ChannelIdea.id == idea_id, Channel.owner_user_id == g.current_user.id)
            .first()
        )
        if not idea:
            return jsonify({"error": "Idea not found"}), 404
        if "status" in data:
            status = str(data["status"] or "").strip().lower()
            if status not in IDEA_STATUSES:
                return jsonify({"error": f"status must be one of {sorted(IDEA_STATUSES)}"}), 400
            idea.status = status
        for f in ("title", "topic", "category", "hook_concept", "summary"):
            if f in data:
                val = str(data.get(f) or "").strip()
                if f == "title" and not val:
                    return jsonify({"error": "Idea title cannot be empty"}), 400
                setattr(idea, f, val or None)
        db.commit()
        db.refresh(idea)
        return jsonify({"idea": _idea_dict(idea)})
    finally:
        db.close()


@channels_api.route("/channels/<int:channel_id>/ideas/generate", methods=["POST"])
@require_auth
def generate_ideas(channel_id: int):
    from openai_client import OpenAIClientError, generate_json_with_retry, is_openai_enabled

    if not is_openai_enabled():
        return jsonify({"error": "OPENAI_API_KEY is not configured; idea generation unavailable"}), 503

    data = request.get_json(silent=True) or {}
    try:
        count = max(1, min(10, int(data.get("count") or 5)))
    except (TypeError, ValueError):
        return jsonify({"error": "count must be an integer"}), 400
    topic_hint = str(data.get("topic") or "").strip()[:300]
    category = str(data.get("category") or "").strip()[:120]

    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        channel_ctx = {
            "niche": c.niche,
            "language": c.language,
            "target_audience": c.target_audience,
            "content_style": c.content_style,
            "allowed_topics": c.allowed_topics,
            "prohibited_topics": c.prohibited_topics,
        }

        def _validate(payload: dict) -> None:
            ideas = payload.get("ideas")
            if not isinstance(ideas, list) or not ideas:
                raise ValueError("ideas must be a non-empty list")
            for item in ideas:
                if not isinstance(item, dict) or not str(item.get("title") or "").strip():
                    raise ValueError("each idea needs a title")

        system_prompt = (
            "You generate short-video (YouTube Shorts) content ideas for a specific channel. "
            "Respond with JSON: {\"ideas\": [{\"title\", \"topic\", \"category\", \"hook_concept\", \"summary\"}]}. "
            "Write in the channel language. Ideas must fit the niche and respect prohibited topics. "
            "For esoteric/mystical niches: frame content as entertainment, culture or history; "
            "never present medical, financial or legal claims, dangerous instructions, "
            "or guaranteed predictions as proven fact."
        )
        user_prompt = json.dumps(
            {"channel": channel_ctx, "count": count, "topic_hint": topic_hint or None, "category": category or None},
            ensure_ascii=False,
        )
        from ai_pricing import BudgetExceeded, check_budget, estimate_cost, record_cost
        import os as _os
        model_name = (_os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
        try:
            check_budget(db, estimated_cost=estimate_cost("openai", model_name, 1000, 1800))
        except BudgetExceeded as exc:
            return jsonify({"error": str(exc)}), 429
        try:
            result = generate_json_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                validator=_validate,
                max_output_tokens=1800,
                temperature=0.8,
            )
        except OpenAIClientError as exc:
            record_cost(provider="openai", model=model_name, operation_type="idea_generation",
                        channel_id=c.id, status="failed", error=str(exc)[:400], db=db)
            return jsonify({"error": f"Idea generation failed: {exc}"}), 502
        record_cost(provider="openai", model=model_name, operation_type="idea_generation",
                    channel_id=c.id,
                    input_units=float(result.input_tokens or 0),
                    output_units=float(result.output_tokens or 0), db=db)

        payload = result.payload or {}
        created = []
        for item in (payload.get("ideas") or [])[:count]:
            idea = ChannelIdea(
                channel_id=c.id,
                title=str(item.get("title") or "").strip()[:300],
                topic=(str(item.get("topic") or "").strip() or None),
                category=(str(item.get("category") or category or "").strip() or None),
                hook_concept=(str(item.get("hook_concept") or "").strip() or None),
                summary=(str(item.get("summary") or "").strip() or None),
                source="generated",
                status="new",
            )
            db.add(idea)
            created.append(idea)
        db.commit()
        for i in created:
            db.refresh(i)
        return jsonify({"ideas": [_idea_dict(i) for i in created]}), 201
    finally:
        db.close()
