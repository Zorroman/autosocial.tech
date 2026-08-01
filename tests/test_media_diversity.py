"""Media Diversity Engine: dual-provider search, category diversity, and the
long-term reuse rule. Pipeline/scheduler/render themselves are untouched by
this feature -- see test_factory_pipeline_e2e.py and test_footage_subtitles.py
for proof those still pass unchanged.
"""
import subprocess

import pytest

from tests.test_private_admin import _fresh_app, _seed_admin, _token_for


@pytest.fixture()
def client(tmp_path):
    app_module = _fresh_app(tmp_path)
    admin_id = _seed_admin()
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)
        yield c


def _register_dummy_asset(db, tmp_path, name, query="candle dark"):
    from footage_library import register_asset
    p = tmp_path / f"{name}.mp4"
    color = f"0x{abs(hash(name)) % 0xFFFFFF:06x}"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=64x114:d=1:r=10",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
                   check=True, capture_output=True)
    return register_asset(db, provider="test", provider_asset_id=name, local_path=p,
                          search_query=query)


# ------------------------------------------------------------ pure functions

def test_infer_category_matches_known_keywords():
    from media_diversity import infer_category
    assert infer_category("misty forest morning") == "forest"
    assert infer_category("buddhist monk walking") == "monk"
    assert infer_category("person meditating in nature") == "meditation"
    assert infer_category("") is None
    assert infer_category("completely unrelated abstract nonsense xyz") is None


def test_category_penalty_favors_novelty():
    from media_diversity import category_penalty
    assert category_penalty(None, ["forest", "forest"]) == 0.0
    assert category_penalty("monk", []) == 20.0
    assert category_penalty("monk", ["forest", "sea"]) == 20.0  # not seen recently
    once = category_penalty("forest", ["sea", "forest"])
    most_recent = category_penalty("forest", ["sea", "forest", "forest"])
    assert once < 0
    assert most_recent < once  # repeating the MOST recent category is worse


def test_graduated_recency_penalty_matches_illustrative_table():
    from media_diversity import graduated_recency_penalty
    assert graduated_recency_penalty(None) == 100.0        # never used
    assert graduated_recency_penalty(400) == 50.0            # > 1 year
    assert graduated_recency_penalty(200) == 30.0            # > 6 months
    assert graduated_recency_penalty(45) == -50.0            # > 1 month
    assert graduated_recency_penalty(10) == -150.0           # > 1 week
    assert graduated_recency_penalty(1.5) == -500.0          # yesterday
    assert graduated_recency_penalty(0.5) == -10_000.0        # today: banned (finite, still composable)


def test_long_term_cooldown_ok_requires_both_thresholds():
    from media_diversity import long_term_cooldown_ok
    assert long_term_cooldown_ok(None, 0, min_days=90, min_uses=500) is True
    # day threshold not met yet, regardless of usage volume
    assert long_term_cooldown_ok(10, 1000, min_days=90, min_uses=500) is False
    # day threshold met, but not enough usage volume has passed since
    assert long_term_cooldown_ok(100, 10, min_days=90, min_uses=500) is False
    # both thresholds cleared
    assert long_term_cooldown_ok(100, 500, min_days=90, min_uses=500) is True


# ------------------------------------------------------- dual-provider search

def test_both_providers_participate(monkeypatch):
    from footage.types import VideoResult
    import media_diversity

    def fake_pexels(**kwargs):
        return [VideoResult(provider="pexels", video_id="p1", duration=10, width=1080,
                            height=1920, page_url="", download_url="u1", tags=[], orientation="vertical")]

    def fake_pixabay(**kwargs):
        return [VideoResult(provider="pixabay", video_id="x1", duration=10, width=1080,
                            height=1920, page_url="", download_url="u2", tags=[], orientation="vertical")]

    monkeypatch.setattr("footage.providers.pexels.search_videos", fake_pexels)
    monkeypatch.setattr("footage.providers.pixabay.search_videos", fake_pixabay)

    results = media_diversity.search_both_providers(
        "forest", orientation="vertical", min_duration=3, max_duration=60, limit=10)
    providers = {r.provider for r in results}
    assert providers == {"pexels", "pixabay"}
    assert len(results) == 2


def test_provider_fallback_when_one_fails(monkeypatch):
    from footage.types import VideoResult
    import media_diversity

    def broken_pexels(**kwargs):
        raise RuntimeError("network error")

    def fake_pixabay(**kwargs):
        return [VideoResult(provider="pixabay", video_id="x1", duration=10, width=1080,
                            height=1920, page_url="", download_url="u2", tags=[], orientation="vertical")]

    monkeypatch.setattr("footage.providers.pexels.search_videos", broken_pexels)
    monkeypatch.setattr("footage.providers.pixabay.search_videos", fake_pixabay)

    results = media_diversity.search_both_providers(
        "forest", orientation="vertical", min_duration=3, max_duration=60, limit=10)
    assert len(results) == 1
    assert results[0].provider == "pixabay"


def test_both_providers_failing_returns_empty_not_exception(monkeypatch):
    import media_diversity

    def broken(**kwargs):
        raise RuntimeError("down")

    monkeypatch.setattr("footage.providers.pexels.search_videos", broken)
    monkeypatch.setattr("footage.providers.pixabay.search_videos", broken)

    assert media_diversity.search_both_providers(
        "forest", orientation="vertical", min_duration=3, max_duration=60, limit=10) == []


def test_merge_dedupes_by_unique_key(monkeypatch):
    from footage.types import VideoResult
    import media_diversity

    dup = VideoResult(provider="pexels", video_id="same", duration=10, width=1080,
                      height=1920, page_url="", download_url="u", tags=[], orientation="vertical")

    monkeypatch.setattr("footage.providers.pexels.search_videos", lambda **kw: [dup, dup])
    monkeypatch.setattr("footage.providers.pixabay.search_videos", lambda **kw: [])

    results = media_diversity.search_both_providers(
        "forest", orientation="vertical", min_duration=3, max_duration=60, limit=10)
    assert len(results) == 1


# --------------------------------------------------------- DB-backed scoring

def test_category_stored_on_registration(client, tmp_path):
    from database import SessionLocal
    db = SessionLocal()
    a = _register_dummy_asset(db, tmp_path, "forestclip", query="misty forest morning")
    db.commit()
    assert a.category == "forest"
    db.close()


def test_score_candidates_penalizes_recent_category(client, tmp_path):
    from database import SessionLocal
    from footage_library import commit_usage, score_candidates
    db = SessionLocal()
    forest_a = _register_dummy_asset(db, tmp_path, "forest_a", query="misty forest morning")
    forest_b = _register_dummy_asset(db, tmp_path, "forest_b", query="forest trees sunlight")
    monk = _register_dummy_asset(db, tmp_path, "monk_clip", query="buddhist monk walking")
    db.commit()
    # channel 1 just used a forest clip
    commit_usage(db, asset=forest_a, project_id=801, channel_id=1, scene_id=None,
                start_time=0, duration=3)
    db.commit()

    scored = score_candidates(db, [forest_b, monk], channel_id=1, project_id=802,
                              job_id=None, min_duration=1)
    by_id = {x[1].id: x for x in scored}
    # same category as the just-used clip should score lower than a fresh category
    assert by_id[monk.id][0] > by_id[forest_b.id][0]
    assert by_id[forest_b.id][2]["category_bonus"] < 0
    assert by_id[monk.id][2]["category_bonus"] > 0
    db.close()


def test_long_term_cooldown_excludes_even_outside_soft_cooldowns(client, tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    from database import SessionLocal
    from app_settings import settings
    from footage_library import commit_usage, score_candidates
    monkeypatch.setattr(settings, "FOOTAGE_LONG_TERM_COOLDOWN_DAYS", 5)
    monkeypatch.setattr(settings, "FOOTAGE_LONG_TERM_COOLDOWN_USES", 3)
    # also shrink the soft cooldowns to 0 so only the long-term rule is in play
    monkeypatch.setattr(settings, "FOOTAGE_SAME_CHANNEL_COOLDOWN_DAYS", 0)
    monkeypatch.setattr(settings, "FOOTAGE_GLOBAL_COOLDOWN_DAYS", 0)

    db = SessionLocal()
    a = _register_dummy_asset(db, tmp_path, "longterm_a")
    db.commit()
    commit_usage(db, asset=a, project_id=701, channel_id=1, scene_id=None, start_time=0, duration=3)
    a.last_used_at = datetime.utcnow() - timedelta(days=10)  # day threshold cleared...
    db.commit()
    # ...but fewer than FOOTAGE_LONG_TERM_COOLDOWN_USES=3 usages have happened since.
    # Still present (not vanished -- the exhausted-search last-resort fallback
    # in acquire_segment_asset depends on rejected candidates staying
    # recoverable), but severely penalized and flagged.
    scored = score_candidates(db, [a], channel_id=2, project_id=702, job_id=None, min_duration=1)
    assert len(scored) == 1
    sc, asset, dbg = scored[0]
    assert sc < -1500
    assert dbg["long_term_cooldown"] is True

    # Add enough usage volume since, then it becomes eligible again (no penalty)
    for i in range(3):
        other = _register_dummy_asset(db, tmp_path, f"longterm_filler_{i}")
        commit_usage(db, asset=other, project_id=703, channel_id=1, scene_id=None, start_time=0, duration=3)
    db.commit()
    scored2 = score_candidates(db, [a], channel_id=2, project_id=704, job_id=None, min_duration=1)
    assert len(scored2) == 1
    assert "long_term_cooldown" not in scored2[0][2]
    db.close()
