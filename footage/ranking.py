import hashlib
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urlparse

from footage.shots import ShotSpec
from footage.types import VideoResult


BANNED_TOKENS = [
    "fantasy",
    "dragon",
    "alien",
    "ufo",
    "anime",
    "cartoon",
    "3d",
    "render",
    "cgi",
    "unreal",
    "ai generated",
    "midjourney",
    "stable diffusion",
    "illustration",
    "sci-fi",
    "space battle",
    "monster",
    "magic spell",
]
SOFT_BANNED_TOKENS = ["metaverse", "cyberpunk", "futuristic", "surreal", "neon"]
SCENE_KEYWORDS = {
    "work": {"office", "laptop", "typing", "meeting", "team", "business", "????????", "??????????????", "????????????", "????????????", "????????????????????"},
    "nature": {
        "forest", "mountain", "river", "landscape", "sunrise", "sea", "ocean", "beach", "lake", "waterfall", "fog", "mist",
        "??????????????", "??????", "????????", "????????", "????????????", "????????", "??????????", "??????????", "??????????", "??????????", "??????????",
    },
    "city": {"street", "traffic", "downtown", "skyline", "??????????", "??????????", "????????????", "??????????", "??????????????????"},
    "people": {"people", "portrait", "talking", "walking", "????????", "??????????????", "????????", "????????????????", "????????????"},
    "home": {"home", "kitchen", "living", "interior", "??????", "????????????????", "??????????", "????????????????"},
    "food": {"food", "cooking", "dish", "kitchen", "??????", "??????????????????", "??????????", "??????????"},
    "travel": {"travel", "tourist", "airport", "walking", "??????????????????????", "????????????", "????????????????", "??????????????"},
    "product": {"product", "hands", "holding", "closeup", "??????????????", "??????????", "????????", "??????????????"},
    "abstract_real": {"bokeh", "lights", "texture", "background", "candle", "smoke", "moonlight", "??????", "????????????????", "????????", "??????????", "??????"},
}
VISUAL_BUCKET_KEYWORDS = {
    "people": {"people", "person", "portrait", "team", "face", "client", "customer", "athlete", "chef", "artist", "therapist"},
    "hands": {"hands", "hand", "typing", "holding", "grip", "touch", "writing", "needle", "tool", "pouring"},
    "environment": {"interior", "workspace", "office", "room", "street", "landscape", "kitchen", "studio", "garage", "gym", "skyline"},
    "object": {"product", "detail", "closeup", "close-up", "macro", "cosmetic", "chart", "engine", "dish", "coffee", "keys"},
    "process": {"process", "workflow", "working", "repair", "training", "cooking", "serving", "meeting", "planning", "diagnostics"},
    "atmosphere": {"bokeh", "smoke", "mist", "moon", "stars", "galaxy", "sunrise", "sunset", "candle", "light", "texture"},
}


def _tokens(text: str) -> set[str]:
    out = set()
    cur = []
    for ch in str(text or "").lower():
        if ch.isalnum() or ch in {"-", "_"}:
            cur.append(ch)
        else:
            if cur:
                out.add("".join(cur))
                cur = []
    if cur:
        out.add("".join(cur))
    return out


def _metadata_text(candidate: VideoResult) -> str:
    return " ".join(
        [
            candidate.title or "",
            candidate.description or "",
            candidate.page_url or "",
            candidate.download_url or "",
            " ".join(candidate.tags or []),
            candidate.source_query or "",
        ]
    ).lower()


def candidate_unique_key(candidate: VideoResult) -> str:
    return candidate.unique_key()


def is_rejected(metadata: VideoResult, hard_banned_tokens: list[str] | None = None) -> bool:
    hay = _metadata_text(metadata)
    banned = hard_banned_tokens if isinstance(hard_banned_tokens, list) else BANNED_TOKENS
    return any(x in hay for x in banned)


def penalty_score(metadata: VideoResult, soft_banned_tokens: list[str] | None = None) -> float:
    hay = _metadata_text(metadata)
    soft = soft_banned_tokens if isinstance(soft_banned_tokens, list) else SOFT_BANNED_TOKENS
    return float(sum(1 for x in soft if x in hay))


def _semantic_relevance(spec: ShotSpec, candidate: VideoResult, soft_banned_tokens: list[str] | None = None) -> float:
    meta_text = _metadata_text(candidate)
    hay_tokens = _tokens(meta_text)
    query_tokens = set()
    for q in spec.queries:
        query_tokens |= _tokens(q)
    phrase_tokens = _tokens(spec.phrase_text or "")
    phrase_tokens = {t for t in phrase_tokens if len(t) >= 4}
    include_tokens = set(_tokens(" ".join(spec.must_include)))
    overlap = len(hay_tokens & query_tokens) / max(1.0, len(query_tokens))
    phrase_overlap = len(hay_tokens & phrase_tokens) / max(1.0, len(phrase_tokens)) if phrase_tokens else 0.0
    include_hit = len(hay_tokens & include_tokens) / max(1.0, len(include_tokens))
    source_query_tokens = _tokens(candidate.source_query or "")
    source_query_hit = len(source_query_tokens & query_tokens) / max(1.0, len(query_tokens))
    soft_penalty = penalty_score(candidate, soft_banned_tokens=soft_banned_tokens) * 0.08
    hard_hint_penalty = 0.2 if any(x in _metadata_text(candidate) for x in (spec.must_exclude or [])) else 0.0
    metadata_sparse_penalty = 0.18 if not (candidate.title or "").strip() and not (candidate.tags or []) else 0.0
    query_hint_boost = 0.24 if (candidate.source_query or "").strip() and any(q in str(candidate.source_query or "").lower() for q in (spec.queries or [])) else 0.0
    required_context_miss_penalty = 0.12 if include_tokens and include_hit <= 0.01 and str(getattr(spec, "niche_profile_id", "generic")) != "generic" else 0.0
    return max(
        0.0,
        min(
            1.0,
            0.46 * overlap
            + 0.34 * include_hit
            + 0.24 * phrase_overlap
            + 0.22 * source_query_hit
            + query_hint_boost
            - soft_penalty
            - hard_hint_penalty
            - metadata_sparse_penalty,
            - required_context_miss_penalty,
        ),
    )


def _scene_match(spec: ShotSpec, candidate: VideoResult) -> float:
    hay_tokens = _tokens(_metadata_text(candidate))
    scene = SCENE_KEYWORDS.get(spec.desired_scene, set())
    if not scene:
        return 0.5
    hit = len(hay_tokens & scene) / max(1.0, len(scene))
    return max(0.0, min(1.0, hit * 1.4))


def _duration_fit(spec: ShotSpec, candidate: VideoResult) -> float:
    need = max(0.6, float(spec.duration_s))
    got = max(0.1, float(candidate.duration or 0.1))
    if got >= need:
        return min(1.0, 0.75 + min(0.25, (got - need) / max(4.0, need * 2)))
    ratio = got / need
    return max(0.0, min(1.0, ratio * ratio))


def _orientation_quality(spec: ShotSpec, candidate: VideoResult, orientation: str) -> float:
    w = float(candidate.width or 0)
    h = float(candidate.height or 0)
    if w <= 0 or h <= 0:
        return 0.2
    ratio = w / h
    if orientation == "vertical":
        target = 9.0 / 16.0
        orientation_ok = 1.0 if h > w else 0.35
    else:
        target = 16.0 / 9.0
        orientation_ok = 1.0 if w > h else 0.35
    ratio_fit = max(0.0, 1.0 - abs(ratio - target) / target)
    px = max(w, h)
    resolution_fit = 1.0 if px >= 1920 else (0.85 if px >= 1080 else 0.55)
    fps = float(candidate.fps or 0)
    fps_fit = 1.0 if fps >= 24 else (0.6 if fps > 0 else 0.8)
    return max(0.0, min(1.0, 0.4 * orientation_ok + 0.3 * ratio_fit + 0.2 * resolution_fit + 0.1 * fps_fit))


def _tag_signature(candidate: VideoResult) -> str:
    base = f"{candidate.title}|{' '.join(sorted(candidate.tags or []))}"
    return hashlib.sha1(base.lower().encode("utf-8")).hexdigest()


def _source_query_bucket_value(candidate: VideoResult) -> str:
    return _query_bucket(candidate.source_query, "generic")


def _page_signature(candidate: VideoResult) -> str:
    raw = str(candidate.page_url or "").strip().lower()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        parts = [part for part in parsed.path.split("/") if part and not part.isdigit()]
        if parts:
            return "/".join(parts[-3:])
        return parsed.netloc or raw
    except Exception:
        return raw


def _tag_overlap_ratio(a: VideoResult, b: VideoResult) -> float:
    a_tags = {str(x or "").strip().lower() for x in (a.tags or []) if str(x or "").strip()}
    b_tags = {str(x or "").strip().lower() for x in (b.tags or []) if str(x or "").strip()}
    if not a_tags or not b_tags:
        return 0.0
    return len(a_tags & b_tags) / max(1.0, len(a_tags | b_tags))


def _infer_shot_size(candidate: VideoResult) -> str:
    explicit = str(candidate.shot_size or "").strip().lower()
    if explicit:
        return explicit
    meta = _metadata_text(candidate)
    if any(token in meta for token in ["closeup", "close up", "portrait", "macro", "hands"]):
        return "closeup"
    if any(token in meta for token in ["wide", "landscape", "skyline", "galaxy", "night sky", "forest", "mountain"]):
        return "wide"
    return "medium"


def _infer_motion_hint(candidate: VideoResult) -> str:
    explicit = str(candidate.motion_hint or "").strip().lower()
    if explicit:
        return explicit
    meta = _metadata_text(candidate)
    if any(token in meta for token in ["walking", "moving", "flow", "waves", "traffic", "rotation", "orbit"]):
        return "motion"
    return "static"


def _infer_visual_bucket(candidate: VideoResult, spec: ShotSpec | None = None) -> str:
    explicit = str(getattr(spec, "visual_bucket", "") or "").strip().lower()
    meta_text = _metadata_text(candidate)
    meta_tokens = _tokens(meta_text)
    for bucket in VISUAL_BUCKET_KEYWORDS:
        if bucket in meta_text:
            return bucket
    for bucket, keywords in VISUAL_BUCKET_KEYWORDS.items():
        if meta_tokens & keywords:
            return bucket
    if explicit:
        return explicit
    if _infer_shot_size(candidate) == "closeup":
        return "object"
    return "environment"


def _desired_visual_bucket(spec: ShotSpec) -> str:
    explicit = str(getattr(spec, "visual_bucket", "") or "").strip().lower()
    if explicit in VISUAL_BUCKET_KEYWORDS:
        return explicit
    scene = str(getattr(spec, "desired_scene", "") or "").strip().lower()
    if scene in {"product", "food"}:
        return "object"
    if scene in {"work"}:
        return "process"
    if scene in {"people"}:
        return "people"
    if scene in {"abstract_real"}:
        return "atmosphere"
    if scene in {"nature", "city", "home", "travel"}:
        return "environment"
    role = str(getattr(spec, "timeline_role", "") or "").strip().lower()
    if role == "hook":
        return "process"
    if role == "closing":
        return "atmosphere"
    return "environment"


def _query_bucket(query: str, fallback: str) -> str:
    q = str(query or "").strip().lower()
    if not q:
        return str(fallback or "generic").strip().lower() or "generic"
    return q.split()[0]


def _diversity(spec: ShotSpec, candidate: VideoResult, already_selected: dict) -> float:
    score = 1.0
    candidate_key = candidate_unique_key(candidate)
    if candidate_key in already_selected.get("ids", set()):
        score -= 0.9
    author = str(candidate.author or "").strip().lower()
    if author and author in already_selected.get("authors", set()):
        score -= 0.4
    sig = _tag_signature(candidate)
    for used in already_selected.get("tag_signatures", []):
        if SequenceMatcher(None, sig, used).ratio() > 0.85:
            score -= 0.35
            break
    qgroups = already_selected.get("query_groups_used", {})
    qkey = _query_bucket(candidate.source_query, spec.query_bucket)
    if qkey and qgroups.get(qkey, 0) >= 1:
        score -= min(0.28, 0.12 * qgroups.get(qkey, 0))
    recent_buckets = list(already_selected.get("recent_query_buckets", []) or [])
    if recent_buckets and qkey and recent_buckets[-1] == qkey:
        score -= 0.22
    recent_scenes = list(already_selected.get("recent_scene_keys", []) or [])
    if recent_scenes and spec.query_bucket and recent_scenes[-1] == spec.query_bucket:
        score -= 0.12
    recent_sizes = list(already_selected.get("recent_shot_sizes", []) or [])
    current_size = _infer_shot_size(candidate)
    if recent_sizes and recent_sizes[-1] == current_size:
        score -= 0.12
    recent_motion = list(already_selected.get("recent_motion_hints", []) or [])
    current_motion = _infer_motion_hint(candidate)
    if recent_motion and recent_motion[-1] == current_motion:
        score -= 0.08
    recent_visual_buckets = list(already_selected.get("recent_visual_buckets", []) or [])
    current_visual_bucket = _infer_visual_bucket(candidate, spec)
    if recent_visual_buckets and recent_visual_buckets[-1] == current_visual_bucket:
        score -= 0.14
    if len(recent_visual_buckets) >= 2 and recent_visual_buckets[-2:] == [current_visual_bucket, current_visual_bucket]:
        score -= 0.18
    return max(0.0, min(1.0, score))


def _near_duplicate_penalty(candidate: VideoResult, already_selected: dict) -> float:
    penalty = 0.0
    for old in already_selected.get("selected_results", []):
        if near_duplicate(candidate, old):
            penalty += 0.85
            break
    return max(0.0, min(1.0, penalty))


def _visual_balance(spec: ShotSpec, candidate: VideoResult, already_selected: dict) -> float:
    balance = 0.55
    current_visual_bucket = _infer_visual_bucket(candidate, spec)
    desired_visual_bucket = _desired_visual_bucket(spec)
    recent_visual_buckets = list(already_selected.get("recent_visual_buckets", []) or [])
    if recent_visual_buckets:
        if recent_visual_buckets[-1] == current_visual_bucket:
            balance -= 0.24
        if len(recent_visual_buckets) >= 2 and recent_visual_buckets[-2] == recent_visual_buckets[-1] == current_visual_bucket:
            balance -= 0.32
    recent_sizes = list(already_selected.get("recent_shot_sizes", []) or [])
    if recent_sizes and recent_sizes[-1] == _infer_shot_size(candidate):
        balance -= 0.14
    recent_motion = list(already_selected.get("recent_motion_hints", []) or [])
    if recent_motion and recent_motion[-1] == _infer_motion_hint(candidate):
        balance -= 0.08
    if desired_visual_bucket == current_visual_bucket:
        balance += 0.38
    else:
        balance += 0.04
    return max(0.0, min(1.0, balance))


@dataclass
class RankedCandidate:
    candidate: VideoResult
    score: float
    breakdown: dict


def rank_candidates(
    spec: ShotSpec,
    candidates: list[VideoResult],
    already_selected: dict,
    orientation: str,
    hard_banned_tokens: list[str] | None = None,
    soft_banned_tokens: list[str] | None = None,
) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for candidate in candidates:
        if is_rejected(candidate, hard_banned_tokens=hard_banned_tokens):
            continue
        semantic = _semantic_relevance(spec, candidate, soft_banned_tokens=soft_banned_tokens)
        scene = _scene_match(spec, candidate)
        duration = _duration_fit(spec, candidate)
        quality = _orientation_quality(spec, candidate, orientation=orientation)
        diversity = _diversity(spec, candidate, already_selected=already_selected)
        visual_balance = _visual_balance(spec, candidate, already_selected=already_selected)
        near_duplicate_penalty = _near_duplicate_penalty(candidate, already_selected=already_selected)
        duplicate_penalty = 1.0 if candidate_unique_key(candidate) in already_selected.get("ids", set()) else 0.0
        monotony_penalty = max(0.0, 1.0 - visual_balance)
        score = (
            30.0 * semantic
            + 15.0 * scene
            + 10.0 * duration
            + 14.0 * quality
            + 15.0 * diversity
            + 16.0 * visual_balance
            - 18.0 * duplicate_penalty
            - 12.0 * near_duplicate_penalty
            - 6.0 * monotony_penalty
        )
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                score=round(max(0.0, min(100.0, score)), 3),
                breakdown={
                    "semantic_relevance": round(semantic, 4),
                    "scene_match": round(scene, 4),
                    "duration_fit": round(duration, 4),
                    "quality_fit": round(quality, 4),
                    "diversity": round(diversity, 4),
                    "visual_balance": round(visual_balance, 4),
                    "duplicate_penalty": round(duplicate_penalty, 4),
                    "near_duplicate_penalty": round(near_duplicate_penalty, 4),
                    "monotony_penalty": round(monotony_penalty, 4),
                    "query_bucket": _query_bucket(candidate.source_query, spec.query_bucket),
                    "shot_size": _infer_shot_size(candidate),
                    "motion_hint": _infer_motion_hint(candidate),
                    "visual_bucket": _infer_visual_bucket(candidate, spec),
                    "soft_penalty": round(penalty_score(candidate, soft_banned_tokens=soft_banned_tokens), 3),
                },
            )
        )
    ranked.sort(key=lambda x: (-x.score, x.candidate.provider, x.candidate.video_id or candidate_unique_key(x.candidate)))
    return ranked


def select_best_clip(
    spec: ShotSpec,
    candidates: list[VideoResult],
    already_selected: dict,
    orientation: str,
    hard_banned_tokens: list[str] | None = None,
    soft_banned_tokens: list[str] | None = None,
) -> RankedCandidate | None:
    ranked = rank_candidates(
        spec,
        candidates,
        already_selected=already_selected,
        orientation=orientation,
        hard_banned_tokens=hard_banned_tokens,
        soft_banned_tokens=soft_banned_tokens,
    )
    if not ranked:
        return None
    return ranked[0]


def near_duplicate(a: VideoResult, b: VideoResult) -> bool:
    if candidate_unique_key(a) == candidate_unique_key(b):
        return True
    same_author = str(a.author or "").strip().lower() and str(a.author or "").strip().lower() == str(b.author or "").strip().lower()
    same_bucket = _source_query_bucket_value(a) and _source_query_bucket_value(a) == _source_query_bucket_value(b)
    same_visual_bucket = _infer_visual_bucket(a) == _infer_visual_bucket(b)
    same_shot_size = _infer_shot_size(a) == _infer_shot_size(b)
    same_motion = _infer_motion_hint(a) == _infer_motion_hint(b)
    tag_overlap = _tag_overlap_ratio(a, b)
    page_similarity = SequenceMatcher(None, _page_signature(a), _page_signature(b)).ratio() if (_page_signature(a) and _page_signature(b)) else 0.0
    if same_author and same_bucket and (same_visual_bucket or same_shot_size or same_motion or tag_overlap >= 0.35):
        return True
    if same_bucket and tag_overlap >= 0.6 and page_similarity >= 0.6:
        return True
    aa = f"{a.title} {' '.join(a.tags or [])}".strip().lower()
    bb = f"{b.title} {' '.join(b.tags or [])}".strip().lower()
    if not aa or not bb:
        return False
    return SequenceMatcher(None, aa, bb).ratio() > 0.85
