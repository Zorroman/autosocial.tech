"""Footage repeat-protection + professional subtitle tests."""
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.test_private_admin import _fresh_app, _seed_admin, _token_for


def _fresh(tmp_path):
    for m in ("publications_api", "video_projects_api", "analytics_api", "ai_pricing",
              "factory_dashboard_api", "footage_library", "subtitle_builder"):
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


LONG_SCRIPT = (
    "Чёрная луна веками считалась знаком перемен и обновления. "
    "Её символ встречается в древних рукописях и на стенах храмов. "
    "Алхимики связывали её с внутренней трансформацией человека. "
    "Мистики утверждали, что в такие ночи граница миров истончается. "
    "Сегодня этот образ продолжает жить в культуре и искусстве. "
    "Многие художники посвящали ей свои самые загадочные работы. "
    "Что на самом деле скрывает этот древний символ? "
    "Дождитесь конца ролика, чтобы узнать главную тайну."
)


def _mk_rendered_project(c, channel_name="Эзотерика", script=LONG_SCRIPT):
    ch = c.post("/api/channels", json={"name": channel_name}, headers=_h(c)).get_json()["channel"]["id"]
    pid = c.post("/api/video-projects", json={"channel_id": ch, "title": "Тест", "script_text": script, "voice_mode": "silent"}, headers=_h(c)).get_json()["project"]["id"]
    scenes = c.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(c)).get_json()["scenes"]
    for s in scenes:
        r = c.post(f"/api/scenes/{s['id']}/fixture-media", headers=_h(c))
        assert r.status_code == 200
    r = c.post(f"/api/video-projects/{pid}/render", headers=_h(c))
    assert r.status_code == 202
    job = c.get(f"/api/video-projects/{pid}", headers=_h(c)).get_json()["project"]["jobs"][0]
    return ch, pid, job


# ------------------------------------------------------------ segmentation

def test_segment_plan_three_seconds():
    from footage_library import segment_plan
    plan = segment_plan(30.0)
    assert all(2.5 <= s <= 3.5 for s in plan)
    assert abs(sum(plan) - 30.0) < 0.05
    assert segment_plan(2.0) == [2.0]  # short scene = one segment
    plan9 = segment_plan(9.0)
    assert len(plan9) == 3 and all(abs(s - 3.0) < 0.01 for s in plan9)


def test_no_repeat_inside_video_and_timeline(client):
    from app_settings import settings
    ch, pid, job = _mk_rendered_project(client)
    assert job["status"] == "completed", job["error"]
    manifest = settings.OUTPUT_MANIFESTS_DIR / f"project_{pid}_job_{job['id']}.json"
    assert manifest.exists()
    timeline = json.loads(manifest.read_text(encoding="utf-8"))["timeline"]
    assert len(timeline) >= 2
    # segment lengths ~3s (last of a scene may absorb remainder within bounds)
    for seg in timeline:
        assert 0.8 <= seg["duration"] <= 3.6
    # no provider_asset_id / file_hash repeats without an explicit reuse reason
    seen_ids, seen_hashes = set(), set()
    for seg in timeline:
        if seg["footage_reuse_reason"] is None:
            assert seg["provider_asset_id"] not in seen_ids
            if seg["file_hash"]:
                assert seg["file_hash"] not in seen_hashes
        seen_ids.add(seg["provider_asset_id"])
        if seg["file_hash"]:
            seen_hashes.add(seg["file_hash"])


def test_video_duration_matches_voiceover(client):
    from app_settings import settings
    ch, pid, job = _mk_rendered_project(client)
    assert job["status"] == "completed", job["error"]
    out = settings.BASE_DIR / job["output_path"]
    probe = subprocess.run(
        [settings.FFPROBE_BIN, "-v", "quiet", "-print_format", "json", "-show_format", str(out)],
        capture_output=True, text=True, check=True)
    dur = float(json.loads(probe.stdout)["format"]["duration"])
    scenes = client.get(f"/api/video-projects/{pid}", headers=_h(client)).get_json()["project"]["scenes"]
    expected = sum(s["estimated_duration"] for s in scenes)
    assert abs(dur - expected) < 1.5


# -------------------------------------------------------------- cooldowns

def _register_dummy_asset(db, tmp_path, name, query="candle dark"):
    from footage_library import register_asset
    p = tmp_path / f"{name}.mp4"
    # unique color per name so SHA-256 differs between dummy assets
    color = f"0x{abs(hash(name)) % 0xFFFFFF:06x}"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=64x114:d=1:r=10",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
                   check=True, capture_output=True)
    return register_asset(db, provider="test", provider_asset_id=name, local_path=p,
                          search_query=query)


def test_same_channel_and_global_cooldown(client, tmp_path):
    from database import SessionLocal
    from footage_library import commit_usage, score_candidates
    db = SessionLocal()
    a = _register_dummy_asset(db, tmp_path, "cool1")
    b = _register_dummy_asset(db, tmp_path, "cool2")
    db.commit()
    # a used on channel 1 recently -> hard penalty on channel 1
    commit_usage(db, asset=a, project_id=901, channel_id=1, scene_id=None,
                 start_time=0, duration=3)
    db.commit()
    scored = score_candidates(db, [a, b], channel_id=1, project_id=902, job_id=None, min_duration=1)
    by_id = {x[1].id: x for x in scored}
    same_channel_score = by_id[a.id][0]
    assert same_channel_score < -400  # same-channel cooldown penalty
    assert by_id[b.id][0] > 0
    assert by_id[a.id][2].get("same_channel_cooldown") is True
    # on another channel -> softer global-cooldown penalty than same-channel
    # (both are also very negative now on top of that: `a` was used moments
    # ago, so the Media Diversity Engine's graduated recency penalty and
    # long-term-cooldown penalty apply equally regardless of channel -- see
    # test_media_diversity.py for those in isolation. What this test actually
    # checks is the same_channel vs global cooldown *relationship*.)
    scored2 = score_candidates(db, [a], channel_id=2, project_id=903, job_id=None, min_duration=1)
    sc, _, dbg = scored2[0]
    assert sc < 0
    assert sc > same_channel_score  # global cooldown alone is softer than same-channel
    assert dbg.get("global_cooldown") is True
    assert not dbg.get("same_channel_cooldown")
    db.close()


def test_sha256_dedup(client, tmp_path):
    from database import SessionLocal
    from footage_library import register_asset
    db = SessionLocal()
    a = _register_dummy_asset(db, tmp_path, "orig")
    # same bytes, different provider id/URL -> must resolve to the same asset
    dup_path = tmp_path / "copy.mp4"
    dup_path.write_bytes(Path(a.local_path).read_bytes())
    b = register_asset(db, provider="test", provider_asset_id="different-id",
                       local_path=dup_path, download_url="https://other.url/x.mp4")
    assert b.id == a.id
    db.close()


def test_parallel_jobs_do_not_share_asset(client, tmp_path):
    from database import SessionLocal
    from footage_library import reserve_asset
    db = SessionLocal()
    a = _register_dummy_asset(db, tmp_path, "race1")
    db.commit()
    assert reserve_asset(db, a, job_id=111) is True
    db2 = SessionLocal()
    from app_models import FootageAsset
    a2 = db2.query(FootageAsset).filter_by(id=a.id).first()
    assert reserve_asset(db2, a2, job_id=222) is False  # second job blocked
    assert reserve_asset(db2, a2, job_id=111) is True   # same job may re-confirm
    from footage_library import release_job_reservations
    release_job_reservations(db, 111)
    assert reserve_asset(db2, a2, job_id=222) is True   # freed -> available
    db.close(); db2.close()


def test_expired_reservation_released(client, tmp_path, monkeypatch):
    from database import SessionLocal
    from footage_library import _release_expired_reservations, reserve_asset
    from app_models import FootageAsset
    db = SessionLocal()
    a = _register_dummy_asset(db, tmp_path, "exp1")
    db.commit()
    reserve_asset(db, a, job_id=333)
    db.query(FootageAsset).filter_by(id=a.id).update(
        {"reserved_at": datetime.utcnow() - timedelta(hours=2)})
    db.commit()
    _release_expired_reservations(db)
    db.commit()
    fresh = db.query(FootageAsset).filter_by(id=a.id).first()
    assert fresh.reserved_by_job_id is None
    db.close()


def test_reuse_fallback_when_no_candidates(client):
    # fixture project uses the same pool; segments beyond unique fixtures must
    # carry an explicit reuse reason instead of failing
    from app_settings import settings
    ch, pid, job = _mk_rendered_project(client)
    assert job["status"] == "completed"
    manifest = settings.OUTPUT_MANIFESTS_DIR / f"project_{pid}_job_{job['id']}.json"
    timeline = json.loads(manifest.read_text(encoding="utf-8"))["timeline"]
    reused = [s for s in timeline if s["footage_reuse_reason"]]
    for seg in reused:
        assert seg["footage_reuse_reason"] in {"cooldown_reuse_after_exhausted_search", "insufficient_unique_candidates_after_exhausted_search"}
        assert "footage_candidate_count" in seg


# -------------------------------------------------------------- subtitles

def test_subtitle_line_limits_and_orphans():
    from subtitle_builder import split_into_cue_texts
    cues = split_into_cue_texts(LONG_SCRIPT)
    assert cues
    for cue in cues:
        lines = cue.split("\n")
        assert len(lines) <= 2
        for line in lines:
            assert len(line) <= 38
        if len(lines) == 2:
            assert len(lines[1]) >= 4  # no orphan short word


def test_subtitle_timing_and_ass_safe_zone(tmp_path):
    from subtitle_builder import build_cues, write_ass
    cues = build_cues([{"text": LONG_SCRIPT, "start": 0.0, "duration": 30.0}])
    assert cues
    assert cues[0]["start"] >= 0
    assert all(c["end"] > c["start"] for c in cues)
    assert abs(cues[-1]["end"] - 30.0) < 1.0  # covers the audio
    out = tmp_path / "test.ass"
    write_ass(cues, out)
    content = out.read_text(encoding="utf-8")
    assert "PlayResY: 1920" in content
    # safe zone: MarginV within 320..420 px from the bottom
    style = next(l for l in content.splitlines() if l.startswith("Style:"))
    margin_v = int(style.split(",")[21])
    assert 320 <= margin_v <= 420
    assert style.split(",")[18] == "2"  # Alignment 2 = bottom-center
    # Cyrillic survives UTF-8 round trip
    assert "Чёрная" in content


def test_subtitle_highlight_optional(tmp_path, monkeypatch):
    from subtitle_builder import build_cues, write_ass
    cues = build_cues([{"text": "Тайна древних символов ждёт вас", "start": 0, "duration": 4}])
    out = tmp_path / "h.ass"
    write_ass(cues, out, highlight=False)
    assert r"\c&H00FFFF&" not in out.read_text(encoding="utf-8")
    write_ass(cues, out, highlight=True)
    assert r"\c&H00FFFF&" in out.read_text(encoding="utf-8")


def test_long_line_auto_shrinks(tmp_path):
    from subtitle_builder import write_ass
    long_word_cue = [{"start": 0, "end": 2, "text": "Сверхдлинноесловокотороеневозможноразбитьнормально дополнительно"}]
    out = tmp_path / "shrink.ass"
    write_ass(long_word_cue, out)
    assert r"\fs" in out.read_text(encoding="utf-8")  # font shrunk, not clipped


def test_media_library_stats(client, tmp_path):
    ch, pid, job = _mk_rendered_project(client)
    r = client.get("/api/media-library/stats", headers=_h(client))
    assert r.status_code == 200
    d = r.get_json()
    assert d["total_assets"] >= 1
    assert d["used_today"] >= 1
    assert d["settings"]["same_channel_cooldown_days"] == 30
    assert client.get("/api/media-library/stats").status_code == 401


# ==================================================== strict review additions

def test_segment_plan_5_10_30_60():
    from footage_library import segment_plan
    for total in (5.0, 10.0, 30.0, 60.0):
        plan = segment_plan(total)
        assert abs(sum(plan) - total) <= 0.1, (total, plan)
        assert all(s >= 0.8 for s in plan), (total, plan)
        assert all(2.5 <= s <= 3.5 for s in plan), (total, plan)
    # awkward totals: sum still exact, no degenerate tail even out of bounds
    for total in (7.2, 4.1, 11.3, 37.97):
        plan = segment_plan(total)
        assert abs(sum(plan) - total) <= 0.1, (total, plan)
        assert all(s >= 0.8 for s in plan), (total, plan)


def test_cooldown_exact_boundaries(client, tmp_path):
    from database import SessionLocal
    from footage_library import score_candidates
    from app_models import FootageUsage
    db = SessionLocal()
    a29 = _register_dummy_asset(db, tmp_path, "b29")
    a30 = _register_dummy_asset(db, tmp_path, "b30")
    g6 = _register_dummy_asset(db, tmp_path, "b6")
    g7 = _register_dummy_asset(db, tmp_path, "b7")
    db.commit()
    now = datetime.utcnow()

    def _usage(asset, channel, days):
        db.add(FootageUsage(footage_asset_id=asset.id, video_project_id=800,
                            channel_id=channel, used_at=now - timedelta(days=days),
                            start_time=0, duration=3))
    _usage(a29, 1, 29)   # same channel, 29d -> blocked
    _usage(a30, 1, 30)   # same channel, 30d -> allowed
    _usage(g6, 2, 6)     # other channel, 6d -> penalized
    _usage(g7, 2, 7)     # other channel, 7d -> allowed
    db.commit()
    scored = {x[1].id: x for x in score_candidates(
        db, [a29, a30, g6, g7], channel_id=1, project_id=801, job_id=None, min_duration=1)}
    assert scored[a29.id][0] < -400 and scored[a29.id][2].get("same_channel_cooldown")
    assert scored[a30.id][0] > 0 and not scored[a30.id][2].get("same_channel_cooldown")
    assert -1000 < scored[g6.id][0] < 0 and scored[g6.id][2].get("global_cooldown")
    assert scored[g7.id][0] > 0 and not scored[g7.id][2].get("global_cooldown")
    db.close()


def test_project_asset_blocked_regardless_of_cooldown(client, tmp_path):
    from database import SessionLocal
    from footage_library import score_candidates
    from app_models import FootageUsage
    db = SessionLocal()
    a = _register_dummy_asset(db, tmp_path, "proj_block")
    db.commit()
    # used in THIS project long ago (cooldown expired) -> still hard-blocked
    db.add(FootageUsage(footage_asset_id=a.id, video_project_id=555, channel_id=1,
                        used_at=datetime.utcnow() - timedelta(days=90),
                        start_time=0, duration=3))
    db.commit()
    scored = score_candidates(db, [a], channel_id=1, project_id=555, job_id=None, min_duration=1)
    assert scored == []  # excluded entirely, not just penalized
    db.close()


def test_failed_render_does_not_consume_cooldown(client, monkeypatch):
    """reservation released + no FootageUsage when render fails."""
    from database import SessionLocal
    from app_models import FootageAsset, FootageUsage
    import importlib
    rv = importlib.import_module("video.render.render_video")

    ch = client.post("/api/channels", json={"name": "FailCh"}, headers=_h(client)).get_json()["channel"]["id"]
    pid = client.post("/api/video-projects", json={"channel_id": ch, "title": "Fail", "script_text": "Раз. Два. Три. Четыре.", "voice_mode": "silent"}, headers=_h(client)).get_json()["project"]["id"]
    for s in client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client)).get_json()["scenes"]:
        client.post(f"/api/scenes/{s['id']}/fixture-media", headers=_h(client))

    db = SessionLocal()
    usage_before = db.query(FootageUsage).count()
    db.close()

    def boom(*a, **k):
        raise RuntimeError("ffmpeg_exploded_for_test")
    monkeypatch.setattr(rv, "render_video", boom)

    r = client.post(f"/api/video-projects/{pid}/render", headers=_h(client))
    assert r.status_code == 202
    job = client.get(f"/api/video-projects/{pid}", headers=_h(client)).get_json()["project"]["jobs"][0]
    assert job["status"] == "failed"
    assert "ffmpeg_exploded_for_test" in job["error"]

    db = SessionLocal()
    assert db.query(FootageUsage).count() == usage_before  # cooldown NOT consumed
    assert db.query(FootageAsset).filter(FootageAsset.reserved_by_job_id.isnot(None)).count() == 0
    db.close()


def test_successful_render_creates_usage_after_validation(client):
    """lifecycle: usage rows appear only for completed job, count == segments."""
    from database import SessionLocal
    from app_models import FootageUsage
    from app_settings import settings
    ch, pid, job = _mk_rendered_project(client, channel_name="LifeCh")
    assert job["status"] == "completed"
    manifest = settings.OUTPUT_MANIFESTS_DIR / f"project_{pid}_job_{job['id']}.json"
    timeline = json.loads(manifest.read_text(encoding="utf-8"))["timeline"]
    db = SessionLocal()
    usages = db.query(FootageUsage).filter_by(video_project_id=pid).all()
    assert len(usages) == len(timeline)
    db.close()


def test_concurrent_next_candidate_selection(client, tmp_path):
    """Two jobs see the same best candidate; loser must take the NEXT one."""
    from database import SessionLocal
    from footage_library import score_candidates, select_and_reserve
    db1, db2 = SessionLocal(), SessionLocal()
    best = _register_dummy_asset(db1, tmp_path, "conc_best", query="candle dark")
    second = _register_dummy_asset(db1, tmp_path, "conc_second", query="candle dark")
    db1.commit()
    from app_models import FootageAsset
    b2 = db2.query(FootageAsset).filter_by(id=best.id).first()
    s2 = db2.query(FootageAsset).filter_by(id=second.id).first()

    scored1 = score_candidates(db1, [best, second], channel_id=1, project_id=701, job_id=1, min_duration=1)
    scored2 = score_candidates(db2, [b2, s2], channel_id=1, project_id=702, job_id=2, min_duration=1)
    assert scored1[0][1].id == scored2[0][1].id  # both see the same best

    _, won1, _ = select_and_reserve(db1, scored1, job_id=1, used_asset_ids=set(), used_hashes=set())
    _, won2, _ = select_and_reserve(db2, scored2, job_id=2, used_asset_ids=set(), used_hashes=set())
    assert won1 is not None and won2 is not None
    assert won1.id != won2.id  # loser moved on to the next unique candidate
    db1.close(); db2.close()


def test_manifest_search_budget_fields(client):
    from app_settings import settings
    ch, pid, job = _mk_rendered_project(client, channel_name="BudgetCh")
    manifest = settings.OUTPUT_MANIFESTS_DIR / f"project_{pid}_job_{job['id']}.json"
    timeline = json.loads(manifest.read_text(encoding="utf-8"))["timeline"]
    non_primary = [s for s in timeline if s["segment"] > 0]
    for seg in non_primary:
        for field in ("search_queries_attempted", "pages_attempted", "candidates_examined",
                      "candidates_rejected_cooldown", "candidates_rejected_duplicate",
                      "reuse_was_unavoidable"):
            assert field in seg, seg
        if seg["footage_reuse_reason"]:
            # a reuse without exhausting the search budget is a bug
            assert seg["reuse_was_unavoidable"] is True
            assert seg["search_queries_attempted"] >= 2


def test_subtitles_ru_de_en_and_escaping(tmp_path):
    from subtitle_builder import build_cues, split_into_cue_texts, write_ass
    samples = {
        "ru": "Чёрная луна — древний символ перемен, «знак» номер 7. Скрытая {тайна} и путь\\дорога.",
        "de": "Die geheimnisvolle Nacht überraschte alle Bewohner der Straße völlig unerwartet.",
        "en": 'The ancient symbol of the "black moon" has 12 hidden meanings - watch until the end.',
    }
    for lang, text in samples.items():
        cues = build_cues([{"text": text, "start": 0, "duration": 10}])
        assert cues, lang
        for cue in split_into_cue_texts(text):
            for line in cue.split("\n"):
                assert len(line) <= 38, (lang, line)
        out = tmp_path / f"{lang}.ass"
        write_ass(cues, out)
        content = out.read_text(encoding="utf-8")
        # special chars neutralized so they can't break ASS parsing
        dialogue = "\n".join(l for l in content.splitlines() if l.startswith("Dialogue:"))
        assert "{тайна}" not in dialogue
        # only our own control tags may contain backslash/braces
        import re as _re
        stripped = _re.sub(r"\{\\[^}]*\}", "", dialogue)  # remove our tags
        assert "\\N" in dialogue or "\n" not in dialogue  # line breaks via \N only
        assert "{" not in stripped and "}" not in stripped
    # umlauts and quotes survive
    de = (tmp_path / "de.ass").read_text(encoding="utf-8")
    assert "überraschte" in de
