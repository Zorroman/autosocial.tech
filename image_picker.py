from __future__ import annotations

from backend.services.media import (
    PexelsConfigError,
    PexelsEmptyResultError,
    PexelsRateLimitError,
    PexelsRequestError,
    fetch_pixabay_post_image,
    fetch_post_image,
)


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
    _ = (goal, language, offer_text, orientation, api_key)
    topic = str(manual_topic or niche_title or niche_slug or "").strip()
    if not topic:
        return None

    try:
        image = fetch_post_image(
            niche=niche_slug or niche_title,
            topic=topic,
            platform="instagram",
            post_text=None,
        )
        if image and image.local_url:
            return image.local_url
    except (PexelsConfigError, PexelsRateLimitError, PexelsRequestError, PexelsEmptyResultError):
        pass

    pixabay_image = fetch_pixabay_post_image(
        niche=niche_slug or niche_title,
        topic=topic,
        platform="instagram",
        post_text=None,
    )
    return pixabay_image.local_url if pixabay_image else None


def get_image_by_niche(niche: str, **kwargs) -> str:
    picked = pick_image_url(
        niche_slug=str(kwargs.get("niche_slug") or niche or ""),
        niche_title=str(kwargs.get("niche_title") or niche or ""),
        goal=str(kwargs.get("goal") or "awareness"),
        language=str(kwargs.get("language") or "ru"),
        offer_text=str(kwargs.get("offer_text") or ""),
        manual_topic=str(kwargs.get("manual_topic") or niche or ""),
        orientation=str(kwargs.get("orientation") or "any"),
        api_key=kwargs.get("api_key"),
    )
    return picked or ""
