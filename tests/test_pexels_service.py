import importlib
import os
import sys
from pathlib import Path

import pytest


def _load_service():
    for name in [
        "backend.services.media.pexels_service",
        "backend.services.media",
        "config",
        "saas_settings",
    ]:
        if name in sys.modules:
            del sys.modules[name]
    return importlib.import_module("backend.services.media.pexels_service")


def test_build_media_query_prefers_topic_terms_for_real_estate():
    service = _load_service()
    meta = service.build_media_query(
        niche="real_estate",
        topic="5 ошибок при продаже квартиры",
        post_text="Покажите квартиру, ключи и современный интерьер.",
        platform="facebook",
    )
    assert meta["niche_slug"] == "real_estate"
    assert meta["orientation"] == "landscape"
    assert meta["primary_query"]
    assert any(token in " ".join(meta["topic_terms"]) for token in ["продаже", "квартиры", "квартиру"])
    assert "modern apartment interior" in " ".join(meta["niche_terms"])


def test_build_media_query_maps_esoterica_and_instagram_orientation():
    service = _load_service()
    meta = service.build_media_query(
        niche="Эзотерика",
        topic="Как распознать знаки Вселенной",
        post_text="Свечи, медитация и спокойный ритуал.",
        platform="instagram",
    )
    assert meta["niche_slug"] == "esoterica"
    assert meta["orientation"] == "portrait"
    assert any("candles" in t or "meditation" in t for t in meta["niche_terms"])
    assert any("meditation" in query or "moon" in query or "candles" in query for query in [meta["primary_query"], *meta["fallback_queries"]])


def test_score_candidate_penalizes_negative_terms_and_wrong_orientation():
    service = _load_service()
    meta = service.build_media_query(
        niche="autoservice",
        topic="Диагностика двигателя перед ремонтом",
        post_text="Механик проверяет двигатель в сервисной зоне.",
        platform="facebook",
    )
    good = {
        "id": 1,
        "alt": "Mechanic inspecting engine in auto service workshop",
        "width": 1800,
        "height": 1200,
        "src": {"large2x": "https://images.pexels.com/photos/1/good.jpg"},
        "photographer": "A",
    }
    bad = {
        "id": 2,
        "alt": "Forest train and animal near road",
        "width": 900,
        "height": 1400,
        "src": {"large2x": "https://images.pexels.com/photos/2/bad.jpg"},
        "photographer": "B",
    }
    assert service._score_candidate(good, meta, meta["orientation"]) > service._score_candidate(bad, meta, meta["orientation"])


def test_fetch_post_image_dedupes_project_and_batch_refs(monkeypatch, tmp_path):
    service = _load_service()
    monkeypatch.setattr(service, "MEDIA_DIR", tmp_path)
    monkeypatch.setattr(service, "_load_recent_project_refs", lambda db, project_id: ({"101"}, {"https://images.pexels.com/photos/101/a.jpg"}))

    def fake_search(query, orientation, per_page=10):
        return [
            {"id": "101", "alt": "duplicate image", "width": 1600, "height": 900, "src": {"large2x": "https://images.pexels.com/photos/101/a.jpg"}, "photographer": "A"},
            {"id": "202", "alt": "fresh business planning desk", "width": 1600, "height": 900, "src": {"large2x": "https://images.pexels.com/photos/202/b.jpg"}, "photographer": "B"},
        ]

    monkeypatch.setattr(service, "_search_photos", fake_search)
    monkeypatch.setattr(service, "_persist_photo", lambda photo: (str(tmp_path / f"pexels_{photo['id']}.jpg"), f"https://api.autosocial.tech/api/media/pexels_{photo['id']}.jpg"))

    image = service.fetch_post_image(
        niche="finance",
        topic="Финансовое планирование для предпринимателя",
        platform="facebook",
        used_external_ids={"999"},
        used_urls={"https://images.pexels.com/photos/999/x.jpg"},
    )
    assert image.external_id == "202"
    assert image.local_url.endswith("pexels_202.jpg")


def test_fetch_post_image_raises_empty_when_all_queries_empty(monkeypatch):
    service = _load_service()
    monkeypatch.setattr(service, "_search_photos", lambda query, orientation, per_page=10: [])
    with pytest.raises(service.PexelsEmptyResultError):
        service.fetch_post_image(
            niche="psychology",
            topic="Как снизить тревожность",
            platform="instagram",
        )


def test_select_candidate_prefers_different_photo_family_when_scores_are_close():
    service = _load_service()
    query_meta = service.build_media_query(
        niche="esoterica",
        topic="Moon ritual energy cleanse guidance focus",
        post_text="Candles ritual guidance for intuition and calm reflection.",
        platform="instagram",
    )
    candidates = [
        (
            32.0,
            {
                "id": "101",
                "alt": "moon ritual candles crystals woman hands",
                "url": "https://www.pexels.com/photo/moon-ritual-candles-crystals-101/",
                "width": 1200,
                "height": 1600,
                "src": {"large2x": "https://images.pexels.com/photos/101/moon-ritual-candles-crystals.jpg"},
                "photographer": "Same Creator",
            },
        ),
        (
            31.5,
            {
                "id": "102",
                "alt": "moon ritual candles crystals close up hands",
                "url": "https://www.pexels.com/photo/moon-ritual-candles-crystals-close-up-102/",
                "width": 1200,
                "height": 1600,
                "src": {"large2x": "https://images.pexels.com/photos/102/moon-ritual-candles-crystals-close-up.jpg"},
                "photographer": "Same Creator",
            },
        ),
        (
            30.5,
            {
                "id": "201",
                "alt": "spiritual journal incense moon table",
                "url": "https://www.pexels.com/photo/spiritual-journal-incense-moon-table-201/",
                "width": 1200,
                "height": 1600,
                "src": {"large2x": "https://images.pexels.com/photos/201/spiritual-journal-incense-moon-table.jpg"},
                "photographer": "Different Creator",
            },
        ),
    ]

    score, photo = service._select_candidate(candidates, query_meta=query_meta, query=query_meta["primary_query"])
    assert score == 30.5
    assert photo["id"] == "201"
