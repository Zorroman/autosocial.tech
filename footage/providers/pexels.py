import os
from pathlib import Path

import requests

from footage.types import VideoResult

from saas_settings import settings

from ._common import download_to_path, index_lookup, remember_index, stable_cache_file


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
    cleaned_query = str(query or "").strip()
    try:
        res = requests.get(
            API_URL,
            headers={"Authorization": key},
            params={
                "query": cleaned_query,
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
            if orientation == "vertical" and height <= width:
                continue
            if orientation == "horizontal" and width <= height:
                continue
            tags = []
            for tag in (item.get("tags") or []):
                if isinstance(tag, dict):
                    val = str(tag.get("title") or "").strip()
                    if val:
                        tags.append(val)
            author = ""
            user = item.get("user") or {}
            if isinstance(user, dict):
                author = str(user.get("name") or user.get("id") or "").strip()
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
                    title=str(item.get("url") or cleaned_query),
                    description="",
                    author=author,
                    fps=float(best.get("fps")) if str(best.get("fps") or "").replace(".", "", 1).isdigit() else None,
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
