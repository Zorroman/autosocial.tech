import logging
from dataclasses import dataclass
from pathlib import Path

from footage.providers.pexels import download_video as download_pexels_video
from footage.providers.pexels import search_videos as search_pexels_videos
from footage.providers.pixabay import download_video as download_pixabay_video
from footage.providers.pixabay import search_videos as search_pixabay_videos
from footage.ranking import (
    BANNED_TOKENS,
    SCENE_KEYWORDS,
    is_rejected,
    near_duplicate,
    penalty_score,
    rank_candidates,
    select_best_clip,
)
from footage.shots import DEFAULT_SCENE_QUERIES, ShotSpec
from footage.types import VideoResult
from saas_settings import settings
from style_packs import get_style_pack, normalize_scene


logger = logging.getLogger(__name__)

MIN_ACCEPT_SCORE = 58.0
MIN_ACCEPT_SEMANTIC = 0.18
MIN_ACCEPT_SCENE = 0.12


@dataclass
class MatchedClip:
    shot_index: int
    phrase_index: int
    phrase_text: str
    clip_path: str
    provider: str
    clip_id: str
    clip_url: str
    duration_target: float
    start_trim_s: float
    end_trim_s: float
    query_used: str
    score: float
    score_breakdown: dict


def _search_all(query: str, orientation: str, min_duration: int, max_duration: int, limit: int) -> list[VideoResult]:
    out = []
    out.extend(search_pexels_videos(query, orientation, min_duration, max_duration, limit))
    out.extend(search_pixabay_videos(query, orientation, min_duration, max_duration, limit))
    return out


def _download(result: VideoResult) -> str:
    ext = ".mp4"
    target = Path(settings.FOOTAGE_CACHE_DIR) / f"{result.provider}_{result.video_id}{ext}"
    if result.provider == "pexels":
        return download_pexels_video(result, target)
    return download_pixabay_video(result, target)


def _safe_library_dir(orientation: str) -> Path:
    d = settings.CACHE_DIR / "safe_broll" / orientation
    d.mkdir(parents=True, exist_ok=True)
    return d


def _neutral_query_for_scene(scene: str) -> str:
    scene = str(scene or "").strip().lower()
    if scene == "work":
        return "office work"
    if scene == "city":
        return "city street"
    if scene == "nature":
        return "nature landscape"
    if scene == "product":
        return "hands holding product"
    if scene == "home":
        return "home interior"
    if scene == "people":
        return "people walking"
    return "real life broll"


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


def _candidate_in_allowed_scenes(candidate: VideoResult, allowed_scenes: set[str]) -> bool:
    if not allowed_scenes:
        return True
    hay = _metadata_text(candidate)
    if not hay.strip():
        return True
    for scene in allowed_scenes:
        keywords = SCENE_KEYWORDS.get(scene, set())
        if any(k in hay for k in keywords):
            return True
    return False


def _ensure_safe_library(orientation: str, allowed_scenes: set[str]) -> list[VideoResult]:
    lib_dir = _safe_library_dir(orientation)
    present = sorted([x for x in lib_dir.glob("*.mp4") if x.is_file()])
    if len(present) >= 20:
        return [
            VideoResult(
                provider="safe_broll",
                video_id=p.stem,
                duration=8,
                width=1080 if orientation == "vertical" else 1920,
                height=1920 if orientation == "vertical" else 1080,
                page_url="",
                download_url=str(p),
                tags=["safe", "neutral"],
                orientation=orientation,
                title=p.stem,
                description="safe_broll",
                author="safe_library",
            )
            for p in present[:20]
        ]

    query_scenes = [s for s in allowed_scenes if s in {"work", "city", "nature", "people", "home", "product", "abstract_real"}]
    if not query_scenes:
        query_scenes = ["work", "city", "nature", "people"]
    neutral_queries = [_neutral_query_for_scene(s) for s in query_scenes]

    gathered: list[VideoResult] = []
    used = set()
    for q in neutral_queries:
        candidates = _search_all(q, orientation, 3, 20, 8)
        for c in candidates:
            cid = f"{c.provider}:{c.video_id}"
            if cid in used or is_rejected(c):
                continue
            if not _candidate_in_allowed_scenes(c, allowed_scenes):
                continue
            used.add(cid)
            gathered.append(c)
            if len(gathered) >= 20:
                break
        if len(gathered) >= 20:
            break

    out = []
    for idx, c in enumerate(gathered):
        local = _download(c)
        src = Path(local)
        dst = lib_dir / f"safe_{idx:03d}_{c.provider}_{c.video_id}.mp4"
        if src.exists() and src.resolve() != dst.resolve():
            if not dst.exists():
                dst.write_bytes(src.read_bytes())
        out.append(
            VideoResult(
                provider="safe_broll",
                video_id=dst.stem,
                duration=max(3, int(c.duration or 8)),
                width=int(c.width or (1080 if orientation == "vertical" else 1920)),
                height=int(c.height or (1920 if orientation == "vertical" else 1080)),
                page_url=c.page_url,
                download_url=str(dst),
                tags=["safe", "neutral", *(c.tags or [])[:4]],
                orientation=orientation,
                title=c.title or dst.stem,
                description="safe_broll",
                author=c.author or "safe_library",
            )
        )
    return out


def _filter_duplicates(candidates: list[VideoResult], already_selected: dict) -> list[VideoResult]:
    out = []
    for c in candidates:
        cid = f"{c.provider}:{c.video_id}"
        if cid in already_selected["ids"]:
            continue
        duplicate = False
        for old in already_selected.get("selected_results", []):
            if near_duplicate(c, old):
                duplicate = True
                break
        if duplicate:
            continue
        out.append(c)
    return out


def _update_memory(chosen: VideoResult, query_used: str, already_selected: dict) -> None:
    already_selected["ids"].add(f"{chosen.provider}:{chosen.video_id}")
    author = str(chosen.author or "").strip().lower()
    if author:
        already_selected["authors"].add(author)
    sig = f"{chosen.title}|{' '.join(sorted(chosen.tags or []))}".lower()
    already_selected["tag_signatures"].append(sig)
    qkey = str(query_used or "").strip().lower()
    if qkey:
        already_selected["query_groups_used"][qkey] = int(already_selected["query_groups_used"].get(qkey, 0)) + 1
    already_selected["selected_results"].append(chosen)


def _build_hard_tokens(spec: ShotSpec, style_pack: dict) -> list[str]:
    out = [*(BANNED_TOKENS or []), *((style_pack.get("banned_tokens") or [])), *((spec.must_exclude or []))]
    uniq = []
    for token in out:
        t = str(token or "").strip().lower()
        if t and t not in uniq:
            uniq.append(t)
    return uniq


def _build_soft_tokens(spec: ShotSpec, style_pack: dict) -> list[str]:
    out = [*((style_pack.get("soft_banned_tokens") or [])), *((spec.soft_exclude or []))]
    uniq = []
    for token in out:
        t = str(token or "").strip().lower()
        if t and t not in uniq:
            uniq.append(t)
    return uniq


def _build_query_order(spec: ShotSpec, style_pack: dict, allowed_scenes: set[str]) -> list[str]:
    desired = normalize_scene(spec.desired_scene, list(allowed_scenes))
    scene_overrides = style_pack.get("scene_query_overrides") if isinstance(style_pack.get("scene_query_overrides"), dict) else {}
    overrides = scene_overrides.get(desired) if isinstance(scene_overrides, dict) else []
    if isinstance(overrides, str):
        overrides = [overrides]
    override_queries = [str(x).strip() for x in (overrides or []) if str(x).strip()][:2]
    fallback_scene_queries = [_neutral_query_for_scene(desired)]
    query_order = [*spec.queries, *override_queries, *spec.fallback_queries, *fallback_scene_queries]
    final = []
    for q in query_order:
        cur = str(q or "").strip()
        if cur and cur not in final:
            final.append(cur)
    return final


def _reselect_for_business_clean(
    spec: ShotSpec,
    candidate_pool: list[VideoResult],
    already_selected: dict,
    orientation: str,
    hard_tokens: list[str],
    soft_tokens: list[str],
) -> tuple[VideoResult | None, float, dict]:
    ranked = rank_candidates(
        spec,
        candidate_pool,
        already_selected=already_selected,
        orientation=orientation,
        hard_banned_tokens=hard_tokens,
        soft_banned_tokens=soft_tokens,
    )
    for item in ranked:
        if is_rejected(item.candidate, hard_banned_tokens=hard_tokens):
            continue
        if penalty_score(item.candidate, soft_banned_tokens=soft_tokens) > 0:
            continue
        return item.candidate, float(item.score), dict(item.breakdown or {})
    if ranked:
        return ranked[0].candidate, float(ranked[0].score), dict(ranked[0].breakdown or {})
    return None, 0.0, {}


def _is_ranked_good(best) -> bool:
    if not best:
        return False
    score = float(getattr(best, "score", 0.0) or 0.0)
    breakdown = dict(getattr(best, "breakdown", {}) or {})
    semantic = float(breakdown.get("semantic_relevance", 0.0) or 0.0)
    scene = float(breakdown.get("scene_match", 0.0) or 0.0)
    return score >= MIN_ACCEPT_SCORE and semantic >= MIN_ACCEPT_SEMANTIC and scene >= MIN_ACCEPT_SCENE


def match_shots(
    shot_specs: list[ShotSpec],
    orientation: str,
    style_pack: dict | None = None,
    minimize_repeats: bool = True,
    initial_memory: dict | None = None,
) -> list[MatchedClip]:
    style_pack = get_style_pack((style_pack or {}).get("id") if isinstance(style_pack, dict) else None)
    allowed_scenes = set(style_pack.get("allowed_scenes") or [])
    seed = initial_memory if isinstance(initial_memory, dict) else {}
    already_selected = {
        "ids": set(seed.get("ids") or []),
        "authors": set(seed.get("authors") or []),
        "tag_signatures": list(seed.get("tag_signatures") or []),
        "query_groups_used": dict(seed.get("query_groups_used") or {}),
        "selected_results": list(seed.get("selected_results") or []),
    }
    matches: list[MatchedClip] = []
    for shot_index, spec in enumerate(shot_specs):
        candidate_pool: list[VideoResult] = []
        rejected_count = 0
        used_query = ""
        spec.desired_scene = normalize_scene(spec.desired_scene, list(allowed_scenes))
        hard_tokens = _build_hard_tokens(spec, style_pack)
        soft_tokens = _build_soft_tokens(spec, style_pack)
        query_order = _build_query_order(spec, style_pack, allowed_scenes)
        for query in query_order:
            q = str(query or "").strip()
            if not q:
                continue
            qlow = q.lower()
            if any(tok in qlow for tok in hard_tokens):
                continue
            used_query = q
            fetched = _search_all(
                query=q,
                orientation=orientation,
                min_duration=max(2, int(spec.duration_s) - 1),
                max_duration=max(8, int(spec.duration_s) + 30),
                limit=12,
            )
            rejected_count += sum(1 for x in fetched if is_rejected(x, hard_banned_tokens=hard_tokens))
            clean = [x for x in fetched if not is_rejected(x, hard_banned_tokens=hard_tokens)]
            if allowed_scenes:
                clean = [x for x in clean if _candidate_in_allowed_scenes(x, allowed_scenes)]
            filtered = _filter_duplicates(clean, already_selected) if minimize_repeats else list(clean)
            candidate_pool.extend(filtered)
            best = select_best_clip(
                spec,
                candidate_pool,
                already_selected=already_selected,
                orientation=orientation,
                hard_banned_tokens=hard_tokens,
                soft_banned_tokens=soft_tokens,
            )
            if best and _is_ranked_good(best):
                break

        best = select_best_clip(
            spec,
            candidate_pool,
            already_selected=already_selected,
            orientation=orientation,
            hard_banned_tokens=hard_tokens,
            soft_banned_tokens=soft_tokens,
        )
        if best and not _is_ranked_good(best):
            logger.info(
                "shot %s: best clip below strict threshold score=%s semantic=%s scene=%s; keep provider clip for better topical relevance",
                shot_index,
                best.score,
                (best.breakdown or {}).get("semantic_relevance"),
                (best.breakdown or {}).get("scene_match"),
            )
        chosen = best.candidate if best else None
        score = float(best.score) if best else 0.0
        score_breakdown = dict(best.breakdown or {}) if best else {}

        if str(style_pack.get("id") or "") == "business_clean" and chosen:
            bad = is_rejected(chosen, hard_banned_tokens=hard_tokens) or penalty_score(chosen, soft_banned_tokens=soft_tokens) > 0
            if bad:
                logger.info("shot %s: business_clean reselect due to banned/soft token clip=%s:%s", shot_index, chosen.provider, chosen.video_id)
                alt_clip, alt_score, alt_breakdown = _reselect_for_business_clean(
                    spec,
                    candidate_pool,
                    already_selected=already_selected,
                    orientation=orientation,
                    hard_tokens=hard_tokens,
                    soft_tokens=soft_tokens,
                )
                if alt_clip:
                    chosen = alt_clip
                    score = alt_score
                    score_breakdown = alt_breakdown

        if not chosen:
            safe_pool = _ensure_safe_library(orientation, allowed_scenes=allowed_scenes)
            safe_pool = _filter_duplicates(safe_pool, already_selected) if minimize_repeats else list(safe_pool)
            best = select_best_clip(
                spec,
                safe_pool,
                already_selected=already_selected,
                orientation=orientation,
                hard_banned_tokens=hard_tokens,
                soft_banned_tokens=soft_tokens,
            )
            if not best:
                raise RuntimeError(f"footage_not_found_for_shot_{shot_index}")
            chosen = best.candidate
            score = float(best.score)
            score_breakdown = dict(best.breakdown or {})

        clip_path = chosen.download_url if chosen.provider == "safe_broll" else _download(chosen)
        if minimize_repeats:
            _update_memory(chosen, used_query, already_selected)
        end_trim = max(0.8, float(spec.duration_s))
        matches.append(
            MatchedClip(
                shot_index=shot_index,
                phrase_index=spec.phrase_index,
                phrase_text=spec.phrase_text,
                clip_path=str(Path(clip_path).resolve()),
                provider=chosen.provider,
                clip_id=chosen.video_id,
                clip_url=chosen.download_url,
                duration_target=float(spec.duration_s),
                start_trim_s=0.0,
                end_trim_s=end_trim,
                query_used=used_query,
                score=score,
                score_breakdown=score_breakdown,
            )
        )
        logger.info(
            "shot %s: query='%s' candidates=%s rejected=%s best=%s:%s score=%s",
            shot_index,
            used_query,
            len(candidate_pool),
            rejected_count,
            chosen.provider,
            chosen.video_id,
            score,
        )
    return matches
