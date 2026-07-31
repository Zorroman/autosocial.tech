"""Multichannel architecture tests: niches, pillars, rotation, safety,
visual intent/validation, channel isolation, snapshots."""
import json
import sys
from pathlib import Path

import pytest

from tests.test_private_admin import _fresh_app, _seed_admin, _token_for


def _fresh(tmp_path):
    for m in ("publications_api", "video_projects_api", "analytics_api", "ai_pricing",
              "factory_dashboard_api", "footage_library", "subtitle_builder",
              "content_api", "visual_validation"):
        sys.modules.pop(m, None)
    return _fresh_app(tmp_path)


@pytest.fixture()
def client(tmp_path):
    app_module = _fresh(tmp_path)
    admin_id = _seed_admin()
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)
        yield c


def _h(c):
    return {"Authorization": f"Bearer {c.admin_token}"}


def _seed_eso(client):
    from content_api import seed_esotericism
    from database import SessionLocal
    db = SessionLocal()
    niche = seed_esotericism(db)
    nid = niche.id
    db.close()
    return nid


# ------------------------------------------------------- niches & pillars

def test_create_niche_without_code_change(client):
    r = client.post("/api/niches", json={"name": "Психология", "description": "поведение и привычки"}, headers=_h(client))
    assert r.status_code == 201
    nid = r.get_json()["niche"]["id"]
    for name in ("Отношения", "Тревожность", "Привычки", "Язык тела"):
        pr = client.post(f"/api/niches/{nid}/pillars", json={"name": name}, headers=_h(client))
        assert pr.status_code == 201
    d = client.get(f"/api/niches/{nid}", headers=_h(client)).get_json()["niche"]
    assert len(d["pillars"]) == 4
    # duplicate slug within niche -> 409
    assert client.post(f"/api/niches/{nid}/pillars", json={"name": "Привычки"}, headers=_h(client)).status_code == 409
    # niche slug conflict
    assert client.post("/api/niches", json={"name": "Психология"}, headers=_h(client)).status_code == 409
    # anonymous 401
    assert client.get("/api/niches").status_code == 401


def test_esotericism_seed_complete(client):
    nid = _seed_eso(client)
    d = client.get(f"/api/niches/{nid}", headers=_h(client)).get_json()["niche"]
    assert d["slug"] == "esotericism"
    assert d["disclaimer_policy"] == "ENTERTAINMENT_AND_CULTURAL_INTERPRETATION"
    assert d["factuality_policy"] == "ENTERTAINMENT_AND_CULTURAL_INTERPRETATION"
    assert len(d["pillars"]) == 10
    slugs = {p["slug"] for p in d["pillars"]}
    assert {"universe-signs", "human-energy", "dream-meanings", "spiritual-growth",
            "karma", "numerology", "astrology", "relationship-energy",
            "subconscious-intuition", "mystic-stories"} == slugs
    # seed is idempotent
    nid2 = _seed_eso(client)
    assert nid2 == nid
    d2 = client.get(f"/api/niches/{nid}", headers=_h(client)).get_json()["niche"]
    assert len(d2["pillars"]) == 10


def test_pillar_soft_delete_with_projects(client):
    nid = _seed_eso(client)
    pillars = client.get(f"/api/niches/{nid}/pillars", headers=_h(client)).get_json()["pillars"]
    pid = pillars[0]["id"]
    ch = client.post("/api/channels", json={"name": "Эзо"}, headers=_h(client)).get_json()["channel"]["id"]
    client.patch(f"/api/channels/{ch}", json={"niche_id": nid}, headers=_h(client))
    proj = client.post("/api/video-projects", json={"channel_id": ch, "title": "P", "content_pillar_id": pid}, headers=_h(client))
    assert proj.status_code == 201
    r = client.delete(f"/api/pillars/{pid}", headers=_h(client))
    assert r.status_code == 200
    assert r.get_json().get("soft_deleted") is True
    # pillar without projects -> hard delete
    empty = next(p for p in pillars if p["id"] != pid)
    r2 = client.delete(f"/api/pillars/{empty['id']}", headers=_h(client))
    assert r2.get_json().get("deleted") is True


# --------------------------------------------------------------- channels

def test_multiple_channels_separate_niches_and_snapshot(client):
    nid1 = _seed_eso(client)
    nid2 = client.post("/api/niches", json={"name": "История"}, headers=_h(client)).get_json()["niche"]["id"]
    client.post(f"/api/niches/{nid2}/pillars", json={"name": "Древние цивилизации"}, headers=_h(client))
    ch1 = client.post("/api/channels", json={"name": "Эзо-канал"}, headers=_h(client)).get_json()["channel"]["id"]
    ch2 = client.post("/api/channels", json={"name": "Исторический"}, headers=_h(client)).get_json()["channel"]["id"]
    client.patch(f"/api/channels/{ch1}", json={"niche_id": nid1, "language": "ru"}, headers=_h(client))
    client.patch(f"/api/channels/{ch2}", json={"niche_id": nid2, "language": "de"}, headers=_h(client))
    c1 = client.get(f"/api/channels/{ch1}", headers=_h(client)).get_json()["channel"]
    c2 = client.get(f"/api/channels/{ch2}", headers=_h(client)).get_json()["channel"]
    assert c1["niche_id"] == nid1 and c2["niche_id"] == nid2
    assert c1["language"] != c2["language"]

    # snapshot persisted; later channel changes do not rewrite it
    pillars = client.get(f"/api/niches/{nid1}/pillars", headers=_h(client)).get_json()["pillars"]
    proj = client.post("/api/video-projects", json={"channel_id": ch1, "title": "Сны",
                       "content_pillar_id": next(p["id"] for p in pillars if p["slug"] == "dream-meanings"),
                       "topic": "Почему снится вода"}, headers=_h(client)).get_json()["project"]
    snap = proj["generation_profile"]
    assert snap["niche_name"] == "Эзотерика"
    assert snap["content_pillar_name"] == "Сны и их значения"
    assert snap["topic"] == "Почему снится вода"
    client.patch(f"/api/channels/{ch1}", json={"language": "en", "name": "Renamed"}, headers=_h(client))
    proj2 = client.get(f"/api/video-projects/{proj['id']}", headers=_h(client)).get_json()["project"]
    assert proj2["generation_profile"]["language"] == "ru"
    assert proj2["generation_profile"]["channel_name"] == "Эзо-канал"


def test_pillar_from_other_niche_rejected(client):
    nid1 = _seed_eso(client)
    nid2 = client.post("/api/niches", json={"name": "Космос"}, headers=_h(client)).get_json()["niche"]["id"]
    other_pillar = client.post(f"/api/niches/{nid2}/pillars", json={"name": "Планеты"}, headers=_h(client)).get_json()["pillar"]["id"]
    ch = client.post("/api/channels", json={"name": "Эзо"}, headers=_h(client)).get_json()["channel"]["id"]
    client.patch(f"/api/channels/{ch}", json={"niche_id": nid1}, headers=_h(client))
    r = client.post("/api/video-projects", json={"channel_id": ch, "title": "X", "content_pillar_id": other_pillar}, headers=_h(client))
    assert r.status_code == 400


def test_wrong_channel_publishing_forbidden(client, monkeypatch):
    """Publication whose project belongs to another channel must be blocked."""
    ch1 = client.post("/api/channels", json={"name": "A"}, headers=_h(client)).get_json()["channel"]["id"]
    ch2 = client.post("/api/channels", json={"name": "B"}, headers=_h(client)).get_json()["channel"]["id"]
    pid = client.post("/api/video-projects", json={"channel_id": ch1, "title": "V", "script_text": "Раз. Два.", "voice_mode": "silent"}, headers=_h(client)).get_json()["project"]["id"]
    for s in client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client)).get_json()["scenes"]:
        client.post(f"/api/scenes/{s['id']}/fixture-media", headers=_h(client))
    client.post(f"/api/video-projects/{pid}/render", headers=_h(client))
    pub = client.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(client)).get_json()["publication"]
    # link YouTube to BOTH, but corrupt the publication to point at ch2
    from database import SessionLocal
    from saas_models import Channel, Publication
    db = SessionLocal()
    for cid in (ch1, ch2):
        c = db.query(Channel).filter_by(id=cid).first()
        c.youtube_channel_id = f"UCch{cid}"
        c.youtube_connection_status = "connected"
        c.automatic_publishing_enabled = True
    p = db.query(Publication).filter_by(id=pub["id"]).first()
    p.channel_id = ch2  # cross-channel mismatch
    db.commit(); db.close()
    r = client.post(f"/api/publications/{pub['id']}/upload", headers=_h(client))
    assert r.status_code == 409
    assert "different channel" in r.get_json()["error"]


def test_automatic_publishing_disabled_blocks_upload(client):
    ch = client.post("/api/channels", json={"name": "NoPub"}, headers=_h(client)).get_json()["channel"]["id"]
    pid = client.post("/api/video-projects", json={"channel_id": ch, "title": "V", "script_text": "Раз. Два.", "voice_mode": "silent"}, headers=_h(client)).get_json()["project"]["id"]
    for s in client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client)).get_json()["scenes"]:
        client.post(f"/api/scenes/{s['id']}/fixture-media", headers=_h(client))
    client.post(f"/api/video-projects/{pid}/render", headers=_h(client))
    pub = client.post(f"/api/video-projects/{pid}/prepare-publication", headers=_h(client)).get_json()["publication"]
    from database import SessionLocal
    from saas_models import Channel
    db = SessionLocal()
    c = db.query(Channel).filter_by(id=ch).first()
    c.youtube_channel_id = "UCx"
    c.youtube_connection_status = "connected"
    c.automatic_publishing_enabled = False
    db.commit(); db.close()
    r = client.post(f"/api/publications/{pub['id']}/upload", headers=_h(client))
    assert r.status_code == 409
    assert "disabled" in r.get_json()["error"].lower()


def test_generation_readiness_rules(client):
    ch = client.post("/api/channels", json={"name": "R"}, headers=_h(client)).get_json()["channel"]["id"]
    r = client.get(f"/api/channels/{ch}/generation-readiness", headers=_h(client)).get_json()
    assert r["generation_ready"] is False
    assert "niche_not_selected" in r["generation_problems"]
    assert "daily_video_limit_not_set" in r["generation_problems"]
    # enable-generation must refuse while unready
    assert client.post(f"/api/channels/{ch}/enable-generation", headers=_h(client)).status_code == 409
    nid = _seed_eso(client)
    client.patch(f"/api/channels/{ch}", json={"niche_id": nid, "daily_video_limit": 5, "language": "ru"}, headers=_h(client))
    r2 = client.post(f"/api/channels/{ch}/enable-generation", headers=_h(client))
    assert r2.status_code == 200 and r2.get_json()["automatic_generation_enabled"] is True
    rr = client.get(f"/api/channels/{ch}/generation-readiness", headers=_h(client)).get_json()
    assert rr["generation_ready"] is True
    # publishing toggle refuses without YouTube
    assert client.post(f"/api/channels/{ch}/enable-publishing", headers=_h(client)).status_code == 409


# ------------------------------------------------------ rotation & topics

def test_weighted_rotation_and_daily_limits(client):
    import content_api as ca
    from database import SessionLocal
    from saas_models import Channel, ContentPillar, VideoProject
    nid = _seed_eso(client)
    ch = client.post("/api/channels", json={"name": "Rot"}, headers=_h(client)).get_json()["channel"]["id"]
    client.patch(f"/api/channels/{ch}", json={"niche_id": nid}, headers=_h(client))
    db = SessionLocal()
    channel = db.query(Channel).filter_by(id=ch).first()
    picks = {ca.pick_pillar(db, channel).slug for _ in range(60)}
    assert len(picks) >= 3  # rotation uses many pillars, not only the top weight
    # inactive pillar never picked
    db.query(ContentPillar).filter_by(niche_id=nid).update({"active": False})
    top = db.query(ContentPillar).filter_by(niche_id=nid, slug="universe-signs").first()
    top.active = True
    db.commit()
    assert all(ca.pick_pillar(db, channel).id == top.id for _ in range(10))
    # daily limit exhausts the pillar
    top.daily_video_limit = 1
    db.add(VideoProject(channel_id=ch, title="t", content_pillar_id=top.id))
    db.commit()
    assert ca.pick_pillar(db, channel) is None
    db.close()


def test_safety_and_disclaimers(client):
    from content_api import check_content_safety, check_disclaimers
    assert "medical_claim" in check_content_safety("Этот ритуал вылечит болезни без врача")
    assert "guaranteed_money" in check_content_safety("Гарантированный доход уже завтра")
    assert "partner_return_promise" in check_content_safety("Обряд вернёт партнёра за 3 дня")
    assert "curse_fear" in check_content_safety("На вас проклятие, срочно снять порчу срочно")
    assert check_content_safety("Спокойный рассказ о значении снов") == []
    # disclaimers
    assert "numerology" in check_disclaimers("Число 7 приносит удачу в нумерологии всегда")
    assert check_disclaimers("В нумерологии считается, что число 7 связано с интуицией") == []
    assert "astrology" in check_disclaimers("Овнам сегодня повезёт")
    assert check_disclaimers("Астрологи связывают этот период с переменами") == []


def test_topic_requires_pillar_and_niche(client):
    ch = client.post("/api/channels", json={"name": "NoNiche"}, headers=_h(client)).get_json()["channel"]["id"]
    r = client.post(f"/api/channels/{ch}/generate-topic", headers=_h(client), json={})
    assert r.status_code == 409  # no niche selected
    # pillar of another niche
    nid = _seed_eso(client)
    other = client.post("/api/niches", json={"name": "Другое"}, headers=_h(client)).get_json()["niche"]["id"]
    op = client.post(f"/api/niches/{other}/pillars", json={"name": "X"}, headers=_h(client)).get_json()["pillar"]["id"]
    client.patch(f"/api/channels/{ch}", json={"niche_id": nid}, headers=_h(client))
    r2 = client.post(f"/api/channels/{ch}/generate-topic", headers=_h(client), json={"content_pillar_id": op})
    assert r2.status_code == 400


def test_topic_duplicate_score(client):
    from content_api import _topic_duplicate_score
    from database import SessionLocal
    from saas_models import ChannelIdea
    ch = client.post("/api/channels", json={"name": "Dup"}, headers=_h(client)).get_json()["channel"]["id"]
    db = SessionLocal()
    db.add(ChannelIdea(channel_id=ch, title="Почему снится вода каждую ночь", topic="сны про воду"))
    db.commit()
    high = _topic_duplicate_score(db, ch, "Почему каждую ночь снится вода", "вода во сне")
    low = _topic_duplicate_score(db, ch, "Число 11:11 на часах", "нумерология времени")
    assert high > 0.5 and low < 0.3
    db.close()


# --------------------------------------------------- visual intent & AI

def test_visual_intent_uses_niche_and_pillar(client):
    from visual_validation import build_visual_intent
    intent = build_visual_intent(
        scene_text="Если человеку часто снится вода, это связывают с эмоциями",
        niche_slug="esotericism",
        pillar={"slug": "dream-meanings",
                "visual_keywords": "person sleeping in bed at night, calm water waves, foggy lake",
                "forbidden_visual_keywords": "cars traffic, office desk, party crowd"},
        channel_visual_style="атмосферный, мистический",
    )
    assert intent["channel_niche"] == "esotericism"
    assert intent["content_pillar"] == "dream-meanings"
    assert "person sleeping in bed at night" in intent["search_queries"]
    assert "cars traffic" in intent["avoid"]
    assert intent["people_required"] is True
    assert intent["time_of_day"] == "night"
    # concrete queries, not abstract "meaning of dream"
    assert not any("meaning" in q for q in intent["search_queries"])


def test_visual_mock_provider_rules(client, tmp_path):
    from visual_validation import MockVisualValidationProvider
    provider = MockVisualValidationProvider()
    intent = {"primary_subjects": ["sleeping person", "night bed"],
              "search_queries": ["person sleeping night"],
              "avoid": ["office desk"], "people_required": True,
              "abstract_allowed": False}
    ok = provider.evaluate([], intent, {"search_query": "person sleeping night bed", "tags": []})
    assert ok.accepted, ok.rejection_reason
    # forbidden keyword -> reject
    bad = provider.evaluate([], intent, {"search_query": "office desk person computer", "tags": []})
    assert not bad.accepted and bad.rejection_reason.startswith("avoid_matched")
    # person required but absent -> reject
    nop = provider.evaluate([], intent, {"search_query": "night sleeping bed room", "tags": []})
    assert not nop.accepted and nop.rejection_reason == "people_required_absent"
    # unrelated -> low relevance reject
    unrel = provider.evaluate([], intent, {"search_query": "man mountain bike race", "tags": []})
    assert not unrel.accepted


def test_visual_validation_cache_and_frames_cleanup(client, tmp_path, monkeypatch):
    import subprocess as sp
    from database import SessionLocal
    from footage_library import register_asset
    from saas_models import VisualValidationRecord
    monkeypatch.setenv("VISUAL_VALIDATION_ENABLED", "true")
    import saas_settings, importlib
    importlib.reload(saas_settings)
    import visual_validation
    importlib.reload(visual_validation)
    db = SessionLocal()
    p = tmp_path / "clip.mp4"
    sp.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x223344:s=64x114:d=2:r=10",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)], check=True, capture_output=True)
    asset = register_asset(db, provider="test", provider_asset_id="vv1", local_path=p,
                           search_query="person sleeping night")
    db.commit()
    intent = {"primary_subjects": ["sleeping person"], "search_queries": ["person sleeping night"],
              "avoid": [], "people_required": False, "abstract_allowed": False}
    r1 = visual_validation.validate_asset(db, asset, intent)
    assert r1.accepted
    assert db.query(VisualValidationRecord).count() == 1
    r2 = visual_validation.validate_asset(db, asset, intent)
    assert r2.provider.endswith(":cache")  # cache hit, no re-analysis
    assert db.query(VisualValidationRecord).count() == 1
    # temp frames removed (nothing left behind in system temp matching ours)
    import glob, tempfile
    assert not glob.glob(str(Path(tempfile.gettempdir()) / "frame_*.jpg"))
    db.close()


def test_render_with_visual_validation_manifest(client, monkeypatch):
    """E2E with mock visual provider: manifest records visual stats; no network."""
    monkeypatch.setenv("VISUAL_VALIDATION_ENABLED", "true")
    import importlib, saas_settings
    importlib.reload(saas_settings)
    for m in ("visual_validation", "footage_library"):
        if m in sys.modules:
            importlib.reload(sys.modules[m])
    from saas_settings import settings
    nid = _seed_eso(client)
    ch = client.post("/api/channels", json={"name": "ЭзоE2E"}, headers=_h(client)).get_json()["channel"]["id"]
    client.patch(f"/api/channels/{ch}", json={"niche_id": nid}, headers=_h(client))
    pillars = client.get(f"/api/niches/{nid}/pillars", headers=_h(client)).get_json()["pillars"]
    dream = next(p["id"] for p in pillars if p["slug"] == "dream-meanings")
    script = ("Если вам часто снится вода, в эзотерических традициях это связывают с эмоциональным состоянием. "
              "Психологи объясняют такие сны переработкой дневных переживаний. "
              "Доказанный факт лишь один: фаза быстрого сна нужна каждому человеку. "
              "Понаблюдайте за своими снами — и сделайте собственные выводы.")
    pid = client.post("/api/video-projects", json={
        "channel_id": ch, "title": "Почему человеку часто снится вода",
        "content_pillar_id": dream, "topic": "Почему человеку часто снится вода",
        "script_text": script, "voice_mode": "silent"}, headers=_h(client)).get_json()["project"]["id"]
    for s in client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client)).get_json()["scenes"]:
        client.post(f"/api/scenes/{s['id']}/fixture-media", headers=_h(client))
    r = client.post(f"/api/video-projects/{pid}/render", headers=_h(client))
    assert r.status_code == 202
    proj = client.get(f"/api/video-projects/{pid}", headers=_h(client)).get_json()["project"]
    assert proj["status"] == "rendered", proj["error"]
    assert proj["generation_profile"]["content_pillar_name"] == "Сны и их значения"
    job_id = proj["jobs"][0]["id"]
    manifest = json.loads((settings.OUTPUT_MANIFESTS_DIR / f"project_{pid}_job_{job_id}.json").read_text(encoding="utf-8"))
    non_primary = [s for s in manifest["timeline"] if s["segment"] > 0]
    for seg in non_primary:
        assert "visual_checks" in seg and "visual_degraded" in seg
