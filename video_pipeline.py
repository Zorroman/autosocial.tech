import json
import re
import threading
from datetime import datetime
from pathlib import Path

from footage_matcher import match_shots
from footage.shots import normalize_shot_specs
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


def _manifest_path(job_id: int) -> Path:
    return settings.OUTPUT_MANIFESTS_DIR / f"{int(job_id)}.json"


def _to_rel(path: str | Path) -> str:
    p = Path(path).resolve()
    return str(p.relative_to(settings.BASE_DIR)).replace("\\", "/")


def _from_rel(path_rel: str) -> Path:
    return (settings.BASE_DIR / str(path_rel or "").strip()).resolve()


def _load_manifest_if_possible(job_id: int) -> dict | None:
    path = _manifest_path(job_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def generate_video_job_payload(
    *,
    job_id: int,
    campaign_id: int,
    topic: str,
    offer: str | None,
    language: str,
    target_seconds: int,
    aspect_ratio: str,
    style: str,
    use_lecture_txt: bool = True,
    reuse_manifest: bool = False,
) -> dict:
    target_seconds = max(20, min(480, int(target_seconds or 30)))
    orientation = "vertical" if aspect_ratio == "9:16" else "horizontal"
    if reuse_manifest:
        old = _load_manifest_if_possible(job_id)
        if old:
            out_rel = ((old.get("render") or {}).get("out_path") or "").strip()
            if out_rel:
                out_abs = _from_rel(out_rel)
                if out_abs.exists():
                    audio_rel = ((old.get("audio") or {}).get("local_path") or "").strip()
                    sub_rel = ((old.get("subtitles") or {}).get("local_path") or "").strip()
                    return {
                        "video_local_path": str(out_abs),
                        "video_url": _public_media_url(out_abs),
                        "audio_url": _public_media_url(_from_rel(audio_rel)) if audio_rel else "",
                        "subtitles_url": _public_media_url(_from_rel(sub_rel)) if sub_rel else "",
                        "manifest_url": _public_media_url(_manifest_path(job_id)),
                        "title": str(old.get("title") or ""),
                        "description": str(old.get("description") or ""),
                        "hashtags": list(old.get("hashtags") or []),
                        "safety_rules": list(old.get("safety_rules") or []),
                        "target_seconds": int(old.get("target_seconds") or target_seconds),
                    }

    script: ScriptBundle = generate_script(
        topic=topic,
        offer=offer,
        language=language or "ru",
        target_seconds=target_seconds,
        style=style or "educational",
    )
    run_id = f"job{job_id}_camp{campaign_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{_safe_slug(topic)}"

    audio_path, phrase_durations = synthesize_voiceover(
        script.phrases,
        out_dir=settings.OUTPUT_AUDIO_DIR,
        prefix=run_id,
    )

    shot_specs = normalize_shot_specs(script.phrases, script.shotlist[: len(script.phrases)], phrase_durations)
    clips = match_shots(shot_specs=shot_specs, orientation=orientation)
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
        "job_id": str(job_id),
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
        "phrases": script.phrases,
        "title": script.title,
        "description": script.description,
        "hashtags": script.hashtags,
        "safety_rules": script.safety_rules,
        "shots": [
            {
                "phrase_index": c.phrase_index,
                "phrase_text": c.phrase_text,
                "duration_s": c.duration_target,
                "queries": [c.query_used],
                "chosen_clip": {
                    "provider": c.provider,
                    "id": c.clip_id,
                    "url": c.clip_url,
                    "local_path": _to_rel(c.clip_path),
                    "start_trim_s": c.start_trim_s,
                    "end_trim_s": c.end_trim_s,
                    "score_breakdown": c.score_breakdown,
                },
            }
            for c in clips
        ],
        "audio": {
            "voice": "Eddy",
            "local_path": _to_rel(audio_path),
            "duration_s": round(sum(phrase_durations), 3),
        },
        "subtitles": {
            "mode": "word",
            "local_path": _to_rel(subtitles_path),
        },
        "render": {
            "fps": 30,
            "resolution": "1080x1920" if orientation == "vertical" else "1920x1080",
            "out_path": _to_rel(out_video),
        },
        "clips": [
            {
                "shot_index": c.shot_index,
                "phrase_index": c.phrase_index,
                "clip_path": _to_rel(c.clip_path),
                "provider": c.provider,
                "duration_target": c.duration_target,
                "query_used": c.query_used,
                "score": c.score,
                "score_breakdown": c.score_breakdown,
            }
            for c in clips
        ],
    }
    manifest_path = _manifest_path(job_id)
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
