from pathlib import Path

from footage.ranking import is_rejected, select_best_clip
from footage.shots import ShotSpec
from footage.types import VideoResult
from video_pipeline import generate_video_job_payload


def _spec() -> ShotSpec:
    return ShotSpec(
        phrase_index=0,
        phrase_text="Команда работает над стратегией",
        duration_s=3.2,
        desired_scene="work",
        mood="calm",
        queries=["office team work"],
        fallback_queries=["office work", "business meeting"],
        must_include=["realistic", "real life", "office", "team"],
        must_exclude=["fantasy", "anime", "cartoon"],
    )


def test_banned_tokens_filtering():
    bad = VideoResult(
        provider="pexels",
        video_id="1",
        duration=6,
        width=1920,
        height=1080,
        page_url="https://example.com/fantasy-dragon",
        download_url="https://example.com/1.mp4",
        tags=["cinematic", "dragon"],
        orientation="horizontal",
        title="Fantasy Dragon",
    )
    assert is_rejected(bad) is True


def test_ranking_stable_best_candidate():
    spec = _spec()
    candidates = [
        VideoResult(
            provider="pexels",
            video_id="11",
            duration=3,
            width=1280,
            height=720,
            page_url="https://pexels.com/a",
            download_url="https://cdn/a.mp4",
            tags=["office", "team", "meeting"],
            orientation="horizontal",
            title="Office team meeting",
            author="john",
        ),
        VideoResult(
            provider="pixabay",
            video_id="22",
            duration=8,
            width=1920,
            height=1080,
            page_url="https://pixabay.com/b",
            download_url="https://cdn/b.mp4",
            tags=["nature", "landscape"],
            orientation="horizontal",
            title="Nature landscape",
            author="kate",
        ),
    ]
    memory = {"ids": set(), "authors": set(), "tag_signatures": [], "query_groups_used": {}, "selected_results": []}
    best = select_best_clip(spec, candidates, already_selected=memory, orientation="horizontal")
    assert best is not None
    assert best.candidate.video_id == "11"


def test_diversity_penalizes_same_author():
    spec = _spec()
    a = VideoResult(
        provider="pexels",
        video_id="1",
        duration=5,
        width=1920,
        height=1080,
        page_url="https://pexels.com/1",
        download_url="https://cdn/1.mp4",
        tags=["office", "team"],
        orientation="horizontal",
        title="Office team meeting",
        author="same-author",
    )
    b = VideoResult(
        provider="pexels",
        video_id="2",
        duration=5,
        width=1920,
        height=1080,
        page_url="https://pexels.com/2",
        download_url="https://cdn/2.mp4",
        tags=["office", "team"],
        orientation="horizontal",
        title="Office team meeting",
        author="other-author",
    )
    memory = {"ids": set(), "authors": {"same-author"}, "tag_signatures": [], "query_groups_used": {}, "selected_results": []}
    best = select_best_clip(spec, [a, b], already_selected=memory, orientation="horizontal")
    assert best is not None
    assert best.candidate.video_id == "2"


def test_manifest_saved_and_reused(monkeypatch, tmp_path):
    import video_pipeline as vp
    from saas_settings import settings

    settings.BASE_DIR = tmp_path.resolve()
    settings.CACHE_DIR = (settings.BASE_DIR / "cache").resolve()
    settings.OUTPUT_DIR = (settings.BASE_DIR / "output").resolve()
    settings.FOOTAGE_CACHE_DIR = (settings.CACHE_DIR / "footage").resolve()
    settings.OUTPUT_VIDEOS_DIR = (settings.OUTPUT_DIR / "videos").resolve()
    settings.OUTPUT_AUDIO_DIR = (settings.OUTPUT_DIR / "audio").resolve()
    settings.OUTPUT_SUBTITLES_DIR = (settings.OUTPUT_DIR / "subtitles").resolve()
    settings.OUTPUT_MANIFESTS_DIR = (settings.OUTPUT_DIR / "manifests").resolve()
    for p in [
        settings.CACHE_DIR,
        settings.OUTPUT_DIR,
        settings.FOOTAGE_CACHE_DIR,
        settings.OUTPUT_VIDEOS_DIR,
        settings.OUTPUT_AUDIO_DIR,
        settings.OUTPUT_SUBTITLES_DIR,
        settings.OUTPUT_MANIFESTS_DIR,
    ]:
        p.mkdir(parents=True, exist_ok=True)

    class Bundle:
        phrases = ["Фраза 1", "Фраза 2"]
        shotlist = [{"phrase_index": 0, "queries": ["office work"], "mood": "calm", "scene_type": "work"}]
        title = "Title"
        description = "Desc"
        hashtags = ["#a"]
        safety_rules = ["only realistic scenes"]

    class Clip:
        shot_index = 0
        phrase_index = 0
        phrase_text = "Фраза 1"
        clip_path = str((settings.FOOTAGE_CACHE_DIR / "c1.mp4").resolve())
        provider = "pexels"
        clip_id = "123"
        clip_url = "https://cdn/1.mp4"
        duration_target = 2.2
        start_trim_s = 0.0
        end_trim_s = 2.2
        query_used = "office work"
        score = 88.0
        score_breakdown = {"semantic_relevance": 0.9}

    (settings.FOOTAGE_CACHE_DIR / "c1.mp4").write_bytes(b"x")
    dummy_audio = settings.OUTPUT_AUDIO_DIR / "a.mp3"
    dummy_audio.write_bytes(b"x")

    monkeypatch.setattr(vp, "generate_script", lambda **_kwargs: Bundle())
    monkeypatch.setattr(vp, "synthesize_voiceover", lambda *_args, **_kwargs: (str(dummy_audio), [1.1, 1.2]))
    monkeypatch.setattr(vp, "normalize_shot_specs", lambda *args, **kwargs: [_spec()])
    monkeypatch.setattr(vp, "match_shots", lambda **_kwargs: [Clip()])
    monkeypatch.setattr(vp, "load_subtitle_lines", lambda *_args, **_kwargs: ["Фраза 1", "Фраза 2"])
    monkeypatch.setattr(vp, "build_ass_subtitles", lambda **kwargs: str(Path(kwargs["out_path"])))

    def _render_stub(**kwargs):
        Path(kwargs["out_path"]).write_bytes(b"video")
        return kwargs["out_path"]

    monkeypatch.setattr(vp, "render_video", _render_stub)

    first = generate_video_job_payload(
        job_id=9001,
        campaign_id=44,
        topic="Тема",
        offer="Оффер",
        language="ru",
        target_seconds=30,
        aspect_ratio="9:16",
        style="expert",
        reuse_manifest=False,
    )
    assert Path(first["video_local_path"]).exists()
    manifest_path = settings.OUTPUT_MANIFESTS_DIR / "9001.json"
    assert manifest_path.exists()

    monkeypatch.setattr(vp, "match_shots", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("should_not_run")))
    second = generate_video_job_payload(
        job_id=9001,
        campaign_id=44,
        topic="Тема",
        offer="Оффер",
        language="ru",
        target_seconds=30,
        aspect_ratio="9:16",
        style="expert",
        reuse_manifest=True,
    )
    assert second["video_local_path"] == first["video_local_path"]
