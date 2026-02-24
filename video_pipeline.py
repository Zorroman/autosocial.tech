import json
import re
import threading
from datetime import datetime
from pathlib import Path

from footage_matcher import match_shots
from saas_settings import settings
from video.render.render_video import render_video
from video.subtitles import build_ass_subtitles, load_subtitle_lines
from video.tts import synthesize_voiceover
from video_script_generator import ScriptBundle, generate as generate_script


_RENDER_SEMAPHORE = threading.Semaphore(settings.VIDEO_RENDER_CONCURRENCY)


def _safe_slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9а-яА-Я_-]+", "-", str(text or "").strip()).strip("-").lower()
    return value[:80] or "video"


def _public_media_url(path: Path) -> str:
    rel = path.resolve().relative_to(settings.BASE_DIR).as_posix()
    return f"{settings.API_BASE_URL}/api/media/{rel}"


def generate_video_job_payload(
    *,
    campaign_id: int,
    topic: str,
    offer: str | None,
    language: str,
    target_seconds: int,
    aspect_ratio: str,
    style: str,
    use_lecture_txt: bool = True,
) -> dict:
    target_seconds = max(20, min(480, int(target_seconds or 30)))
    orientation = "vertical" if aspect_ratio == "9:16" else "horizontal"
    script: ScriptBundle = generate_script(
        topic=topic,
        offer=offer,
        language=language or "ru",
        target_seconds=target_seconds,
        style=style or "educational",
    )
    run_id = f"camp{campaign_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{_safe_slug(topic)}"

    audio_path, phrase_durations = synthesize_voiceover(
        script.phrases,
        out_dir=settings.OUTPUT_AUDIO_DIR,
        prefix=run_id,
    )

    shotlist = script.shotlist[: len(script.phrases)]
    clips = match_shots(
        shotlist=shotlist,
        phrase_durations=phrase_durations,
        orientation=orientation,
    )
    lecture_path = (settings.BASE_DIR / "lecture.txt") if use_lecture_txt else None
    subtitle_lines = load_subtitle_lines(lecture_path, script.phrases)
    subtitles_path = settings.OUTPUT_SUBTITLES_DIR / f"{run_id}.ass"
    build_ass_subtitles(
        lines=subtitle_lines,
        phrase_durations=phrase_durations,
        out_path=subtitles_path,
        reveal_mode="word",
    )
    out_video = settings.OUTPUT_VIDEOS_DIR / f"{run_id}.mp4"

    with _RENDER_SEMAPHORE:
        render_video(
            clips=[{"clip_path": c.clip_path, "duration_target": c.duration_target} for c in clips],
            voiceover_path=audio_path,
            subtitles_path=str(subtitles_path),
            out_path=str(out_video),
            orientation=orientation,
            fps=30,
            resolution="1080x1920" if orientation == "vertical" else "1920x1080",
        )

    manifest = {
        "run_id": run_id,
        "campaign_id": campaign_id,
        "topic": topic,
        "offer": offer,
        "language": language,
        "target_seconds": target_seconds,
        "aspect_ratio": aspect_ratio,
        "orientation": orientation,
        "script": {
            "phrases": script.phrases,
            "shotlist": script.shotlist,
            "title": script.title,
            "description": script.description,
            "hashtags": script.hashtags,
            "safety_rules": script.safety_rules,
        },
        "voiceover_path": str(Path(audio_path).resolve().relative_to(settings.BASE_DIR)).replace("\\", "/"),
        "subtitles_path": str(subtitles_path.resolve().relative_to(settings.BASE_DIR)).replace("\\", "/"),
        "video_path": str(out_video.resolve().relative_to(settings.BASE_DIR)).replace("\\", "/"),
        "clips": [
            {
                "shot_index": c.shot_index,
                "phrase_index": c.phrase_index,
                "clip_path": str(Path(c.clip_path).resolve().relative_to(settings.BASE_DIR)).replace("\\", "/"),
                "provider": c.provider,
                "duration_target": c.duration_target,
                "queries_used": c.queries_used,
            }
            for c in clips
        ],
    }
    manifest_path = settings.OUTPUT_MANIFESTS_DIR / f"{run_id}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "video_local_path": str(out_video),
        "video_url": _public_media_url(out_video),
        "audio_url": _public_media_url(Path(audio_path)),
        "subtitles_url": _public_media_url(subtitles_path),
        "manifest_url": _public_media_url(manifest_path),
        "title": script.title,
        "description": script.description,
        "hashtags": script.hashtags,
        "safety_rules": script.safety_rules,
        "target_seconds": target_seconds,
    }
