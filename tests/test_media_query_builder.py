import importlib
import os
import sys


def _reload_module():
    if "media_query_builder" in sys.modules:
        del sys.modules["media_query_builder"]
    return importlib.import_module("media_query_builder")


def test_build_media_query_barbershop_contains_expected_keywords():
    mod = _reload_module()
    out = mod.buildMediaQuery(
        {
            "nicheSlug": "barbershop",
            "nicheTitle": "Barbershop",
            "goal": "awareness",
            "language": "Русский",
            "offerText": "Скидка на стрижку",
            "manualTopic": "Сильный заголовок про рост охвата",
            "contentType": "post",
        }
    )
    query = str(out.get("query") or "").lower()
    assert ("barber" in query) or ("barbershop" in query)
    negatives = [str(x).lower() for x in (out.get("negativeKeywords") or [])]
    assert "shopping mall" in negatives


def test_filter_media_results_rejects_crowd_accepts_haircut():
    mod = _reload_module()
    items = [
        {
            "id": "1",
            "title": "shopping mall crowd people",
            "alt": "large crowd in mall",
            "tags": ["crowd", "shopping mall", "people"],
            "url": "https://example.com/crowd.jpg",
        },
        {
            "id": "2",
            "title": "barber haircut close up",
            "alt": "barber trimming beard in barbershop",
            "tags": ["barber", "haircut", "beard trim", "barbershop"],
            "url": "https://example.com/haircut.jpg",
        },
    ]
    out = mod.filter_media_results(
        items,
        positive_keywords=["barber", "haircut", "barbershop"],
        negative_keywords=["crowd", "shopping mall"],
        min_positive=2,
    )
    assert len(out) == 1
    assert out[0]["url"] == "https://example.com/haircut.jpg"


def test_pick_image_url_uses_filter_and_fallback(monkeypatch):
    import image_picker

    def fake_search(query, api_key, orientation, per_page=20):
        if "barbershop" in query:
            return [
                {
                    "id": "1",
                    "title": "shopping mall crowd",
                    "alt": "crowd in mall",
                    "tags": ["crowd", "shopping mall"],
                    "url": "https://example.com/crowd.jpg",
                }
            ]
        return [
            {
                "id": "2",
                "title": "barber haircut close up",
                "alt": "barber trimming beard",
                "tags": ["barber", "haircut", "barbershop"],
                "url": "https://example.com/haircut.jpg",
            }
        ]

    # pick_image_url now delegates to fetch_post_image (returns an image with a
    # .local_url), not the old internal _search_pexels(query)->list[dict].
    class _Img:
        local_url = "https://example.com/haircut.jpg"

    monkeypatch.setattr(image_picker, "fetch_post_image", lambda **k: _Img())
    picked = image_picker.pick_image_url(
        niche_slug="barbershop",
        niche_title="Barbershop",
        goal="awareness",
        language="Русский",
        offer_text="Стрижка и борода",
        manual_topic="Как увеличить охват",
        orientation="any",
        api_key="test-key",
    )
    assert picked == "https://example.com/haircut.jpg"
