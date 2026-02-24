from dataclasses import dataclass
from pathlib import Path

from footage.providers.pexels import download_video as download_pexels_video
from footage.providers.pexels import search_videos as search_pexels_videos
from footage.providers.pixabay import download_video as download_pixabay_video
from footage.providers.pixabay import search_videos as search_pixabay_videos
from footage.types import VideoResult
from saas_settings import settings


BLOCKED_TERMS = {"fantasy", "dragon", "unicorn", "cartoon", "anime", "cgi", "ai generated", "render"}


@dataclass
class MatchedClip:
    shot_index: int
    phrase_index: int
    clip_path: str
    provider: str
    duration_target: float
    queries_used: list[str]


def _is_realistic(result: VideoResult) -> bool:
    hay = " ".join([result.page_url or "", " ".join(result.tags or [])]).lower()
    return not any(token in hay for token in BLOCKED_TERMS)


def _search_all(query: str, orientation: str, min_duration: int, max_duration: int, limit: int) -> list[VideoResult]:
    out = []
    out.extend(search_pexels_videos(query, orientation, min_duration, max_duration, limit))
    out.extend(search_pixabay_videos(query, orientation, min_duration, max_duration, limit))
    return out


def _fallback_queries(queries: list[str]) -> list[str]:
    base = [q for q in queries if q]
    out = []
    for q in base:
        out.append(q)
        parts = q.split()
        if len(parts) > 1:
            out.append(" ".join(parts[:2]))
            out.append(parts[0])
    out.extend(["real people work", "city business", "nature real life"])
    uniq = []
    for q in out:
        qq = q.strip()
        if qq and qq not in uniq:
            uniq.append(qq)
    return uniq


def _download(result: VideoResult) -> str:
    ext = ".mp4"
    target = Path(settings.FOOTAGE_CACHE_DIR) / f"{result.provider}_{result.video_id}{ext}"
    if result.provider == "pexels":
        return download_pexels_video(result, target)
    return download_pixabay_video(result, target)


def match_shots(
    shotlist: list[dict],
    phrase_durations: list[float],
    orientation: str,
) -> list[MatchedClip]:
    used_ids: set[str] = set()
    matches: list[MatchedClip] = []
    for shot_index, shot in enumerate(shotlist):
        phrase_index = int(shot.get("phrase_index") or shot_index)
        duration_target = float(phrase_durations[min(max(phrase_index, 0), len(phrase_durations) - 1)])
        duration_target = max(2.0, min(20.0, duration_target))
        queries = shot.get("queries")
        if isinstance(queries, str):
            queries = [queries]
        if not isinstance(queries, list):
            queries = []
        query_chain = _fallback_queries([str(x).strip() for x in queries if str(x).strip()])

        picked: VideoResult | None = None
        used_query = ""
        for query in query_chain:
            candidates = _search_all(
                query=query,
                orientation=orientation,
                min_duration=max(2, int(duration_target) - 1),
                max_duration=max(8, int(duration_target) + 20),
                limit=8,
            )
            clean = [x for x in candidates if _is_realistic(x) and f"{x.provider}:{x.video_id}" not in used_ids]
            if clean:
                picked = clean[0]
                used_query = query
                break
        if not picked:
            raise RuntimeError(f"footage_not_found_for_shot_{shot_index}")
        clip_path = _download(picked)
        used_ids.add(f"{picked.provider}:{picked.video_id}")
        matches.append(
            MatchedClip(
                shot_index=shot_index,
                phrase_index=phrase_index,
                clip_path=clip_path,
                provider=picked.provider,
                duration_target=duration_target,
                queries_used=[used_query],
            )
        )
    return matches
