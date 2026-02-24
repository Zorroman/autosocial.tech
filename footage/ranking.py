import hashlib
import math
from dataclasses import dataclass
from difflib import SequenceMatcher

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
    "work": {"office", "laptop", "typing", "meeting", "team", "business"},
    "nature": {"forest", "mountain", "river", "landscape", "sunrise"},
    "city": {"street", "traffic", "downtown", "skyline"},
    "people": {"people", "portrait", "talking", "walking"},
    "home": {"home", "kitchen", "living", "interior"},
    "food": {"food", "cooking", "dish", "kitchen"},
    "travel": {"travel", "tourist", "airport", "walking"},
    "product": {"product", "hands", "holding", "closeup"},
    "abstract_real": {"bokeh", "lights", "texture", "background"},
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


def is_rejected(metadata: VideoResult) -> bool:
    hay = _metadata_text(metadata)
    return any(x in hay for x in BANNED_TOKENS)


def penalty_score(metadata: VideoResult) -> float:
    hay = _metadata_text(metadata)
    return float(sum(1 for x in SOFT_BANNED_TOKENS if x in hay))


def _semantic_relevance(spec: ShotSpec, candidate: VideoResult) -> float:
    hay_tokens = _tokens(_metadata_text(candidate))
    query_tokens = set()
    for q in spec.queries:
        query_tokens |= _tokens(q)
    include_tokens = set(_tokens(" ".join(spec.must_include)))
    overlap = len(hay_tokens & query_tokens) / max(1.0, len(query_tokens))
    include_hit = len(hay_tokens & include_tokens) / max(1.0, len(include_tokens))
    soft_penalty = penalty_score(candidate) * 0.08
    return max(0.0, min(1.0, 0.62 * overlap + 0.48 * include_hit - soft_penalty))


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


def _diversity(spec: ShotSpec, candidate: VideoResult, already_selected: dict) -> float:
    score = 1.0
    candidate_id = f"{candidate.provider}:{candidate.video_id}"
    if candidate_id in already_selected.get("ids", set()):
        score -= 0.8
    author = str(candidate.author or "").strip().lower()
    if author and author in already_selected.get("authors", set()):
        score -= 0.55
    sig = _tag_signature(candidate)
    for used in already_selected.get("tag_signatures", []):
        if SequenceMatcher(None, sig, used).ratio() > 0.85:
            score -= 0.35
            break
    qgroups = already_selected.get("query_groups_used", {})
    qkey = (candidate.source_query or "").strip().lower()
    if qkey and qgroups.get(qkey, 0) >= 2:
        score -= min(0.4, 0.1 * qgroups.get(qkey, 0))
    return max(0.0, min(1.0, score))


@dataclass
class RankedCandidate:
    candidate: VideoResult
    score: float
    breakdown: dict


def rank_candidates(spec: ShotSpec, candidates: list[VideoResult], already_selected: dict, orientation: str) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for candidate in candidates:
        if is_rejected(candidate):
            continue
        semantic = _semantic_relevance(spec, candidate)
        scene = _scene_match(spec, candidate)
        duration = _duration_fit(spec, candidate)
        quality = _orientation_quality(spec, candidate, orientation=orientation)
        diversity = _diversity(spec, candidate, already_selected=already_selected)
        score = (
            40.0 * semantic
            + 20.0 * scene
            + 15.0 * duration
            + 15.0 * quality
            + 10.0 * diversity
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
                    "soft_penalty": round(penalty_score(candidate), 3),
                },
            )
        )
    ranked.sort(key=lambda x: (-x.score, x.candidate.provider, x.candidate.video_id))
    return ranked


def select_best_clip(spec: ShotSpec, candidates: list[VideoResult], already_selected: dict, orientation: str) -> RankedCandidate | None:
    ranked = rank_candidates(spec, candidates, already_selected=already_selected, orientation=orientation)
    if not ranked:
        return None
    return ranked[0]


def near_duplicate(a: VideoResult, b: VideoResult) -> bool:
    aa = f"{a.title} {' '.join(a.tags or [])}".strip().lower()
    bb = f"{b.title} {' '.join(b.tags or [])}".strip().lower()
    if not aa or not bb:
        return False
    return SequenceMatcher(None, aa, bb).ratio() > 0.85
