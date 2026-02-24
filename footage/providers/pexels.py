import os
from pathlib import Path

import requests

from footage.types import VideoResult

from ._common import cache_key, cached_file_path, download_to_path, get_cached_path, remember_cache


API_URL = "https://api.pexels.com/videos/search"


def _api_key() -> str:
    return (os.getenv("PEXELS_API_KEY") or "").strip()


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
    orient = "portrait" if orientation == "vertical" else "landscape"
    per_page = min(80, max(5, limit * 4))
    try:
        res = requests.get(
            API_URL,
            headers={"Authorization": key},
            params={
                "query": query,
                "orientation": orient,
                "size": "medium",
                "per_page": per_page,
            },
            timeout=40,
        )
        if res.status_code != 200:
            return []
        payload = res.json() if res.content else {}
        videos = payload.get("videos") or []
        out: list[VideoResult] = []
        for item in videos:
            duration = int(item.get("duration") or 0)
            if duration < min_duration or duration > max_duration:
                continue
            width = int(item.get("width") or 0)
            height = int(item.get("height") or 0)
            files = item.get("video_files") or []
            if not files:
                continue
            best = sorted(files, key=lambda x: int(x.get("width") or 0), reverse=True)[0]
            download_url = str(best.get("link") or "").strip()
            if not download_url:
                continue
            tags = []
            for tag in (item.get("tags") or []):
                if isinstance(tag, dict):
                    val = str(tag.get("title") or "").strip()
                    if val:
                        tags.append(val)
            out.append(
                VideoResult(
                    provider="pexels",
                    video_id=str(item.get("id") or ""),
                    duration=duration,
                    width=width,
                    height=height,
                    page_url=str(item.get("url") or ""),
                    download_url=download_url,
                    tags=tags,
                    orientation="vertical" if height > width else "horizontal",
                )
            )
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []


def download_video(video_result: VideoResult, target_path: Path) -> str:
    key = cache_key(video_result.provider, video_result.video_id, video_result.download_url)
    cached = get_cached_path(key)
    if cached:
        return str(cached)
    target = cached_file_path(key, ext=target_path.suffix or ".mp4")
    saved = download_to_path(video_result.download_url, target)
    remember_cache(key, saved)
    return str(saved)
