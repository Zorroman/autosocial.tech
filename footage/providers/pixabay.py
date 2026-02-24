import os
from pathlib import Path

import requests

from footage.types import VideoResult

from saas_settings import settings

from ._common import download_to_path, index_lookup, remember_index, stable_cache_file


API_URL = "https://pixabay.com/api/videos/"


def _api_key() -> str:
    return (os.getenv("PIXABAY_API_KEY") or "").strip()


def search_videos(
    query: str,
    orientation: str,
    min_duration: int,
    max_duration: int,
    limit: int,
) -> list[VideoResult]:
    key = _api_key()
    if not key:
        return []
    cleaned_query = str(query or "").strip()
    try:
        res = requests.get(
            API_URL,
            params={
                "key": key,
                "q": cleaned_query,
                "video_type": "all",
                "per_page": min(200, max(30, limit * 5)),
                "safesearch": "true",
                "order": "popular",
            },
            timeout=40,
        )
        if res.status_code != 200:
            return []
        payload = res.json() if res.content else {}
        hits = payload.get("hits") or []
        out: list[VideoResult] = []
        for item in hits:
            duration = int(item.get("duration") or 0)
            if duration < min_duration or duration > max_duration:
                continue
            videos = item.get("videos") or {}
            file_item = videos.get("large") or videos.get("medium") or videos.get("small") or videos.get("tiny") or {}
            download_url = str(file_item.get("url") or "").strip()
            width = int(file_item.get("width") or 0)
            height = int(file_item.get("height") or 0)
            if not download_url:
                continue
            inferred = "vertical" if height > width else "horizontal"
            if orientation == "vertical" and inferred != "vertical":
                continue
            if orientation == "horizontal" and inferred != "horizontal":
                continue
            tags = [x.strip() for x in str(item.get("tags") or "").split(",") if x.strip()]
            out.append(
                VideoResult(
                    provider="pixabay",
                    video_id=str(item.get("id") or ""),
                    duration=duration,
                    width=width,
                    height=height,
                    page_url=str(item.get("pageURL") or ""),
                    download_url=download_url,
                    tags=tags,
                    orientation=inferred,
                    title=str(item.get("pageURL") or cleaned_query),
                    description="",
                    author=str(item.get("user") or item.get("user_id") or "").strip(),
                    fps=None,
                    source_query=cleaned_query,
                )
            )
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []


def download_video(video_result: VideoResult, target_path: Path) -> str:
    cached = index_lookup(video_result.provider, video_result.video_id, video_result.download_url)
    if cached:
        return str((settings.BASE_DIR / str(cached["local_path"])).resolve())
    target = stable_cache_file(video_result.provider, video_result.video_id, video_result.download_url, ext=target_path.suffix or ".mp4")
    saved = download_to_path(video_result.download_url, target)
    remember_index(video_result, saved)
    return str(saved)
