from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from app_settings import settings

from .pexels_service import (
    MEDIA_DIR,
    PexelsMediaResult,
    _candidate_orientation,
    _score_candidate,
    _select_candidate,
    build_media_query,
)

PIXABAY_PHOTO_API_URL = "https://pixabay.com/api/"


def _api_key() -> str:
    return str(os.getenv("PIXABAY_API_KEY") or "").strip()


def _search_photos(query: str, orientation: str, per_page: int = 10) -> list[dict[str, Any]]:
    key = _api_key()
    if not key:
        return []
    params: dict[str, Any] = {
        "key": key,
        "q": query,
        "image_type": "photo",
        "safesearch": "true",
        "per_page": max(5, min(20, int(per_page or 10))),
        "page": 1,
    }
    if orientation in {"portrait", "landscape"}:
        params["orientation"] = "vertical" if orientation == "portrait" else "horizontal"
    try:
        response = requests.get(PIXABAY_PHOTO_API_URL, params=params, timeout=20)
        if response.status_code != 200:
            return []
        payload = response.json() if response.content else {}
    except (ValueError, requests.RequestException):
        return []
    hits = payload.get("hits") if isinstance(payload, dict) else []
    return [item for item in hits if isinstance(item, dict)]


def _photo_download_url(photo: dict[str, Any]) -> str:
    return str(
        photo.get("largeImageURL")
        or photo.get("fullHDURL")
        or photo.get("webformatURL")
        or photo.get("previewURL")
        or ""
    ).strip()


def _photo_preview_url(photo: dict[str, Any]) -> str:
    return str(photo.get("webformatURL") or photo.get("previewURL") or _photo_download_url(photo)).strip()


def _persist_photo(photo: dict[str, Any]) -> tuple[str, str]:
    photo_id = str(photo.get("id") or "").strip()
    download_url = _photo_download_url(photo)
    if not photo_id or not download_url:
        raise ValueError("Pixabay response missing image id or url")
    target = Path(MEDIA_DIR) / f"pixabay_{photo_id}.jpg"
    if not target.exists():
        response = requests.get(download_url, timeout=30)
        response.raise_for_status()
        target.write_bytes(response.content)
    return str(target), f"{settings.API_BASE_URL}/api/media/{target.name}"


def _normalize_pixabay_photo(photo: dict[str, Any]) -> dict[str, Any]:
    width = int(photo.get("imageWidth") or photo.get("webformatWidth") or 0)
    height = int(photo.get("imageHeight") or photo.get("webformatHeight") or 0)
    return {
        "id": photo.get("id"),
        "width": width,
        "height": height,
        "alt": str(photo.get("tags") or ""),
        "url": str(photo.get("pageURL") or ""),
        "photographer": str(photo.get("user") or ""),
        "src": {
            "large2x": _photo_download_url(photo),
            "large": _photo_download_url(photo),
            "medium": _photo_preview_url(photo),
        },
    }


def fetch_pixabay_post_image(
    *,
    niche: str | None,
    topic: str,
    platform: str,
    post_text: str | None = None,
    db=None,
    project_id: int | None = None,
    used_external_ids: set[str] | None = None,
    used_urls: set[str] | None = None,
) -> PexelsMediaResult | None:
    _ = (db, project_id)
    if not _api_key():
        return None

    query_meta = build_media_query(niche=niche, topic=topic, post_text=post_text, platform=platform)
    orientation = query_meta["orientation"]
    blocked_ids = set(used_external_ids or set())
    blocked_urls = set(used_urls or set())

    for query in [query_meta["primary_query"], *query_meta["fallback_queries"]]:
        candidates: list[tuple[float, dict[str, Any]]] = []
        originals: dict[str, dict[str, Any]] = {}
        for raw_photo in _search_photos(query, orientation, per_page=10):
            ext_id = str(raw_photo.get("id") or "").strip()
            full_url = _photo_download_url(raw_photo)
            if not ext_id or not full_url:
                continue
            if ext_id in blocked_ids or full_url in blocked_urls:
                continue
            normalized = _normalize_pixabay_photo(raw_photo)
            score = _score_candidate(normalized, query_meta, orientation)
            if score <= 0:
                continue
            candidates.append((score, normalized))
            originals[ext_id] = raw_photo
        if not candidates:
            continue
        best_score, best_photo = _select_candidate(candidates, query_meta=query_meta, query=query)
        original = originals.get(str(best_photo.get("id") or ""))
        if not original:
            continue
        try:
            local_path, local_url = _persist_photo(original)
        except (ValueError, requests.RequestException):
            continue
        width = int(original.get("imageWidth") or original.get("webformatWidth") or 0)
        height = int(original.get("imageHeight") or original.get("webformatHeight") or 0)
        return PexelsMediaResult(
            provider="pixabay",
            type="photo",
            external_id=str(original.get("id") or ""),
            preview_url=_photo_preview_url(original),
            full_url=_photo_download_url(original),
            width=width,
            height=height,
            photographer=str(original.get("user") or "").strip(),
            orientation=_candidate_orientation(width, height),
            query_used=query,
            score=best_score,
            local_url=local_url,
            local_path=local_path,
        )
    return None
