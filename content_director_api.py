"""AI Content Director API.

GET  /api/content-director                  — queue of upcoming ideas + reasons
POST /api/content-director/generate         — Director decides the next video
POST /api/content-director/approve          — approve -> hand off to the writer
POST /api/content-director/reject           — reject (optionally ban the topic)
POST /api/content-director/regenerate       — reject current + decide again

Admin extras: pin, ban, change priority.
All endpoints require auth and enforce per-owner channel isolation.
"""
import json
from datetime import datetime

from flask import Blueprint, g, jsonify, request

import content_director as director
from database import SessionLocal
from auth import require_auth
from app_models import Channel, ContentPillar, DirectorStrategy
from app_settings import settings

content_director_api = Blueprint("content_director_api", __name__, url_prefix="/api")

EDITABLE_STATUSES = {"draft", "approved", "rejected", "banned"}


def _own_channel(db, channel_id: int) -> Channel | None:
    return (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


def _own_strategy(db, strategy_id: int) -> DirectorStrategy | None:
    return (
        db.query(DirectorStrategy)
        .join(Channel, Channel.id == DirectorStrategy.channel_id)
        .filter(DirectorStrategy.id == strategy_id,
                Channel.owner_user_id == g.current_user.id)
        .first()
    )


def _iso(dt):
    return dt.isoformat() if dt else None


def _strategy_dict(s: DirectorStrategy, db=None, *, with_decision: bool = False) -> dict:
    out = {
        "id": s.id,
        "channel_id": s.channel_id,
        "niche_id": s.niche_id,
        "pillar_id": s.pillar_id,
        "language": s.language,
        "target_audience": s.target_audience,
        "generation_reason": s.generation_reason,
        "priority": s.priority,
        "estimated_ctr": s.estimated_ctr,
        "estimated_retention": s.estimated_retention,
        "novelty_score": s.novelty_score,
        "competition_score": s.competition_score,
        "hook_strength": s.hook_strength,
        "visual_potential": s.visual_potential,
        "educational_value": s.educational_value,
        "entertainment_value": s.entertainment_value,
        "selected_topic": s.selected_topic,
        "selected_angle": s.selected_angle,
        "selected_hook": s.selected_hook,
        "outline": json.loads(s.outline_json) if s.outline_json else None,
        "status": s.status,
        "pinned": bool(s.pinned),
        "source": s.source,
        "video_project_id": s.video_project_id,
        "created_at": _iso(s.created_at),
        "updated_at": _iso(s.updated_at),
    }
    if db is not None and s.pillar_id:
        p = db.query(ContentPillar).filter_by(id=s.pillar_id).first()
        out["pillar_name"] = p.name if p else None
    if with_decision and s.decision_json:
        try:
            out["decision"] = json.loads(s.decision_json)
        except Exception:
            out["decision"] = None
    return out


# ------------------------------------------------------------------ read

@content_director_api.route("/content-director", methods=["GET"])
@require_auth
def list_strategies():
    """Upcoming ideas with their reasons and scores (pinned first, then priority)."""
    db = SessionLocal()
    try:
        q = (
            db.query(DirectorStrategy)
            .join(Channel, Channel.id == DirectorStrategy.channel_id)
            .filter(Channel.owner_user_id == g.current_user.id)
        )
        channel_id = request.args.get("channel_id", type=int)
        if channel_id:
            q = q.filter(DirectorStrategy.channel_id == channel_id)
        status = (request.args.get("status") or "").strip().lower()
        if status:
            q = q.filter(DirectorStrategy.status == status)
        rows = (
            q.order_by(DirectorStrategy.pinned.desc(),
                       DirectorStrategy.priority.desc(),
                       DirectorStrategy.created_at.desc())
            .limit(100).all()
        )
        counts: dict[str, int] = {}
        for r in rows:
            counts[r.status] = counts.get(r.status, 0) + 1
        return jsonify({
            "strategies": [_strategy_dict(r, db) for r in rows],
            "counts": counts,
            "director": {
                "enabled": settings.DIRECTOR_ENABLED,
                "use_ai": settings.DIRECTOR_USE_AI,
                "candidates_per_run": settings.DIRECTOR_CANDIDATES_PER_RUN,
                "duplicate_threshold": settings.DIRECTOR_DUPLICATE_THRESHOLD,
                "topic_cooldown_days": settings.TOPIC_COOLDOWN_DAYS,
            },
        })
    finally:
        db.close()


@content_director_api.route("/content-director/<int:strategy_id>", methods=["GET"])
@require_auth
def get_strategy(strategy_id: int):
    """Full explainability: every candidate, score and reason behind the pick."""
    db = SessionLocal()
    try:
        s = _own_strategy(db, strategy_id)
        if not s:
            return jsonify({"error": "Strategy not found"}), 404
        return jsonify({"strategy": _strategy_dict(s, db, with_decision=True)})
    finally:
        db.close()


# -------------------------------------------------------------- generate

@content_director_api.route("/content-director/generate", methods=["POST"])
@require_auth
def generate():
    data = request.get_json(silent=True) or {}
    channel_id = data.get("channel_id")
    if not channel_id:
        return jsonify({"error": "channel_id is required"}), 400
    if not settings.DIRECTOR_ENABLED:
        return jsonify({"error": "Content Director is disabled (DIRECTOR_ENABLED=false)"}), 409
    db = SessionLocal()
    try:
        c = _own_channel(db, int(channel_id))
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        pillar_id = data.get("pillar_id")
        strategy, decision = director.decide(
            db, c, pillar_id=int(pillar_id) if pillar_id else None)
        if not strategy:
            return jsonify({"error": decision.get("error", "director_could_not_decide"),
                            "decision": decision}), 409
        return jsonify({"strategy": _strategy_dict(strategy, db, with_decision=True)}), 201
    finally:
        db.close()


# --------------------------------------------------------------- approve

@content_director_api.route("/content-director/approve", methods=["POST"])
@require_auth
def approve():
    """Approve a strategy and hand it to the existing Script Generator by
    creating the VideoProject (Director itself writes no script)."""
    data = request.get_json(silent=True) or {}
    sid = data.get("strategy_id")
    if not sid:
        return jsonify({"error": "strategy_id is required"}), 400
    db = SessionLocal()
    try:
        s = _own_strategy(db, int(sid))
        if not s:
            return jsonify({"error": "Strategy not found"}), 404
        if s.status == "used":
            return jsonify({"error": "Strategy already handed off",
                            "video_project_id": s.video_project_id}), 409
        if s.status in {"rejected", "banned"}:
            return jsonify({"error": f"Strategy is {s.status} and cannot be approved"}), 409
        s.status = "approved"
        s.updated_at = datetime.utcnow()
        db.commit()
        project = director.handoff_to_writer(db, s)
        return jsonify({
            "strategy": _strategy_dict(s, db),
            "video_project_id": project.id,
            "handoff": "script generator can now write the script for this project",
        })
    finally:
        db.close()


# ---------------------------------------------------------------- reject

@content_director_api.route("/content-director/reject", methods=["POST"])
@require_auth
def reject():
    """Reject an idea. `ban=true` also blocks the topic from future ideation."""
    data = request.get_json(silent=True) or {}
    sid = data.get("strategy_id")
    if not sid:
        return jsonify({"error": "strategy_id is required"}), 400
    db = SessionLocal()
    try:
        s = _own_strategy(db, int(sid))
        if not s:
            return jsonify({"error": "Strategy not found"}), 404
        if s.status == "used":
            return jsonify({"error": "Strategy already handed off; cannot reject"}), 409
        s.status = "banned" if data.get("ban") else "rejected"
        s.pinned = False
        reason = str(data.get("reason") or "").strip()
        if reason:
            s.generation_reason = f"{s.generation_reason or ''} | rejected: {reason}"[:2000]
        s.updated_at = datetime.utcnow()
        db.commit()
        return jsonify({"strategy": _strategy_dict(s, db)})
    finally:
        db.close()


# ------------------------------------------------------------ regenerate

@content_director_api.route("/content-director/regenerate", methods=["POST"])
@require_auth
def regenerate():
    """Reject the current idea and let the Director decide again. The rejected
    topic is part of the history, so the new idea will differ."""
    data = request.get_json(silent=True) or {}
    sid = data.get("strategy_id")
    if not sid:
        return jsonify({"error": "strategy_id is required"}), 400
    db = SessionLocal()
    try:
        s = _own_strategy(db, int(sid))
        if not s:
            return jsonify({"error": "Strategy not found"}), 404
        if s.status == "used":
            return jsonify({"error": "Strategy already handed off; cannot regenerate"}), 409
        c = db.query(Channel).filter_by(id=s.channel_id).first()
        s.status = "banned" if data.get("ban") else "rejected"
        s.updated_at = datetime.utcnow()
        db.commit()
        keep_pillar = s.pillar_id if data.get("keep_pillar") else None
        strategy, decision = director.decide(db, c, pillar_id=keep_pillar)
        if not strategy:
            return jsonify({"error": decision.get("error", "director_could_not_decide"),
                            "decision": decision, "previous_status": s.status}), 409
        return jsonify({
            "previous_strategy_id": s.id,
            "strategy": _strategy_dict(strategy, db, with_decision=True),
        }), 201
    finally:
        db.close()


# ------------------------------------------------------- admin adjustments

@content_director_api.route("/content-director/<int:strategy_id>", methods=["PATCH"])
@require_auth
def update_strategy(strategy_id: int):
    """Pin a topic, change its priority, or set status (admin control)."""
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        s = _own_strategy(db, strategy_id)
        if not s:
            return jsonify({"error": "Strategy not found"}), 404
        if s.status == "used":
            return jsonify({"error": "Strategy already handed off; cannot edit"}), 409
        if "pinned" in data:
            s.pinned = bool(data["pinned"])
        if "priority" in data:
            try:
                s.priority = max(1, min(100, int(data["priority"])))
            except (TypeError, ValueError):
                return jsonify({"error": "priority must be an integer 1..100"}), 400
        if "status" in data:
            st = str(data["status"]).strip().lower()
            if st not in EDITABLE_STATUSES:
                return jsonify({"error": f"status must be one of {sorted(EDITABLE_STATUSES)}"}), 400
            s.status = st
        s.updated_at = datetime.utcnow()
        db.commit()
        return jsonify({"strategy": _strategy_dict(s, db)})
    finally:
        db.close()
