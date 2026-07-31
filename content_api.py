"""Content architecture API: niches, pillars, channel automation, topics.

Chain: Channel -> ContentNiche -> ContentPillar -> Topic -> Script -> Visual
Intent -> Footage -> Render -> Publish.

Nothing here is hardcoded to esotericism: niches/pillars are DB rows managed
through the admin API/UI. `seed_esotericism()` only creates the starter
profile; the admin can create any other niche without code changes.
"""
import json
import random
import re
import unicodedata
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request

from database import SessionLocal
from saas_auth import require_auth
from saas_models import (
    Channel,
    ChannelIdea,
    ContentNiche,
    ContentPillar,
    VideoProject,
)
from saas_settings import settings

content_api = Blueprint("content_api", __name__, url_prefix="/api")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


_RU_TRANSLIT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
})


def _slugify(value: str) -> str:
    lowered = (value or "").lower().translate(_RU_TRANSLIT)
    norm = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_RE.sub("-", norm).strip("-")
    return slug or "item"


def _iso(dt):
    return dt.isoformat() if dt else None


def _own_channel(db, channel_id: int) -> Channel | None:
    return (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


# --------------------------------------------------------- content safety

# Blocklist of dangerous claims (channel/niche policy layer). Applied to
# generated topics/scripts before they are accepted.
_SAFETY_RULES = [
    ("medical_claim", re.compile(r"(вылечит|исцелит|лечит\s+(болезн|рак|депресс)|откажитесь\s+от\s+(врач|лекарств)|замен(а|ит)\s+врача)", re.I)),
    ("guaranteed_money", re.compile(r"(гарантированн\w*\s+(доход|деньги|прибыль|богатств)|деньги\s+придут\s+обязательно|стопроцентн\w*\s+(доход|результат))", re.I)),
    ("partner_return_promise", re.compile(r"(вернёт\s+партн|вернет\s+(любимого|партн|мужа|жену)|приворот)", re.I)),
    ("curse_fear", re.compile(r"(на\s+вас\s+проклят|вы\s+прокляты|снять\s+порчу\s+срочно|смертельн\w+\s+опасн\w+\s+знак)", re.I)),
    ("money_transfer", re.compile(r"(переведите\s+деньги|отправьте\s+оплату|оплатите\s+ритуал)", re.I)),
    ("diagnosis", re.compile(r"(у\s+вас\s+(депрессия|шизофрения|психоз)|вы\s+одержимы)", re.I)),
]

# Speculative practices must be framed as tradition/belief, never as fact.
_DISCLAIMER_TRIGGERS = {
    "numerology": (re.compile(r"нумеролог", re.I),
                   re.compile(r"(в\s+нумерологии\s+считается|сторонники\s+нумерологии|в\s+эзотерической\s+традиции)", re.I)),
    "astrology": (re.compile(r"(астролог|знак\w*\s+зодиака|овн\w{1,2}\b|тельц\w{1,2}\b|близнец\w{1,3}\b|\bрак\w{0,3}\s+(сегодня|повез|ждут)|льв\w{1,3}\b|дев\w{1,2}\s+(сегодня|повез)|весам|скорпион|стрельц|козерог|водоле|рыбам)", re.I),
                  re.compile(r"(в\s+астрологии\s+считается|астрологи\s+связывают|согласно\s+популярной\s+астрологической)", re.I)),
}


def check_content_safety(text: str) -> list[str]:
    """Returns a list of violated rule names (empty = safe)."""
    violations = []
    for name, rx in _SAFETY_RULES:
        if rx.search(text or ""):
            violations.append(name)
    return violations


def check_disclaimers(text: str) -> list[str]:
    """Returns topics that mention a speculative practice WITHOUT the required
    'considered/believed' framing."""
    missing = []
    for name, (trigger, framing) in _DISCLAIMER_TRIGGERS.items():
        if trigger.search(text or "") and not framing.search(text or ""):
            missing.append(name)
    return missing


# ----------------------------------------------------------------- niches

def _niche_dict(n: ContentNiche, db=None) -> dict:
    out = {
        "id": n.id, "name": n.name, "slug": n.slug, "description": n.description,
        "default_language": n.default_language, "default_tone": n.default_tone,
        "default_visual_style": n.default_visual_style,
        "allowed_topics": n.allowed_topics, "forbidden_topics": n.forbidden_topics,
        "forbidden_visuals": n.forbidden_visuals,
        "disclaimer_policy": n.disclaimer_policy,
        "factuality_policy": n.factuality_policy,
        "sensitive_topics_policy": n.sensitive_topics_policy,
        "active": n.active,
        "created_at": _iso(n.created_at), "updated_at": _iso(n.updated_at),
    }
    if db is not None:
        out["channels_using"] = [
            {"id": c.id, "name": c.name}
            for c in db.query(Channel).filter(Channel.niche_id == n.id).all()
        ]
        out["pillars_count"] = db.query(ContentPillar).filter_by(niche_id=n.id).count()
    return out


_NICHE_TEXT_FIELDS = {
    "name", "description", "default_language", "default_tone",
    "default_visual_style", "allowed_topics", "forbidden_topics",
    "forbidden_visuals", "disclaimer_policy", "factuality_policy",
    "sensitive_topics_policy",
}


@content_api.route("/niches", methods=["GET"])
@require_auth
def list_niches():
    db = SessionLocal()
    try:
        rows = db.query(ContentNiche).order_by(ContentNiche.created_at.asc()).all()
        return jsonify({"niches": [_niche_dict(n, db) for n in rows]})
    finally:
        db.close()


@content_api.route("/niches", methods=["POST"])
@require_auth
def create_niche():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    db = SessionLocal()
    try:
        slug = str(data.get("slug") or "").strip() or _slugify(name)
        if db.query(ContentNiche).filter_by(slug=slug).first():
            return jsonify({"error": f"Niche slug '{slug}' already exists"}), 409
        n = ContentNiche(name=name[:160], slug=slug[:160])
        for f in _NICHE_TEXT_FIELDS - {"name"}:
            if f in data:
                setattr(n, f, str(data.get(f) or "").strip() or None)
        if not n.default_language:
            n.default_language = "ru"
        if "active" in data:
            n.active = bool(data["active"])
        db.add(n)
        db.commit()
        db.refresh(n)
        return jsonify({"niche": _niche_dict(n, db)}), 201
    finally:
        db.close()


@content_api.route("/niches/<int:niche_id>", methods=["GET"])
@require_auth
def get_niche(niche_id: int):
    db = SessionLocal()
    try:
        n = db.query(ContentNiche).filter_by(id=niche_id).first()
        if not n:
            return jsonify({"error": "Niche not found"}), 404
        out = _niche_dict(n, db)
        out["pillars"] = [
            _pillar_dict(p) for p in
            db.query(ContentPillar).filter_by(niche_id=n.id).order_by(ContentPillar.weight.desc()).all()
        ]
        return jsonify({"niche": out})
    finally:
        db.close()


@content_api.route("/niches/<int:niche_id>", methods=["PATCH"])
@require_auth
def update_niche(niche_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        n = db.query(ContentNiche).filter_by(id=niche_id).first()
        if not n:
            return jsonify({"error": "Niche not found"}), 404
        for f in _NICHE_TEXT_FIELDS:
            if f in data:
                val = str(data.get(f) or "").strip()
                if f == "name" and not val:
                    return jsonify({"error": "name cannot be empty"}), 400
                setattr(n, f, val or None if f != "name" else val)
        if "active" in data:
            n.active = bool(data["active"])
        n.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(n)
        return jsonify({"niche": _niche_dict(n, db)})
    finally:
        db.close()


# ---------------------------------------------------------------- pillars

def _pillar_dict(p: ContentPillar) -> dict:
    return {
        "id": p.id, "niche_id": p.niche_id, "name": p.name, "slug": p.slug,
        "description": p.description, "prompt_instructions": p.prompt_instructions,
        "allowed_topics": p.allowed_topics, "forbidden_topics": p.forbidden_topics,
        "visual_keywords": p.visual_keywords,
        "forbidden_visual_keywords": p.forbidden_visual_keywords,
        "weight": p.weight, "daily_video_limit": p.daily_video_limit,
        "active": p.active,
        "created_at": _iso(p.created_at), "updated_at": _iso(p.updated_at),
    }


_PILLAR_TEXT_FIELDS = {
    "name", "description", "prompt_instructions", "allowed_topics",
    "forbidden_topics", "visual_keywords", "forbidden_visual_keywords",
}


@content_api.route("/niches/<int:niche_id>/pillars", methods=["GET"])
@require_auth
def list_pillars(niche_id: int):
    db = SessionLocal()
    try:
        if not db.query(ContentNiche).filter_by(id=niche_id).first():
            return jsonify({"error": "Niche not found"}), 404
        rows = (
            db.query(ContentPillar).filter_by(niche_id=niche_id)
            .order_by(ContentPillar.weight.desc()).all()
        )
        return jsonify({"pillars": [_pillar_dict(p) for p in rows]})
    finally:
        db.close()


@content_api.route("/niches/<int:niche_id>/pillars", methods=["POST"])
@require_auth
def create_pillar(niche_id: int):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    db = SessionLocal()
    try:
        if not db.query(ContentNiche).filter_by(id=niche_id).first():
            return jsonify({"error": "Niche not found"}), 404
        slug = str(data.get("slug") or "").strip() or _slugify(name)
        if db.query(ContentPillar).filter_by(niche_id=niche_id, slug=slug).first():
            return jsonify({"error": f"Pillar slug '{slug}' already exists in this niche"}), 409
        p = ContentPillar(niche_id=niche_id, name=name[:160], slug=slug[:160])
        for f in _PILLAR_TEXT_FIELDS - {"name"}:
            if f in data:
                setattr(p, f, str(data.get(f) or "").strip() or None)
        if "weight" in data:
            p.weight = max(0, int(data.get("weight") or 0))
        if "daily_video_limit" in data:
            p.daily_video_limit = max(0, int(data.get("daily_video_limit") or 0))
        if "active" in data:
            p.active = bool(data["active"])
        db.add(p)
        db.commit()
        db.refresh(p)
        return jsonify({"pillar": _pillar_dict(p)}), 201
    finally:
        db.close()


@content_api.route("/pillars/<int:pillar_id>", methods=["PATCH"])
@require_auth
def update_pillar(pillar_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        p = db.query(ContentPillar).filter_by(id=pillar_id).first()
        if not p:
            return jsonify({"error": "Pillar not found"}), 404
        for f in _PILLAR_TEXT_FIELDS:
            if f in data:
                val = str(data.get(f) or "").strip()
                if f == "name" and not val:
                    return jsonify({"error": "name cannot be empty"}), 400
                setattr(p, f, val or None if f != "name" else val)
        if "weight" in data:
            try:
                p.weight = max(0, int(data["weight"]))
            except (TypeError, ValueError):
                return jsonify({"error": "weight must be an integer"}), 400
        if "daily_video_limit" in data:
            try:
                p.daily_video_limit = max(0, int(data["daily_video_limit"]))
            except (TypeError, ValueError):
                return jsonify({"error": "daily_video_limit must be an integer"}), 400
        if "active" in data:
            p.active = bool(data["active"])
        p.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(p)
        return jsonify({"pillar": _pillar_dict(p)})
    finally:
        db.close()


@content_api.route("/pillars/<int:pillar_id>", methods=["DELETE"])
@require_auth
def delete_pillar(pillar_id: int):
    db = SessionLocal()
    try:
        p = db.query(ContentPillar).filter_by(id=pillar_id).first()
        if not p:
            return jsonify({"error": "Pillar not found"}), 404
        linked = db.query(VideoProject).filter_by(content_pillar_id=p.id).count()
        if linked:
            # soft delete: history stays intact
            p.active = False
            p.updated_at = datetime.utcnow()
            db.commit()
            return jsonify({"pillar": _pillar_dict(p), "soft_deleted": True,
                            "linked_projects": linked})
        db.delete(p)
        db.commit()
        return jsonify({"ok": True, "deleted": True})
    finally:
        db.close()


# ------------------------------------------------- channel automation API

@content_api.route("/channels/<int:channel_id>/enable-generation", methods=["POST"])
@content_api.route("/channels/<int:channel_id>/disable-generation", methods=["POST"])
@require_auth
def toggle_generation(channel_id: int):
    enable = request.path.endswith("enable-generation")
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        if enable:
            ready, problems = generation_readiness(db, c)
            if not ready:
                return jsonify({"error": "Channel is not ready for automatic generation",
                                "problems": problems}), 409
        c.automatic_generation_enabled = enable
        db.commit()
        return jsonify({"automatic_generation_enabled": c.automatic_generation_enabled})
    finally:
        db.close()


@content_api.route("/channels/<int:channel_id>/enable-publishing", methods=["POST"])
@content_api.route("/channels/<int:channel_id>/disable-publishing", methods=["POST"])
@require_auth
def toggle_publishing(channel_id: int):
    enable = request.path.endswith("enable-publishing")
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        if enable and (not c.youtube_channel_id or c.youtube_connection_status != "connected"):
            return jsonify({"error": "YouTube is not connected for this channel"}), 409
        c.automatic_publishing_enabled = enable
        db.commit()
        return jsonify({"automatic_publishing_enabled": c.automatic_publishing_enabled})
    finally:
        db.close()


@content_api.route("/channels/<int:channel_id>/test-connection", methods=["POST"])
@require_auth
def channel_test_connection(channel_id: int):
    """Delegates to the existing YouTube verify logic (no duplicate OAuth)."""
    from publications_api import channel_youtube_verify
    return channel_youtube_verify(channel_id)


def generation_readiness(db, c: Channel) -> tuple[bool, list[str]]:
    problems = []
    if not c.niche_id:
        problems.append("niche_not_selected")
    else:
        niche = db.query(ContentNiche).filter_by(id=c.niche_id).first()
        if not niche or not niche.active:
            problems.append("niche_missing_or_inactive")
        else:
            active_pillars = (
                db.query(ContentPillar)
                .filter_by(niche_id=c.niche_id, active=True).count()
            )
            if not active_pillars:
                problems.append("no_active_pillars")
    if not (c.language or "").strip():
        problems.append("language_not_set")
    if not c.daily_video_limit:
        problems.append("daily_video_limit_not_set")
    return (not problems), problems


@content_api.route("/channels/<int:channel_id>/generation-readiness", methods=["GET"])
@require_auth
def channel_generation_readiness(channel_id: int):
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        ready, problems = generation_readiness(db, c)
        publish_problems = []
        if not c.youtube_channel_id or c.youtube_connection_status != "connected":
            publish_problems.append("youtube_not_connected")
        if not c.automatic_publishing_enabled:
            publish_problems.append("automatic_publishing_disabled")
        return jsonify({
            "generation_ready": ready and c.automatic_generation_enabled,
            "generation_configured": ready,
            "generation_problems": problems + ([] if c.automatic_generation_enabled else ["automatic_generation_disabled"]),
            "publishing_ready": not publish_problems,
            "publishing_problems": publish_problems,
        })
    finally:
        db.close()


# --------------------------------------------------- weighted pillar rotation

def pick_pillar(db, channel: Channel, *, now=None) -> ContentPillar | None:
    """Weighted rotation with anti-monotony protection:
    - inactive pillars and pillars at their daily limit are excluded;
    - the pillar used by the channel's most recent project gets its weight
      halved so the top-weight pillar cannot monopolize output."""
    now = now or datetime.utcnow()
    if not channel.niche_id:
        return None
    pillars = (
        db.query(ContentPillar)
        .filter_by(niche_id=channel.niche_id, active=True)
        .all()
    )
    if not pillars:
        return None
    day_start = now - timedelta(days=1)
    todays = dict(
        (pid, cnt) for pid, cnt in
        db.query(VideoProject.content_pillar_id, __import__("sqlalchemy").func.count(VideoProject.id))
        .filter(VideoProject.channel_id == channel.id,
                VideoProject.created_at >= day_start,
                VideoProject.content_pillar_id.isnot(None))
        .group_by(VideoProject.content_pillar_id).all()
    )
    last_project = (
        db.query(VideoProject)
        .filter(VideoProject.channel_id == channel.id,
                VideoProject.content_pillar_id.isnot(None))
        .order_by(VideoProject.created_at.desc()).first()
    )
    last_pillar_id = last_project.content_pillar_id if last_project else None
    weighted = []
    for p in pillars:
        if p.daily_video_limit and todays.get(p.id, 0) >= p.daily_video_limit:
            continue
        w = max(0, p.weight or 0)
        if p.id == last_pillar_id:
            w = max(1, w // 2)  # anti-monotony
        if w > 0:
            weighted.append((w, p))
    if not weighted:
        return None
    total = sum(w for w, _ in weighted)
    r = random.uniform(0, total)
    upto = 0.0
    for w, p in weighted:
        upto += w
        if r <= upto:
            return p
    return weighted[-1][1]


# ----------------------------------------------------------- topic generator

def _normalize_title(title: str) -> str:
    t = re.sub(r"[^\wа-яёa-z0-9 ]", " ", (title or "").lower())
    return " ".join(sorted(set(t.split())))[:300]


def _topic_duplicate_score(db, channel_id: int, title: str, topic: str) -> float:
    """0..1: keyword overlap with recent channel topics inside cooldown."""
    cutoff = datetime.utcnow() - timedelta(days=settings.TOPIC_COOLDOWN_DAYS)
    recent = (
        db.query(ChannelIdea)
        .filter(ChannelIdea.channel_id == channel_id, ChannelIdea.created_at >= cutoff)
        .order_by(ChannelIdea.created_at.desc()).limit(100).all()
    )
    words = set(_normalize_title(f"{title} {topic}").split())
    if not words or not recent:
        return 0.0
    best = 0.0
    for idea in recent:
        other = set(_normalize_title(f"{idea.title} {idea.topic or ''}").split())
        if not other:
            continue
        overlap = len(words & other) / max(1, min(len(words), len(other)))
        best = max(best, overlap)
    return round(best, 2)


@content_api.route("/channels/<int:channel_id>/generate-topic", methods=["POST"])
@require_auth
def generate_topic(channel_id: int):
    """Topic Generator: requires channel + niche + pillar + language. Every
    topic belongs to a concrete ContentPillar and passes duplicate/safety
    checks before being saved as a ChannelIdea."""
    from openai_client import OpenAIClientError, generate_json_with_retry, is_openai_enabled

    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        if not c.niche_id:
            return jsonify({"error": "Channel has no niche selected"}), 409
        niche = db.query(ContentNiche).filter_by(id=c.niche_id).first()
        if not niche:
            return jsonify({"error": "Niche not found"}), 409
        pillar_id = data.get("content_pillar_id")
        if pillar_id:
            pillar = db.query(ContentPillar).filter_by(id=int(pillar_id)).first()
            if not pillar or pillar.niche_id != niche.id:
                return jsonify({"error": "Pillar does not belong to this channel's niche"}), 400
            if not pillar.active:
                return jsonify({"error": "Pillar is inactive"}), 409
        else:
            pillar = pick_pillar(db, c)
            if not pillar:
                return jsonify({"error": "No active pillar available (weights/daily limits exhausted)"}), 409
        language = (data.get("language") or c.language or niche.default_language or "").strip()
        if not language:
            return jsonify({"error": "language is required"}), 400
        if not is_openai_enabled():
            return jsonify({"error": "OPENAI_API_KEY is not configured; topic generation unavailable"}), 503

        cutoff = datetime.utcnow() - timedelta(days=settings.TOPIC_COOLDOWN_DAYS)
        recent_titles = [
            i.title for i in db.query(ChannelIdea)
            .filter(ChannelIdea.channel_id == c.id, ChannelIdea.created_at >= cutoff)
            .order_by(ChannelIdea.created_at.desc()).limit(30).all()
        ]

        def _validate(payload: dict) -> None:
            if not str(payload.get("title") or "").strip():
                raise ValueError("title required")
            if not str(payload.get("topic") or "").strip():
                raise ValueError("topic required")

        system_prompt = (
            "You generate ONE YouTube Shorts topic for a specific channel/niche/pillar. "
            'Respond with JSON: {"title","hook","topic","angle","audience_interest",'
            '"visual_potential","safety_notes"}. Write in the requested language. '
            "Speculative practices (numerology, astrology, esoteric claims) must be framed as "
            "tradition/belief ('в нумерологии считается', 'астрологи связывают'), never as proven fact. "
            "Never promise health cures, guaranteed money, partner return; never threaten curses. "
            "Avoid the recent topics provided."
        )
        user_prompt = json.dumps({
            "niche": {"name": niche.name, "forbidden_topics": niche.forbidden_topics},
            "pillar": {"name": pillar.name, "description": pillar.description,
                       "prompt_instructions": pillar.prompt_instructions,
                       "allowed_topics": pillar.allowed_topics,
                       "forbidden_topics": pillar.forbidden_topics},
            "language": language,
            "target_audience": c.target_audience,
            "desired_duration_seconds": c.default_video_duration_seconds,
            "recent_topics": recent_titles,
        }, ensure_ascii=False)

        last_error = None
        for _ in range(settings.TOPIC_MAX_GENERATION_ATTEMPTS):
            try:
                result = generate_json_with_retry(
                    system_prompt=system_prompt, user_prompt=user_prompt,
                    validator=_validate, max_output_tokens=700, temperature=0.9,
                )
            except OpenAIClientError as exc:
                return jsonify({"error": f"Topic generation failed: {exc}"}), 502
            payload = result.payload or {}
            title = str(payload.get("title") or "").strip()
            topic = str(payload.get("topic") or "").strip()
            full_text = f"{title} {payload.get('hook') or ''} {topic}"
            violations = check_content_safety(full_text)
            if violations:
                last_error = f"safety_rejected: {violations}"
                continue
            dup = _topic_duplicate_score(db, c.id, title, topic)
            if dup >= settings.TOPIC_DUPLICATE_THRESHOLD:
                last_error = f"duplicate_score {dup} >= threshold"
                continue
            idea = ChannelIdea(
                channel_id=c.id, title=title[:300], topic=topic[:300],
                category=pillar.name[:120], source="generated", status="new",
                content_pillar_id=pillar.id,
                normalized_title=_normalize_title(title),
                hook_concept=str(payload.get("hook") or "")[:500] or None,
                summary=str(payload.get("angle") or "")[:500] or None,
            )
            db.add(idea)
            db.commit()
            db.refresh(idea)
            return jsonify({"topic": {
                "id": idea.id, "title": title, "hook": payload.get("hook"),
                "topic": topic, "angle": payload.get("angle"),
                "content_pillar_id": pillar.id, "content_pillar_name": pillar.name,
                "audience_interest": payload.get("audience_interest"),
                "visual_potential": payload.get("visual_potential"),
                "safety_notes": payload.get("safety_notes") or [],
                "duplicate_score": dup,
            }}), 201
        return jsonify({"error": f"Could not generate a unique safe topic: {last_error}"}), 422
    finally:
        db.close()


# ------------------------------------------------------- esotericism seed

ESOTERICISM_PILLARS = [
    {"name": "Знаки Вселенной", "slug": "universe-signs", "weight": 20,
     "allowed_topics": "повторяющиеся события; неожиданные совпадения; символы; внутренние ощущения; предупреждающие знаки; значимые встречи",
     "visual_keywords": "person noticing detail, clock closeup, repeating numbers, road ahead, window light, dramatic sky, calm atmospheric scene"},
    {"name": "Энергия человека", "slug": "human-energy", "weight": 15,
     "allowed_topics": "эмоциональное состояние; энергетическое истощение; восстановление; личные границы; влияние окружения; внутренний баланс",
     "visual_keywords": "person alone thoughtful, meditation calm, nature peaceful, deep breathing, soft light, tired person, recovery rest"},
    {"name": "Сны и их значения", "slug": "dream-meanings", "weight": 15,
     "allowed_topics": "повторяющиеся сны; падение; вода; полёт; преследование; знакомые люди; дома; дороги; животные во сне",
     "visual_keywords": "person sleeping in bed at night, closed eyes closeup, night bedroom, fog mist, calm water waves, dark forest, surreal dreamy scene"},
    {"name": "Духовное развитие", "slug": "spiritual-growth", "weight": 10,
     "allowed_topics": "осознанность; принятие себя; внутреннее спокойствие; освобождение от прошлого; изменение привычек; личная трансформация",
     "visual_keywords": "sunrise meditation, person mountain view, journaling calm, walking alone nature, candle quiet room"},
    {"name": "Карма", "slug": "karma", "weight": 8,
     "allowed_topics": "последствия поступков; повторяющиеся жизненные ситуации; ответственность; отношения; жизненные уроки",
     "forbidden_topics": "карма как доказанный научный факт",
     "visual_keywords": "cause and effect symbolic, mirror reflection person, path crossroads, falling dominoes, helping hand"},
    {"name": "Нумерология", "slug": "numerology", "weight": 8,
     "allowed_topics": "повторяющиеся числа; дата рождения; числовые символы; популярные трактовки чисел",
     "forbidden_topics": "нумерология как научно подтверждённый метод",
     "prompt_instructions": "Используй формулировки: 'в нумерологии считается', 'сторонники нумерологии трактуют', 'в эзотерической традиции это связывают'.",
     "visual_keywords": "digital clock 11:11, house numbers, calendar closeup, handwritten numbers, phone screen numbers"},
    {"name": "Астрология", "slug": "astrology", "weight": 5,
     "allowed_topics": "знаки зодиака; характер; отношения; общие астрологические трактовки; периоды перемен",
     "forbidden_topics": "астрология как научный факт",
     "prompt_instructions": "Используй формулировки: 'в астрологии считается', 'астрологи связывают', 'согласно популярной астрологической трактовке'.",
     "visual_keywords": "starry night sky, constellations, telescope night, zodiac symbols aesthetic, moon phases"},
    {"name": "Энергетика отношений", "slug": "relationship-energy", "weight": 5,
     "allowed_topics": "эмоциональная связь; привязанность; личные границы; токсичные отношения; ощущение дистанции; восстановление после расставания",
     "forbidden_topics": "советы прекращать отношения на основании мистических признаков; опасные советы",
     "visual_keywords": "couple distant silhouettes, holding hands closeup, person walking away, two coffee cups, emotional conversation"},
    {"name": "Подсознание и интуиция", "slug": "subconscious-intuition", "weight": 12,
     "allowed_topics": "внутреннее ощущение; реакция тела; сомнения; принятие решений; наблюдение за собой",
     "prompt_instructions": "Разделяй психологические объяснения, эзотерические интерпретации и художественную подачу.",
     "visual_keywords": "person deep in thought, eyes closeup decision, heartbeat chest hand, fork in road, notebook writing"},
    {"name": "Мистические истории", "slug": "mystic-stories", "weight": 2,
     "allowed_topics": "необычные совпадения; легенды; необъяснимые истории; исторические мистические сюжеты; городские легенды",
     "forbidden_topics": "вымышленные события как подтверждённые факты",
     "visual_keywords": "old book candlelight, foggy street night, ancient ruins, vintage photographs, mysterious door"},
]


def seed_esotericism(db=None) -> ContentNiche:
    """Creates the starter esotericism niche + 10 pillars. Idempotent.
    Creates NO fake YouTube channel: the admin assigns the niche to a real
    connected channel through the UI."""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        niche = db.query(ContentNiche).filter_by(slug="esotericism").first()
        if not niche:
            niche = ContentNiche(
                name="Эзотерика", slug="esotericism",
                description=("Короткие познавательные и атмосферные ролики о символах, "
                             "духовных практиках, интуиции, снах, энергии, карме, "
                             "нумерологии и мистических явлениях."),
                default_language="ru",
                default_tone="спокойный, интригующий, атмосферный",
                default_visual_style="атмосферный, мистический, тёмные тона, читаемый текст",
                forbidden_topics=("лечение болезней эзотерикой; отказ от врачей; гарантированный доход; "
                                  "возвращение партнёра; проклятия и запугивание; переводы денег; "
                                  "медицинские диагнозы; одержимость; паранойя; зависимость от предсказаний"),
                forbidden_visuals="graphic violence, medical procedures, gambling, casino, money scam imagery",
                disclaimer_policy="ENTERTAINMENT_AND_CULTURAL_INTERPRETATION",
                factuality_policy="ENTERTAINMENT_AND_CULTURAL_INTERPRETATION",
                sensitive_topics_policy="ENTERTAINMENT_AND_CULTURAL_INTERPRETATION",
            )
            db.add(niche)
            db.flush()
        for spec in ESOTERICISM_PILLARS:
            if not db.query(ContentPillar).filter_by(niche_id=niche.id, slug=spec["slug"]).first():
                db.add(ContentPillar(
                    niche_id=niche.id,
                    name=spec["name"], slug=spec["slug"],
                    weight=spec.get("weight", 10),
                    daily_video_limit=3,
                    allowed_topics=spec.get("allowed_topics"),
                    forbidden_topics=spec.get("forbidden_topics"),
                    prompt_instructions=spec.get("prompt_instructions"),
                    visual_keywords=spec.get("visual_keywords"),
                    forbidden_visual_keywords="cars traffic, office desk, party crowd, outer space, unrelated buildings, big logo, embedded text, watermark",
                ))
        db.commit()
        db.refresh(niche)
        return niche
    finally:
        if own:
            db.close()
