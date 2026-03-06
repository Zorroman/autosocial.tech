from __future__ import annotations

import os
from typing import Any

import requests

from media_query_builder import buildMediaQuery, filter_media_results


def _pexels_orientation(orientation: str) -> str | None:
    key = str(orientation or "").strip().lower()
    if key == "vertical":
        return "portrait"
    if key == "horizontal":
        return "landscape"
    return None


def _to_item(photo: dict[str, Any]) -> dict[str, Any]:
    src = photo.get("src") if isinstance(photo.get("src"), dict) else {}
    return {
        "id": str(photo.get("id") or ""),
        "title": str(photo.get("alt") or ""),
        "alt": str(photo.get("alt") or ""),
        "description": "",
        "tags": [str(photo.get("alt") or "")],
        "url": str(src.get("large2x") or src.get("large") or src.get("original") or ""),
    }


def _search_pexels(query: str, api_key: str, orientation: str, per_page: int = 20) -> list[dict[str, Any]]:
    if not query.strip() or not api_key.strip():
        return []
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": api_key.strip()}
    params: dict[str, Any] = {"query": query.strip(), "per_page": int(per_page), "page": 1}
    mapped = _pexels_orientation(orientation)
    if mapped:
        params["orientation"] = mapped
    try:
        res = requests.get(url, headers=headers, params=params, timeout=20)
        if res.status_code != 200:
            return []
        payload = res.json() if res.content else {}
        photos = payload.get("photos") if isinstance(payload, dict) else []
        if not isinstance(photos, list):
            return []
        return [_to_item(p) for p in photos if isinstance(p, dict)]
    except Exception:
        return []


def pick_image_url(
    *,
    niche_slug: str = "",
    niche_title: str = "",
    goal: str = "awareness",
    language: str = "ru",
    offer_text: str = "",
    manual_topic: str = "",
    orientation: str = "any",
    api_key: str | None = None,
) -> str | None:
    key = (api_key or os.getenv("PEXELS_API_KEY") or "").strip()
    if not key:
        return None

    built = buildMediaQuery(
        {
            "nicheSlug": niche_slug,
            "nicheTitle": niche_title,
            "goal": goal,
            "language": language,
            "offerText": offer_text,
            "manualTopic": manual_topic,
            "orientation": orientation,
        }
    )
    query = str(built.get("query") or "").strip()
    fallback = [str(x).strip() for x in (built.get("fallbackQueries") or []) if str(x).strip()]
    negative = [str(x).strip().lower() for x in (built.get("negativeKeywords") or []) if str(x).strip()]
    positive = [str(x).strip().lower() for x in (built.get("positiveKeywords") or []) if str(x).strip()]
    orient = str(built.get("orientation") or "any")

    def _search_and_pick(q: str) -> str | None:
        items = _search_pexels(q, key, orient, per_page=25)
        if not items:
            return None
        accepted = filter_media_results(items, positive_keywords=positive, negative_keywords=negative, min_positive=2)
        if not accepted:
            return None
        first = accepted[0]
        return str(first.get("url") or "").strip() or None

    for q in [query] + fallback:
        picked = _search_and_pick(q)
        if picked:
            return picked
    return None


def get_image_by_niche(niche: str, **kwargs) -> str:
    picked = pick_image_url(
        niche_slug=str(kwargs.get("niche_slug") or ""),
        niche_title=str(kwargs.get("niche_title") or ""),
        goal=str(kwargs.get("goal") or "awareness"),
        language=str(kwargs.get("language") or "ru"),
        offer_text=str(kwargs.get("offer_text") or ""),
        manual_topic=str(kwargs.get("manual_topic") or niche or ""),
        orientation=str(kwargs.get("orientation") or "any"),
        api_key=kwargs.get("api_key"),
    )
    if picked:
        return picked
    return "https://via.placeholder.com/1024x1024.png?text=No+Image+Found"
