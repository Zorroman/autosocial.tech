import subprocess
from pathlib import Path
import re

from saas_settings import settings


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg_failed: {(proc.stderr or proc.stdout)[:1200]}")


def _resolution(orientation: str, resolution: str | None) -> tuple[int, int]:
    if resolution:
        if "x" in resolution:
            w, h = resolution.lower().split("x", 1)
            try:
                return (int(w), int(h))
            except Exception:
                pass
    if orientation == "vertical":
        return (1080, 1920)
    return (1920, 1080)


def _vf_scale_crop(width: int, height: int) -> str:
    return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"


def render_video(clips, voiceover_path, subtitles_path, out_path, orientation, fps, resolution):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = out.parent / f".tmp_{out.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    width, height = _resolution(orientation, resolution)
    fps = int(fps or 30)

    normalized = []
    is_short_render = sum(float(c.get("duration_target") or 0.0) for c in (clips or [])) <= 60.0
    temp_preset = "ultrafast"
    temp_crf = "30" if orientation == "vertical" else "28"
    for idx, clip in enumerate(clips):
        src = str(clip.get("clip_path") or "")
        target = float(clip.get("duration_target") or 2.0)
        target = max(0.8, min(40.0, target))
        dst = temp_dir / f"clip_{idx:03d}.mp4"
        _run(
            [
                settings.FFMPEG_BIN,
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                src,
                "-t",
                str(target),
                "-vf",
                f"{_vf_scale_crop(width, height)},fps={fps},format=yuv420p,fade=t=in:st=0:d=0.25,fade=t=out:st={max(0.0, target-0.25)}:d=0.25",
                "-c:v",
                "libx264",
                "-preset",
                temp_preset,
                "-crf",
                temp_crf,
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(dst),
            ]
        )
        normalized.append(dst)

    concat_txt = temp_dir / "concat.txt"
    concat_txt.write_text("\n".join([f"file '{x.as_posix()}'" for x in normalized]) + "\n", encoding="utf-8")

    cmd = [
        settings.FFMPEG_BIN,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_txt),
        "-i",
        str(voiceover_path),
    ]
    bg_music_path = (settings.VIDEO_BG_MUSIC_PATH or "").strip()
    bg_music_enabled = bool(settings.VIDEO_BG_MUSIC_ENABLED and bg_music_path and Path(bg_music_path).exists())
    if bg_music_enabled:
        cmd.extend(["-stream_loop", "-1", "-i", bg_music_path])

    filter_chain = []
    video_map = "0:v"
    audio_map = "1:a"
    if subtitles_path:
        sub_safe = str(subtitles_path).replace("\\", "/").replace(":", "\\:")
        if orientation == "vertical":
            # Use libass for better unicode wrapping and stable placement above player controls.
            force_style = (
                "FontName=Arial,"
                "FontSize=64,"
                "Alignment=2,"
                "MarginV=360,"
                "MarginL=72,"
                "MarginR=72,"
                "BorderStyle=1,"
                "Outline=3,"
                "Shadow=1,"
                "PrimaryColour=&H00FFFFFF&,"
                "OutlineColour=&H00202020&,"
                "BackColour=&H78000000&"
            )
            filter_chain.append(f"[0:v]subtitles='{sub_safe}':force_style='{force_style}'[v]")
        else:
            filter_chain.append(f"[0:v]subtitles='{sub_safe}'[v]")
        video_map = "[v]"
    if bg_music_enabled:
        # Keep music low so Eddy voice remains dominant.
        filter_chain.append("[2:a]volume=0.08,aresample=44100[bgm]")
        filter_chain.append("[1:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]")
        audio_map = "[aout]"
    if filter_chain:
        cmd.extend(["-filter_complex", ";".join(filter_chain)])
    cmd.extend(["-map", video_map, "-map", audio_map])
    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast" if is_short_render else "fast",
            "-crf",
            "22" if orientation == "vertical" else "20",
            "-c:a",
            "aac",
            "-shortest",
            "-r",
            str(fps),
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]
    )
    _run(cmd)
    return str(out)
