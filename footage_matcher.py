import logging
from dataclasses import dataclass
from pathlib import Path

from footage.providers.pexels import download_video as download_pexels_video
from footage.providers.pexels import search_videos as search_pexels_videos
from footage.providers.pixabay import download_video as download_pixabay_video
from footage.providers.pixabay import search_videos as search_pixabay_videos
from footage.ranking import BANNED_TOKENS, is_rejected, near_duplicate, select_best_clip
from footage.shots import DEFAULT_SCENE_QUERIES, ShotSpec
from footage.types import VideoResult
from saas_settings import settings


logger = logging.getLogger(__name__)


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


def _ensure_safe_library(orientation: str) -> list[VideoResult]:
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

    neutral_queries = ["office work", "city street", "nature landscape", "hands typing", "people walking"]
    gathered: list[VideoResult] = []
    used = set()
    for q in neutral_queries:
        candidates = _search_all(q, orientation, 3, 20, 8)
        for c in candidates:
            cid = f"{c.provider}:{c.video_id}"
            if cid in used or is_rejected(c):
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


def match_shots(shot_specs: list[ShotSpec], orientation: str) -> list[MatchedClip]:
    already_selected = {
        "ids": set(),
        "authors": set(),
        "tag_signatures": [],
        "query_groups_used": {},
        "selected_results": [],
    }
    matches: list[MatchedClip] = []
    for shot_index, spec in enumerate(shot_specs):
        candidate_pool: list[VideoResult] = []
        rejected_count = 0
        used_query = ""
        query_order = [*spec.queries, *spec.fallback_queries, DEFAULT_SCENE_QUERIES.get(spec.desired_scene, "real life")]
        for query in query_order:
            q = str(query or "").strip()
            if not q:
                continue
            qlow = q.lower()
            if any(tok in qlow for tok in BANNED_TOKENS):
                continue
            used_query = q
            fetched = _search_all(
                query=q,
                orientation=orientation,
                min_duration=max(2, int(spec.duration_s) - 1),
                max_duration=max(8, int(spec.duration_s) + 30),
                limit=12,
            )
            rejected_count += sum(1 for x in fetched if is_rejected(x))
            filtered = _filter_duplicates([x for x in fetched if not is_rejected(x)], already_selected)
            candidate_pool.extend(filtered)
            best = select_best_clip(spec, candidate_pool, already_selected=already_selected, orientation=orientation)
            if best:
                break

        best = select_best_clip(spec, candidate_pool, already_selected=already_selected, orientation=orientation)
        if not best:
            safe_pool = _ensure_safe_library(orientation)
            safe_pool = _filter_duplicates(safe_pool, already_selected)
            best = select_best_clip(spec, safe_pool, already_selected=already_selected, orientation=orientation)
            if not best:
                raise RuntimeError(f"footage_not_found_for_shot_{shot_index}")

        chosen = best.candidate
        clip_path = chosen.download_url if chosen.provider == "safe_broll" else _download(chosen)
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
                score=float(best.score),
                score_breakdown=dict(best.breakdown or {}),
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
            best.score,
        )
    return matches
