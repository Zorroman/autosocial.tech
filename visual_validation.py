"""Visual AI validation of footage candidates against a scene's visual intent.

Chain: channel profile -> niche -> pillar -> topic -> scene -> visual intent
-> shot intents -> candidates -> metadata filter -> frame extraction ->
visual AI validation -> scoring -> reservation -> render.

Providers (VISUAL_AI_PROVIDER):
- "mock":      deterministic keyword-based evaluation, no network (tests/dev);
- "openai":    production provider — sends downscaled frames to a vision
               model (requires OPENAI_API_KEY and quota);
- "disabled":  validation off (VISUAL_VALIDATION_ENABLED=false);
- degraded:    provider errors + VISUAL_VALIDATION_FAIL_OPEN=true accept the
               candidate with a recorded fallback_reason (never silent).

Results are cached in VisualValidationRecord by
(footage_asset_id, visual_intent_hash, model, prompt_version), so the same
clip is never re-analysed for the same intent. Frame files are temporary and
removed after evaluation.
"""
import base64
import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app_models import FootageAsset, VisualValidationRecord
from app_settings import settings

PROMPT_VERSION = "v1"
_FRAME_POSITIONS = (0.15, 0.35, 0.55, 0.75, 0.90)


# ------------------------------------------------------------ visual intent

def build_visual_intent(*, scene_text: str, niche_slug: str = "",
                        pillar: dict | None = None,
                        channel_visual_style: str = "") -> dict:
    """Rule-based visual intent (no paid calls): concrete Pexels-friendly
    queries from pillar visual keywords, avoid-list from forbidden keywords."""
    pillar = pillar or {}
    keywords = [k.strip() for k in (pillar.get("visual_keywords") or "").split(",") if k.strip()]
    forbidden = [k.strip() for k in (pillar.get("forbidden_visual_keywords") or "").split(",") if k.strip()]
    text = (scene_text or "").lower()
    people_required = any(w in text for w in ("человек", "люди", "он ", "она ", "вы ", "вам", "person"))
    return {
        "channel_niche": niche_slug or None,
        "content_pillar": pillar.get("slug") or pillar.get("name"),
        "primary_subjects": keywords[:4],
        "actions": [],
        "setting": [],
        "mood": [m.strip() for m in (channel_visual_style or "").split(",")[:3] if m.strip()],
        "time_of_day": "night" if any(w in text for w in ("ноч", "сон", "снит", "спит", "night")) else None,
        "visual_details": [],
        "avoid": forbidden,
        "abstract_allowed": False,
        "people_required": people_required,
        "preferred_shot_types": ["establishing", "medium", "close-up", "detail", "reaction", "environment"],
        "search_queries": keywords[:6],
    }


def visual_intent_hash(intent: dict) -> str:
    return hashlib.sha256(
        json.dumps(intent, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def build_shot_intents(intent: dict, segment_count: int) -> list[dict]:
    """Related shots inside one semantic scene: establishing -> close-up ->
    reaction/environment, all tied to the same visual intent."""
    order = ["establishing", "close-up", "reaction", "detail", "environment", "medium"]
    shots = []
    queries = intent.get("search_queries") or []
    for i in range(segment_count):
        shot_type = order[i % len(order)]
        q = queries[i % len(queries)] if queries else ""
        shots.append({"shot_type": shot_type, "search_query": q, "intent": intent})
    return shots


# ---------------------------------------------------------------- frames

def extract_frames(video_path: Path, out_dir: Path, duration: float | None) -> list[Path]:
    """Representative frames at 15/35/55/75/90% of duration, downscaled."""
    out_dir.mkdir(parents=True, exist_ok=True)
    dur = float(duration or 0)
    if dur <= 0:
        dur = 4.0
    frames = []
    count = min(settings.VISUAL_FRAME_COUNT, len(_FRAME_POSITIONS))
    for i, pos in enumerate(_FRAME_POSITIONS[:count]):
        t = max(0.0, dur * pos)
        f = out_dir / f"frame_{i}.jpg"
        proc = subprocess.run(
            [settings.FFMPEG_BIN, "-y", "-ss", f"{t:.2f}", "-i", str(video_path),
             "-frames:v", "1", "-vf", "scale=384:-2", "-q:v", "6", str(f)],
            capture_output=True, timeout=30,
        )
        if proc.returncode == 0 and f.exists():
            frames.append(f)
    return frames


# ---------------------------------------------------------------- result

@dataclass
class VisualValidationResult:
    relevance_score: float = 0.0
    subject_match_score: float = 0.0
    action_match_score: float = 0.0
    setting_match_score: float = 0.0
    mood_match_score: float = 0.0
    technical_score: float = 0.0
    detected_objects: list = field(default_factory=list)
    detected_actions: list = field(default_factory=list)
    detected_setting: str = ""
    detected_mood: str = ""
    negative_matches: list = field(default_factory=list)
    contains_text: bool = False
    contains_logo: bool = False
    contains_watermark: bool = False
    people_visible: bool = False
    accepted: bool = False
    rejection_reason: str | None = None
    provider: str = ""
    cost: float | None = None
    degraded: bool = False
    fallback_reason: str | None = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _apply_rules(res: VisualValidationResult, intent: dict) -> VisualValidationResult:
    """Deterministic accept/reject rules on top of provider scores."""
    if res.contains_watermark:
        res.accepted, res.rejection_reason = False, "watermark"
        return res
    if res.contains_text:
        res.accepted, res.rejection_reason = False, "embedded_text"
        return res
    if intent.get("people_required") and not res.people_visible:
        res.accepted, res.rejection_reason = False, "people_required_absent"
        return res
    if res.negative_matches:
        res.accepted, res.rejection_reason = False, f"avoid_matched:{res.negative_matches[0]}"
        return res
    if res.relevance_score < settings.VISUAL_RELEVANCE_MIN_SCORE:
        res.accepted, res.rejection_reason = False, "low_relevance"
        return res
    if res.subject_match_score < settings.VISUAL_SUBJECT_MIN_SCORE:
        res.accepted, res.rejection_reason = False, "low_subject_match"
        return res
    res.accepted, res.rejection_reason = True, None
    return res


# -------------------------------------------------------------- providers

class VisualValidationProvider:
    name = "base"

    def evaluate(self, frames: list[Path], visual_intent: dict,
                 candidate_metadata: dict) -> VisualValidationResult:
        raise NotImplementedError


class MockVisualValidationProvider(VisualValidationProvider):
    """Deterministic, network-free: keyword overlap between candidate metadata
    (search_query/tags) and the visual intent."""
    name = "mock"

    def evaluate(self, frames, visual_intent, candidate_metadata):
        meta_text = " ".join([
            str(candidate_metadata.get("search_query") or ""),
            " ".join(candidate_metadata.get("tags") or []),
        ]).lower()
        subjects = [s.lower() for s in (visual_intent.get("primary_subjects") or [])]
        queries = [q.lower() for q in (visual_intent.get("search_queries") or [])]
        avoid = [a.lower() for a in (visual_intent.get("avoid") or [])]
        subj_words = set(w for s in subjects + queries for w in s.split())
        meta_words = set(meta_text.split())
        overlap = len(subj_words & meta_words) / max(1, len(subj_words)) if subj_words else 0.5
        negative = [a for a in avoid if a and all(w in meta_words for w in a.split())]
        res = VisualValidationResult(
            relevance_score=round(min(1.0, overlap * 2), 2),
            subject_match_score=round(min(1.0, overlap * 2), 2),
            action_match_score=0.5,
            setting_match_score=0.5,
            mood_match_score=0.5,
            technical_score=0.8,
            detected_objects=sorted(subj_words & meta_words)[:8],
            negative_matches=negative,
            contains_text="text" in meta_words or "watermark" in meta_words,
            contains_watermark="watermark" in meta_words,
            people_visible=any(w in meta_words for w in ("person", "people", "man", "woman", "human", "face")),
            provider=self.name, cost=0.0,
        )
        return _apply_rules(res, visual_intent)


class OpenAIVisualValidationProvider(VisualValidationProvider):
    """Production provider: sends downscaled frames to a vision model."""
    name = "openai"

    def evaluate(self, frames, visual_intent, candidate_metadata):
        import os

        from openai import OpenAI
        if not (os.getenv("OPENAI_API_KEY") or "").strip():
            raise RuntimeError("OPENAI_API_KEY not configured")
        client = OpenAI()
        content = [{"type": "text", "text": (
            "Evaluate whether these video frames match the visual intent. "
            "Respond with JSON only: {relevance_score, subject_match_score, action_match_score, "
            "setting_match_score, mood_match_score, technical_score, detected_objects, detected_actions, "
            "detected_setting, detected_mood, negative_matches, contains_text, contains_logo, "
            "contains_watermark, people_visible}. Scores are 0..1. "
            f"Visual intent: {json.dumps(visual_intent, ensure_ascii=False)}"
        )}]
        for f in frames:
            b64 = base64.b64encode(f.read_bytes()).decode()
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}})
        resp = client.chat.completions.create(
            model=settings.VISUAL_AI_MODEL,
            messages=[{"role": "user", "content": content}],
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        res = VisualValidationResult(provider=self.name)
        for k in ("relevance_score", "subject_match_score", "action_match_score",
                  "setting_match_score", "mood_match_score", "technical_score"):
            setattr(res, k, float(data.get(k) or 0.0))
        for k in ("detected_objects", "detected_actions", "negative_matches"):
            setattr(res, k, list(data.get(k) or []))
        res.detected_setting = str(data.get("detected_setting") or "")
        res.detected_mood = str(data.get("detected_mood") or "")
        for k in ("contains_text", "contains_logo", "contains_watermark", "people_visible"):
            setattr(res, k, bool(data.get(k)))
        usage = getattr(resp, "usage", None)
        if usage:
            from ai_pricing import estimate_cost
            res.cost = estimate_cost("openai", settings.VISUAL_AI_MODEL,
                                     float(usage.prompt_tokens or 0),
                                     float(usage.completion_tokens or 0))
        return _apply_rules(res, visual_intent)


def get_provider() -> VisualValidationProvider | None:
    if not settings.VISUAL_VALIDATION_ENABLED:
        return None
    if settings.VISUAL_AI_PROVIDER == "openai":
        return OpenAIVisualValidationProvider()
    return MockVisualValidationProvider()


# ------------------------------------------------------------ validation

def validate_asset(db, asset: FootageAsset, intent: dict,
                   *, checks_done_today: int = 0) -> VisualValidationResult:
    """Cache-first validation with budget guard and honest degraded mode."""
    intent_hash = visual_intent_hash(intent)
    cached = (
        db.query(VisualValidationRecord)
        .filter_by(footage_asset_id=asset.id, visual_intent_hash=intent_hash,
                   model=settings.VISUAL_AI_MODEL, prompt_version=PROMPT_VERSION)
        .first()
    )
    if cached:
        res = VisualValidationResult(**{
            **json.loads(cached.scores_json or "{}"),
            "accepted": cached.accepted,
            "rejection_reason": cached.rejection_reason,
        })
        res.provider = cached.provider + ":cache"
        return res

    provider = get_provider()
    if provider is None:
        res = VisualValidationResult(accepted=True, provider="disabled",
                                     fallback_reason="validation_disabled")
        return res

    # budget guard (uses existing AI cost tracking)
    from ai_pricing import spent_summary
    spent = spent_summary(db)
    if spent["spent_today"] >= settings.VISUAL_AI_DAILY_BUDGET_USD + spent["daily_budget"]:
        res = VisualValidationResult(
            accepted=settings.VISUAL_VALIDATION_FAIL_OPEN, provider="budget_guard",
            degraded=True, fallback_reason="visual_ai_daily_budget_exceeded")
        return res

    frames: list[Path] = []
    tmp = None
    try:
        tmp = tempfile.TemporaryDirectory()
        frames = extract_frames(Path(asset.local_path), Path(tmp.name), asset.duration)
        meta = {"search_query": asset.search_query,
                "tags": json.loads(asset.tags_json) if asset.tags_json else []}
        res = provider.evaluate(frames, intent, meta)
    except Exception as exc:
        res = VisualValidationResult(
            accepted=settings.VISUAL_VALIDATION_FAIL_OPEN,
            provider=getattr(provider, "name", "unknown"), degraded=True,
            fallback_reason=f"provider_error: {str(exc)[:150]}")
        return res
    finally:
        if tmp:
            tmp.cleanup()  # temporary frames always removed

    # persist asset-level summary + intent-level cache
    asset.analysis_json = json.dumps({
        "detected_objects": res.detected_objects,
        "detected_setting": res.detected_setting,
        "detected_mood": res.detected_mood,
        "contains_text": res.contains_text,
        "contains_logo": res.contains_logo,
        "contains_watermark": res.contains_watermark,
        "people_visible": res.people_visible,
    }, ensure_ascii=False)
    asset.analysis_model = settings.VISUAL_AI_MODEL
    asset.analyzed_at = datetime.utcnow()
    db.add(VisualValidationRecord(
        footage_asset_id=asset.id, visual_intent_hash=intent_hash,
        provider=res.provider, model=settings.VISUAL_AI_MODEL,
        prompt_version=PROMPT_VERSION,
        scores_json=json.dumps({k: v for k, v in res.to_dict().items()
                                if k not in ("accepted", "rejection_reason")},
                               ensure_ascii=False),
        accepted=res.accepted, rejection_reason=res.rejection_reason,
        cost=res.cost,
    ))
    db.commit()
    if res.cost:
        from ai_pricing import record_cost
        record_cost(provider="openai", model=settings.VISUAL_AI_MODEL,
                    operation_type="other", actual_cost=res.cost,
                    request_id=f"visual:{asset.id}:{intent_hash[:12]}", db=db)
    return res
