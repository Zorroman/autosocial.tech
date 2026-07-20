"""AI Content Director tests: pillar choice, topic ideation, duplicate/cooldown
protection, hook, outline, analytics on/off, explainability, rotation,
multi-channel/multi-niche isolation, reject/regenerate, writer handoff."""
import json
import sys
from datetime import datetime, timedelta

import pytest

from tests.test_private_admin import _fresh_app, _seed_admin, _token_for


def _fresh(tmp_path):
    for m in ("publications_api", "video_projects_api", "analytics_api", "ai_pricing",
              "factory_dashboard_api", "footage_library", "subtitle_builder",
              "content_api", "visual_validation", "content_director",
              "content_director_api"):
        sys.modules.pop(m, None)
    return _fresh_app(tmp_path)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Director runs offline in tests: heuristic ideation, no network.
    monkeypatch.setenv("DIRECTOR_USE_AI", "false")
    app_module = _fresh(tmp_path)
    admin_id = _seed_admin()
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)
        yield c


def _h(c):
    return {"Authorization": f"Bearer {c.admin_token}"}


def _seed_channel(client, name="Эзо", niche_slug="esotericism"):
    from content_api import seed_esotericism
    from database import SessionLocal
    db = SessionLocal()
    niche = seed_esotericism(db)
    nid = niche.id
    db.close()
    ch = client.post("/api/channels", json={"name": name}, headers=_h(client)).get_json()["channel"]["id"]
    client.patch(f"/api/channels/{ch}", json={"niche_id": nid, "language": "ru",
                                              "daily_video_limit": 5}, headers=_h(client))
    return ch, nid


# ------------------------------------------------------------ basic decide

def test_director_generates_full_strategy(client):
    ch, nid = _seed_channel(client)
    r = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client))
    assert r.status_code == 201, r.get_json()
    s = r.get_json()["strategy"]
    # every stage produced output
    assert s["pillar_id"] and s["pillar_name"]
    assert s["selected_topic"]
    assert s["selected_angle"]
    assert s["selected_hook"]
    assert s["outline"] and len(s["outline"]["structure"]) >= 5
    parts = [p["part"] for p in s["outline"]["structure"]]
    assert parts[0] == "hook" and parts[-1] == "cta"
    assert s["status"] == "draft"
    assert 1 <= s["priority"] <= 100
    assert s["source"] == "heuristic"  # offline mode
    # Director must NOT write a script
    assert "script" not in json.dumps(s).lower() or not s.get("script_text")


def test_requires_niche_and_auth(client):
    ch = client.post("/api/channels", json={"name": "NoNiche"}, headers=_h(client)).get_json()["channel"]["id"]
    r = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client))
    assert r.status_code == 409
    assert r.get_json()["error"] == "channel_has_no_niche"
    assert client.get("/api/content-director").status_code == 401
    assert client.post("/api/content-director/generate", json={"channel_id": ch}).status_code == 401


# ------------------------------------------------------- stage 1: pillars

def test_pillar_selection_is_deliberate_and_explained(client):
    from content_director import select_pillar
    from database import SessionLocal
    from saas_models import Channel
    ch, nid = _seed_channel(client)
    db = SessionLocal()
    channel = db.query(Channel).filter_by(id=ch).first()
    pillar, debug = select_pillar(db, channel)
    assert pillar is not None
    assert debug["chosen"]["pillar_id"] == pillar.id
    assert len(debug["candidates"]) >= 5
    # highest scoring candidate wins, and every candidate carries reasons
    assert debug["candidates"][0]["score"] >= debug["candidates"][-1]["score"]
    assert all(c["reasons"] for c in debug["candidates"])
    assert debug["analytics_used"] is False
    db.close()


def test_weighted_rotation_avoids_monotony(client):
    """Consecutive runs must not stack on one pillar."""
    ch, nid = _seed_channel(client)
    pillars = []
    for _ in range(6):
        r = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client))
        assert r.status_code == 201, r.get_json()
        pillars.append(r.get_json()["strategy"]["pillar_id"])
    # never the same pillar twice in a row, and several distinct pillars used
    assert all(pillars[i] != pillars[i + 1] for i in range(len(pillars) - 1)), pillars
    assert len(set(pillars)) >= 3, pillars


def test_pillar_daily_limit_and_inactive_excluded(client):
    from content_director import select_pillar
    from database import SessionLocal
    from saas_models import Channel, ContentPillar, VideoProject
    ch, nid = _seed_channel(client)
    db = SessionLocal()
    channel = db.query(Channel).filter_by(id=ch).first()
    # keep only one active pillar, give it limit 1 and consume it
    db.query(ContentPillar).filter_by(niche_id=nid).update({"active": False})
    only = db.query(ContentPillar).filter_by(niche_id=nid, slug="dream-meanings").first()
    only.active = True
    only.daily_video_limit = 1
    db.commit()
    pillar, _ = select_pillar(db, channel)
    assert pillar.id == only.id
    db.add(VideoProject(channel_id=ch, title="used today", content_pillar_id=only.id))
    db.commit()
    pillar2, debug2 = select_pillar(db, channel)
    assert pillar2 is None
    assert any(e["reason"] == "daily_limit_reached" for e in debug2["excluded"])
    db.close()


def test_forced_pillar_respected_and_cross_niche_rejected(client):
    ch, nid = _seed_channel(client)
    pillars = client.get(f"/api/niches/{nid}/pillars", headers=_h(client)).get_json()["pillars"]
    karma = next(p["id"] for p in pillars if p["slug"] == "karma")
    r = client.post("/api/content-director/generate",
                    json={"channel_id": ch, "pillar_id": karma}, headers=_h(client))
    assert r.status_code == 201
    assert r.get_json()["strategy"]["pillar_id"] == karma
    # pillar from a different niche is refused
    other = client.post("/api/niches", json={"name": "Космос"}, headers=_h(client)).get_json()["niche"]["id"]
    op = client.post(f"/api/niches/{other}/pillars", json={"name": "Планеты"}, headers=_h(client)).get_json()["pillar"]["id"]
    r2 = client.post("/api/content-director/generate",
                     json={"channel_id": ch, "pillar_id": op}, headers=_h(client))
    assert r2.status_code == 409
    assert r2.get_json()["error"] == "pillar_not_in_channel_niche"


# ------------------------------------------- stage 2/3: topics & duplicates

def test_topics_are_varied_and_never_repeat(client):
    ch, nid = _seed_channel(client)
    topics = []
    for _ in range(8):
        r = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client))
        if r.status_code != 201:
            break
        topics.append(r.get_json()["strategy"]["selected_topic"])
    assert len(topics) >= 6
    assert len(set(topics)) == len(topics), topics  # no exact repeats


def test_duplicate_and_cooldown_protection(client):
    from content_director import duplicate_check, normalize_title, similarity
    from database import SessionLocal
    from saas_models import DirectorStrategy
    ch, nid = _seed_channel(client)
    db = SessionLocal()
    db.add(DirectorStrategy(channel_id=ch, language="ru",
                            selected_topic="Почему часто снится вода",
                            normalized_topic=normalize_title("Почему часто снится вода")))
    db.commit()
    # near-identical wording is caught
    dup = duplicate_check(db, ch, "Почему снится вода часто")
    assert dup["duplicate"] is True
    assert dup["score"] >= 0.55
    # unrelated topic passes
    fresh = duplicate_check(db, ch, "Значение числа 11:11 на часах")
    assert fresh["duplicate"] is False
    assert fresh["reason"] == "unique_enough"
    # similarity helper is order-independent
    assert similarity("снится вода почему", "почему снится вода") == 1.0

    # cooldown: an OLD topic outside the window no longer blocks
    old = db.query(DirectorStrategy).first()
    old.created_at = datetime.utcnow() - timedelta(days=400)
    db.commit()
    after_cooldown = duplicate_check(db, ch, "Почему снится вода часто")
    assert after_cooldown["duplicate"] is False
    db.close()


def test_banned_topic_never_returns(client):
    from content_director import duplicate_check
    from database import SessionLocal
    ch, nid = _seed_channel(client)
    s = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client)).get_json()["strategy"]
    banned_topic = s["selected_topic"]
    r = client.post("/api/content-director/reject",
                    json={"strategy_id": s["id"], "ban": True}, headers=_h(client))
    assert r.status_code == 200
    assert r.get_json()["strategy"]["status"] == "banned"
    db = SessionLocal()
    dup = duplicate_check(db, ch, banned_topic)
    assert dup["duplicate"] is True
    assert dup["reason"] == "explicitly_banned"
    db.close()


# ------------------------------------------------- stage 4/5/6: angle/hook

def test_angle_rotation_and_hook_and_outline(client):
    from content_director import ANGLES, build_hook, build_outline, select_angle
    from database import SessionLocal
    ch, nid = _seed_channel(client)
    db = SessionLocal()
    angle, adebug = select_angle(db, ch, "Почему снится вода")
    assert angle["name"] in [a["name"] for a in ANGLES]
    assert adebug["candidates"] and adebug["chosen"] == angle["name"]
    hook, strength = build_hook("Почему часто снится вода", angle, "вода")
    assert isinstance(hook, str) and len(hook) > 20
    assert "вода" in hook.lower()
    assert 0 < strength <= 1
    outline = build_outline("Почему часто снится вода", angle, hook)
    parts = [p["part"] for p in outline["structure"]]
    assert parts == ["hook", "intrigue", "main_idea", "two_versions", "conclusion", "cta"]
    assert outline["structure"][0]["text_hint"] == hook
    db.close()


def test_angles_differ_across_consecutive_strategies(client):
    ch, nid = _seed_channel(client)
    angles = []
    for _ in range(4):
        r = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client))
        if r.status_code != 201:
            break
        angles.append(r.get_json()["strategy"]["selected_angle"])
    assert len(set(angles)) >= 2, angles


# --------------------------------------------------------------- analytics

def test_works_without_analytics(client):
    ch, nid = _seed_channel(client)
    r = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client))
    assert r.status_code == 201
    dec = r.get_json()["strategy"]["decision"]
    assert dec["analytics"]["has_data"] is False
    assert any("no analytics" in x for x in dec["reasons"])
    assert r.get_json()["strategy"]["estimated_ctr"] is not None  # still estimates


def test_uses_analytics_when_present(client):
    from content_director import channel_analytics, select_pillar
    from database import SessionLocal
    from saas_models import Channel, ContentPerformance, ContentPillar
    ch, nid = _seed_channel(client)
    db = SessionLocal()
    pillars = {p.slug: p for p in db.query(ContentPillar).filter_by(niche_id=nid).all()}
    star = pillars["astrology"]      # low weight (5) but great performance
    weak = pillars["universe-signs"]  # top weight (20) but poor performance
    for _ in range(3):
        db.add(ContentPerformance(video_project_id=0, channel_id=ch, pillar_id=star.id,
                                  ctr=0.20, retention=0.7, views=10000))
        db.add(ContentPerformance(video_project_id=0, channel_id=ch, pillar_id=weak.id,
                                  ctr=0.01, retention=0.2, views=100))
    db.commit()
    stats = channel_analytics(db, ch)
    assert stats["has_data"] is True and stats["videos"] == 6
    assert stats["per_pillar"][star.id]["avg_ctr"] == 0.2

    channel = db.query(Channel).filter_by(id=ch).first()
    _, debug = select_pillar(db, channel)
    assert debug["analytics_used"] is True
    by_name = {c["pillar"]: c for c in debug["candidates"]}
    # good performer gets a positive bonus, bad performer a negative one
    assert by_name[star.name]["performance_bonus"] > 0
    assert by_name[weak.name]["performance_bonus"] < 0
    assert any("historical CTR" in r for r in by_name[star.name]["reasons"])
    db.close()


# ---------------------------------------------------------- explainability

def test_every_decision_is_explainable(client):
    ch, nid = _seed_channel(client)
    sid = client.post("/api/content-director/generate", json={"channel_id": ch},
                      headers=_h(client)).get_json()["strategy"]["id"]
    d = client.get(f"/api/content-director/{sid}", headers=_h(client)).get_json()["strategy"]
    assert d["generation_reason"]
    dec = d["decision"]
    for stage in ("pillar", "ideation", "angle", "duplicates", "selection", "outline"):
        assert stage in dec["stages"], stage
    assert dec["stages"]["pillar"]["candidates"]        # why this pillar
    assert dec["stages"]["duplicates"]["threshold"]     # how duplicates judged
    assert dec["stages"]["selection"]["chosen"] == d["selected_topic"]
    assert len(dec["reasons"]) >= 4
    # scores exposed for the UI
    for f in ("novelty_score", "hook_strength", "visual_potential",
              "estimated_ctr", "estimated_retention", "priority"):
        assert d[f] is not None, f


# ------------------------------------------------ reject / regenerate / pin

def test_reject_and_regenerate(client):
    ch, nid = _seed_channel(client)
    s = client.post("/api/content-director/generate", json={"channel_id": ch},
                    headers=_h(client)).get_json()["strategy"]
    r = client.post("/api/content-director/reject",
                    json={"strategy_id": s["id"], "reason": "не нравится"}, headers=_h(client))
    assert r.status_code == 200 and r.get_json()["strategy"]["status"] == "rejected"
    assert "не нравится" in r.get_json()["strategy"]["generation_reason"]

    s2 = client.post("/api/content-director/generate", json={"channel_id": ch},
                     headers=_h(client)).get_json()["strategy"]
    rg = client.post("/api/content-director/regenerate",
                     json={"strategy_id": s2["id"]}, headers=_h(client))
    assert rg.status_code == 201
    body = rg.get_json()
    assert body["previous_strategy_id"] == s2["id"]
    assert body["strategy"]["id"] != s2["id"]
    assert body["strategy"]["selected_topic"] != s2["selected_topic"]


def test_pin_and_priority_and_ordering(client):
    ch, nid = _seed_channel(client)
    a = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client)).get_json()["strategy"]
    b = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client)).get_json()["strategy"]
    client.patch(f"/api/content-director/{a['id']}", json={"priority": 5}, headers=_h(client))
    up = client.patch(f"/api/content-director/{b['id']}", json={"priority": 99, "pinned": True}, headers=_h(client))
    assert up.status_code == 200 and up.get_json()["strategy"]["pinned"] is True
    rows = client.get(f"/api/content-director?channel_id={ch}", headers=_h(client)).get_json()["strategies"]
    assert rows[0]["id"] == b["id"]  # pinned + highest priority first
    bad = client.patch(f"/api/content-director/{a['id']}", json={"priority": "high"}, headers=_h(client))
    assert bad.status_code == 400


# ------------------------------------------- multi-channel / multi-niche

def test_multi_channel_and_multi_niche_isolation(client):
    ch1, nid1 = _seed_channel(client, name="Эзо-1")
    # second channel, different niche
    nid2 = client.post("/api/niches", json={"name": "История"}, headers=_h(client)).get_json()["niche"]["id"]
    client.post(f"/api/niches/{nid2}/pillars",
                json={"name": "Древние цивилизации", "allowed_topics": "пирамиды; забытые города; артефакты"},
                headers=_h(client))
    ch2 = client.post("/api/channels", json={"name": "История-канал"}, headers=_h(client)).get_json()["channel"]["id"]
    client.patch(f"/api/channels/{ch2}", json={"niche_id": nid2, "language": "de",
                                               "daily_video_limit": 3}, headers=_h(client))
    s1 = client.post("/api/content-director/generate", json={"channel_id": ch1}, headers=_h(client)).get_json()["strategy"]
    s2 = client.post("/api/content-director/generate", json={"channel_id": ch2}, headers=_h(client)).get_json()["strategy"]
    assert s1["niche_id"] == nid1 and s2["niche_id"] == nid2
    assert s1["language"] == "ru" and s2["language"] == "de"
    # each channel's queue only shows its own ideas
    q1 = client.get(f"/api/content-director?channel_id={ch1}", headers=_h(client)).get_json()["strategies"]
    assert {x["channel_id"] for x in q1} == {ch1}
    # another allowlisted user cannot read this owner's strategies
    import importlib, os
    from tests.test_private_admin import ADMIN_EMAIL
    os.environ["ADMIN_ALLOWLIST_EMAILS"] = f"{ADMIN_EMAIL},cd_other@test.local"
    import saas_settings
    importlib.reload(saas_settings)
    other = _token_for(_seed_admin(email="cd_other@test.local", role="user"))
    r = client.get(f"/api/content-director/{s1['id']}", headers={"Authorization": f"Bearer {other}"})
    assert r.status_code in (403, 404)


# -------------------------------------------- stage 7: script generator

def test_approve_hands_off_to_script_generator(client):
    """Director produces the plan; the existing VideoProject/Script pipeline
    takes over. Director itself writes no script text."""
    ch, nid = _seed_channel(client)
    s = client.post("/api/content-director/generate", json={"channel_id": ch},
                    headers=_h(client)).get_json()["strategy"]
    r = client.post("/api/content-director/approve", json={"strategy_id": s["id"]}, headers=_h(client))
    assert r.status_code == 200, r.get_json()
    pid = r.get_json()["video_project_id"]

    proj = client.get(f"/api/video-projects/{pid}", headers=_h(client)).get_json()["project"]
    assert proj["title"] == s["selected_topic"]
    assert proj["content_pillar_id"] == s["pillar_id"]
    # script is NOT written by the Director — writer fills it later
    assert not proj["script_text"]
    # the plan travels with the project for the writer
    gp = proj["generation_profile"]
    assert gp["director"]["strategy_id"] == s["id"]
    assert gp["director"]["hook"] == s["selected_hook"]
    assert gp["director"]["angle"] == s["selected_angle"]
    assert gp["director"]["outline"]["structure"]
    assert gp["topic"] == s["selected_topic"]

    # strategy is now 'used' and cannot be approved/rejected again
    after = client.get(f"/api/content-director/{s['id']}", headers=_h(client)).get_json()["strategy"]
    assert after["status"] == "used" and after["video_project_id"] == pid
    assert client.post("/api/content-director/approve", json={"strategy_id": s["id"]}, headers=_h(client)).status_code == 409
    assert client.post("/api/content-director/reject", json={"strategy_id": s["id"]}, headers=_h(client)).status_code == 409
    assert client.post("/api/content-director/regenerate", json={"strategy_id": s["id"]}, headers=_h(client)).status_code == 409

    # and the writer can now add the script through the existing API
    upd = client.patch(f"/api/video-projects/{pid}",
                       json={"script_text": "Первое. Второе. Третье."}, headers=_h(client))
    assert upd.status_code == 200
    assert upd.get_json()["project"]["script_text"]


def test_rejected_strategy_cannot_be_approved(client):
    ch, nid = _seed_channel(client)
    s = client.post("/api/content-director/generate", json={"channel_id": ch},
                    headers=_h(client)).get_json()["strategy"]
    client.post("/api/content-director/reject", json={"strategy_id": s["id"]}, headers=_h(client))
    r = client.post("/api/content-director/approve", json={"strategy_id": s["id"]}, headers=_h(client))
    assert r.status_code == 409


def test_falls_back_to_next_pillar_when_ideas_exhausted(client):
    """Mass generation: when the best pillar's ideas are all duplicates, the
    Director moves to the next-ranked pillar instead of giving up."""
    ch, nid = _seed_channel(client)
    topics, pillars_used = [], []
    for _ in range(12):
        r = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client))
        if r.status_code != 201:
            break
        s = r.get_json()["strategy"]
        topics.append(s["selected_topic"])
        pillars_used.append(s["pillar_name"])
    # sustained unique output across many runs
    assert len(topics) >= 10, topics
    assert len(set(topics)) == len(topics)          # every idea unique
    assert len(set(pillars_used)) >= 4              # spread across pillars
    # at least one run had to try more than one pillar, and said so
    last = client.get(f"/api/content-director?channel_id={ch}", headers=_h(client)).get_json()["strategies"]
    detail = client.get(f"/api/content-director/{last[0]['id']}", headers=_h(client)).get_json()["strategy"]
    dup_stage = detail["decision"]["stages"]["duplicates"]
    assert "pillars_tried" in dup_stage and dup_stage["pillars_tried"]
    assert detail["decision"]["stages"]["ideation"]["pillar_attempts"]
