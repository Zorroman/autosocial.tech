"""Media matching + scheduler reservation tests.

The media_matcher functions are pure/injectable, so these run without network:
a fake `search_fn` stands in for Pexels and a fake `llm` for OpenAI. The last
test exercises the scheduler's DB reservation guard against a double tick.
"""
import os
import sys
from types import SimpleNamespace

import pytest

import media_matcher as mm


# --------------------------------------------------------------- test helpers

def C(video_id, slug, tags=None, orient="vertical"):
    """A fake Pexels VideoResult-ish candidate."""
    return SimpleNamespace(
        video_id=str(video_id),
        page_url=f"https://www.pexels.com/video/{slug}-{video_id}/",
        tags=tags or [],
        orientation=orient,
    )


def S(scene_id, voiceover):
    return SimpleNamespace(id=scene_id, voiceover_text=voiceover,
                           estimated_duration=6.0, stock_search_query=None, visual_prompt="")


def fake_llm(payload):
    def _call(**kwargs):
        # mimic generate_json_with_retry: validate then return .payload
        v = kwargs.get("validator")
        if v:
            v(payload)
        return SimpleNamespace(payload=payload)
    return _call


ABSTRACT = [
    S(1, "Символы окружают нас повсюду, они рассказывают свои истории."),
    S(2, "Мы часто не замечаем, как символы формируют нашу реальность."),
    S(3, "Символы связывают нас с культурой и историей."),
    S(4, "Каждый символ — это отражение нашей жизни."),
]


# 1) Abstract theme, 4 scenes → concrete English plan from the LLM
def test_abstract_theme_llm_plan():
    payload = {
        "scenes": [
            {"id": 1, "queries": ["starry night sky timelapse", "glowing constellations"],
             "simple": "night sky", "keywords": ["stars", "sky", "night"]},
            {"id": 2, "queries": ["mysterious ancient symbols carved"], "simple": "symbols",
             "keywords": ["symbols", "carved"]},
            {"id": 3, "queries": ["old temple ruins"], "simple": "temple", "keywords": ["temple", "ruins"]},
            {"id": 4, "queries": ["candle flame dark"], "simple": "candle", "keywords": ["candle", "flame"]},
        ],
        "atmospheric": ["sacred geometry", "northern lights", "mystical smoke"],
    }
    plan = mm.plan_project_queries(ABSTRACT, "ЭЗОТЕРИКА", "ru", llm=fake_llm(payload))
    assert plan.source == "llm"
    assert set(plan.scenes) == {1, 2, 3, 4}
    # queries must be ASCII/English (no Cyrillic leaked through)
    for sp in plan.scenes.values():
        for q in sp.queries:
            assert q.isascii(), q
    assert plan.atmospheric and all(a.isascii() for a in plan.atmospheric)


def _raising_llm(**kwargs):
    """An LLM callable that fails, forcing the deterministic heuristic path."""
    raise RuntimeError("llm down")


# 2) Concrete theme, 4 scenes → deterministic heuristic (LLM unavailable)
def test_concrete_theme_heuristic_plan():
    scenes = [S(i, "звёздное небо и символы вселенной") for i in range(1, 5)]
    plan = mm.plan_project_queries(scenes, "ЭЗОТЕРИКА", "ru", llm=_raising_llm)
    assert plan.source == "heuristic"
    assert set(plan.scenes) == {1, 2, 3, 4}
    for sp in plan.scenes.values():
        assert sp.queries and all(q.isascii() for q in sp.queries)
    # esoteric niche → real-scene atmospheric pool (no abstract terms)
    assert "misty forest morning" in plan.atmospheric


# 3) First (concrete) query returns nothing, fallback finds material
def test_fallback_finds_when_primary_empty():
    sp = mm.ScenePlan(1, queries=["specific rare thing"], simple="thing", keywords=["thing"])
    atmos = ["starry night sky"]

    def search(q, excl):
        if q == "starry night sky":
            return [C(100, "starry-night-sky-timelapse")]
        return []  # concrete + simple find nothing

    pick = mm.pick_media(sp, atmos, search_fn=search, exclude_ids=set())
    assert pick.candidate is not None
    assert pick.confidence == "atmospheric"
    assert pick.candidate.video_id == "100"


# 3b) Abstract/CGI "screensaver" footage is rejected in favour of real footage
def test_abstract_footage_rejected():
    assert mm.is_abstract_footage(C(1, "abstract-glowing-particles-loop"))
    assert mm.is_abstract_footage(C(2, "3d-geometric-neon-tunnel"))
    assert not mm.is_abstract_footage(C(3, "misty-forest-morning-trees"))
    assert not mm.is_abstract_footage(C(4, "slow-motion-ocean-waves"))  # 'motion' not a marker

    sp = mm.ScenePlan(1, queries=["forest"], simple="forest", keywords=["forest", "trees"])

    def search(q, excl):
        # provider returns an abstract clip first, a real one second
        return [C(10, "abstract-particles-background"), C(11, "green-forest-trees-fog")]

    pick = mm.pick_media(sp, [], search_fn=search, exclude_ids=set())
    assert pick.candidate is not None
    assert pick.candidate.video_id == "11"          # real footage chosen
    assert not mm.is_abstract_footage(pick.candidate)


# 4) Provider returns empty everywhere → honest needs_review
def test_provider_empty_needs_review():
    sp = mm.ScenePlan(1, queries=["anything"], simple="x", keywords=["x"])
    pick = mm.pick_media(sp, ["atmos term"], search_fn=lambda q, e: [], exclude_ids=set())
    assert pick.candidate is None
    assert pick.confidence == "needs_review"


# 5) Provider returns duplicates → the same clip is never reused within a video
def test_duplicates_not_reused_within_video():
    sp = mm.ScenePlan(1, queries=["glowing runes"], simple="runes", keywords=["runes"])
    used = {"777"}  # already used earlier in this project

    def search(q, excl):
        # provider hands back a dup of the used clip plus one fresh
        return [C(777, "ancient-runes-stone"), C(778, "ancient-runes-temple")]

    pick = mm.pick_media(sp, [], search_fn=search, exclude_ids=used)
    assert pick.candidate is not None
    assert pick.candidate.video_id == "778"  # the used 777 is skipped


# 6) All concrete candidates score 0 relevance → concrete rejected, atmospheric taken
def test_low_score_concrete_falls_through_to_atmospheric():
    sp = mm.ScenePlan(1, queries=["ancient symbols"], simple="symbols", keywords=["symbols"])

    def search(q, excl):
        if q == "ancient symbols":
            return [C(1, "unrelated-cat-playing"), C(2, "random-office-desk")]  # 0 overlap
        return [C(9, "misty-forest-fog-morning")]

    pick = mm.pick_media(sp, ["sacred geometry"], search_fn=search, exclude_ids=set())
    # concrete rejected (score 0 < 1), atmospheric accepted
    assert pick.confidence == "atmospheric"
    assert pick.candidate.video_id == "9"


# 7) Vertical candidates flow through unchanged (orientation is provider-enforced)
def test_vertical_candidate_selected():
    sp = mm.ScenePlan(1, queries=["candle flame"], simple="candle", keywords=["candle", "flame"])
    cand = C(5, "candle-flame-dark", orient="vertical")
    pick = mm.pick_media(sp, [], search_fn=lambda q, e: [cand], exclude_ids=set())
    assert pick.candidate is cand
    assert pick.candidate.orientation == "vertical"
    assert pick.confidence == "matched"


# 8) A concrete match with real relevance is preferred over atmospheric
def test_relevant_concrete_preferred():
    sp = mm.ScenePlan(1, queries=["starry night sky"], simple="sky", keywords=["stars", "sky", "night"])

    def search(q, excl):
        if q == "starry night sky":
            return [C(11, "starry-night-sky-stars")]  # score >= 1
        return [C(99, "sacred-geometry")]

    pick = mm.pick_media(sp, ["sacred geometry"], search_fn=search, exclude_ids=set())
    assert pick.confidence == "matched"
    assert pick.candidate.video_id == "11"
    assert pick.diagnostics["chosen_score"] >= 1


# 9) Diagnostics always record every stage tried (auditable needs_review)
def test_diagnostics_record_stages():
    sp = mm.ScenePlan(1, queries=["q1", "q2"], simple="s", keywords=["k"])
    pick = mm.pick_media(sp, ["a1"], search_fn=lambda q, e: [], exclude_ids=set())
    tried = pick.diagnostics["stages_tried"]
    queries = [t["query"] for t in tried]
    assert queries == ["q1", "q2", "s", "a1"]  # full ladder walked in order


# 10) Scheduler: two concurrent ticks must not both reserve the same channel
def test_scheduler_reservation_blocks_double_generation(tmp_path):
    from tests.test_private_admin import _fresh_app, _seed_admin
    for m in ("scheduler",):
        sys.modules.pop(m, None)
    _fresh_app(tmp_path)
    admin_id = _seed_admin()

    from database import SessionLocal
    from saas_models import Channel
    import scheduler

    db = SessionLocal()
    ch = Channel(owner_user_id=admin_id, name="Ch", slug="ch", niche="ЭЗОТЕРИКА",
                 language="ru", status="active", niche_id=1, daily_video_limit=6,
                 automatic_generation_enabled=True, last_generated_at=None)
    db.add(ch)
    db.commit()
    cid = ch.id
    db.close()

    # Shorts only generate inside the daytime window (default 06:00–22:00 local);
    # this test is about the reservation lock, not the clock, so open the window
    # to 24h for determinism regardless of when the suite runs.
    os.environ["SHORTS_WINDOW_START_HOUR"] = "0"
    os.environ["SHORTS_WINDOW_END_HOUR"] = "24"

    # First tick reserves the slot (advances last_generated_at inside the txn).
    reserved1, owner1, limit1 = scheduler._reserve(cid)
    assert reserved1 is True
    assert owner1 == admin_id and limit1 == 6

    # Second, immediately-following tick must be refused: the reservation moved
    # last_generated_at to now, so the due-time re-check inside the transaction
    # fails. (On Postgres the row lock also serialises truly-concurrent ticks;
    # SQLite runs them serially, which still proves the due-recheck guard.)
    reserved2, _, _ = scheduler._reserve(cid)
    assert reserved2 is False


# 11) Scheduler backlog cap: no new generation past FACTORY_BACKLOG_LIMIT
def test_scheduler_backlog_limit_blocks(tmp_path, monkeypatch):
    from tests.test_private_admin import _fresh_app, _seed_admin
    for m in ("scheduler",):
        sys.modules.pop(m, None)
    _fresh_app(tmp_path)
    admin_id = _seed_admin()

    from database import SessionLocal
    from saas_models import Channel, VideoProject
    import scheduler
    monkeypatch.setattr(scheduler, "_BACKLOG_LIMIT", 3)

    db = SessionLocal()
    ch = Channel(owner_user_id=admin_id, name="Ch", slug="ch2", niche="ЭЗОТЕРИКА",
                 language="ru", status="active", niche_id=1, daily_video_limit=6,
                 automatic_generation_enabled=True, last_generated_at=None)
    db.add(ch)
    db.commit()
    cid = ch.id
    # 3 unfinished factory projects (needs_review) == backlog full
    for i in range(3):
        db.add(VideoProject(channel_id=cid, title=f"p{i}", status="draft",
                            pipeline_stage="media", pipeline_state="needs_review"))
    db.commit()
    db.close()

    reserved, _, _ = scheduler._reserve(cid)
    assert reserved is False  # backlog full → no new generation


# 12) Scheduler single-active-pipeline: a running pipeline blocks a new one
def test_scheduler_single_active_pipeline(tmp_path):
    from tests.test_private_admin import _fresh_app, _seed_admin
    for m in ("scheduler",):
        sys.modules.pop(m, None)
    _fresh_app(tmp_path)
    admin_id = _seed_admin()

    from database import SessionLocal
    from saas_models import Channel, VideoProject
    import scheduler

    db = SessionLocal()
    ch = Channel(owner_user_id=admin_id, name="Ch", slug="ch3", niche="ЭЗОТЕРИКА",
                 language="ru", status="active", niche_id=1, daily_video_limit=6,
                 automatic_generation_enabled=True, last_generated_at=None)
    db.add(ch)
    db.commit()
    cid = ch.id
    db.add(VideoProject(channel_id=cid, title="running", status="draft",
                        pipeline_stage="render", pipeline_state="running"))
    db.commit()
    db.close()

    reserved, _, _ = scheduler._reserve(cid)
    assert reserved is False  # one pipeline already running → no new generation
