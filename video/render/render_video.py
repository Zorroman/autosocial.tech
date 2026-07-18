import subprocess
from pathlib import Path

from saas_settings import settings


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg_failed: {(proc.stderr or proc.stdout)[:1200]}")


def _resolution(orientation: str, resolution: str | None) -> tuple[int, int]:
    if resolution and "x" in resolution:
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


def render_video(clips, voiceover_path, subtitles_path, out_path, orientation, fps, resolution, subtitle_profile: dict | None = None):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = out.parent / f".tmp_{out.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    width, height = _resolution(orientation, resolution)
    fps = int(fps or 30)
    subtitle_profile = subtitle_profile or {}

    normalized = []
    is_short_render = sum(float(c.get("duration_target") or 0.0) for c in (clips or [])) <= 60.0
    temp_preset = "ultrafast"
    temp_crf = "30" if orientation == "vertical" else "28"
    fade = max(0.0, min(0.5, float(getattr(settings, "VIDEO_CLIP_FADE_SECONDS", 0.2))))
    n_clips = len(clips or [])
    for idx, clip in enumerate(clips):
        src = str(clip.get("clip_path") or "")
        target = float(clip.get("duration_target") or 2.0)
        target = max(0.8, min(40.0, target))
        dst = temp_dir / f"clip_{idx:03d}.mp4"
        # Interior boundaries are hard cuts (no dip-to-black between segments);
        # only the very first/last clip fade from/to black.
        fades = []
        if fade > 0 and idx == 0:
            fades.append(f"fade=t=in:st=0:d={fade}")
        if fade > 0 and idx == n_clips - 1:
            fades.append(f"fade=t=out:st={max(0.0, target - fade)}:d={fade}")
        motion = str(clip.get("motion") or "")
        motion_vf = ""
        if motion in {"in", "out"}:
            frames = max(1, int(target * fps))
            if motion == "in":
                zexpr = f"min(1.10,1+0.10*on/{frames})"
            else:
                zexpr = f"max(1.0,1.10-0.10*on/{frames})"
            motion_vf = (
                f",zoompan=z='{zexpr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d=1:s={width}x{height}:fps={fps}"
            )
        vf = f"{_vf_scale_crop(width, height)},fps={fps}{motion_vf},format=yuv420p"
        if fades:
            vf += "," + ",".join(fades)
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
                vf,
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
        if str(subtitles_path).lower().endswith(".ass"):
            # ASS carries its own styles (safe-zone margins, fonts) - don't override.
            filter_chain.append(f"[0:v]subtitles='{sub_safe}'[v]")
        elif orientation == "vertical":
            force_style = (
                f"FontName={subtitle_profile.get('font_name', 'Arial')},"
                f"FontSize={int(subtitle_profile.get('font_size', 64))},"
                f"Alignment={int(subtitle_profile.get('alignment', 2))},"
                f"MarginV={int(subtitle_profile.get('margin_v', 430))},"
                f"MarginL={int(subtitle_profile.get('margin_lr', 84))},"
                f"MarginR={int(subtitle_profile.get('margin_lr', 84))},"
                "BorderStyle=1,"
                f"Outline={float(subtitle_profile.get('outline', 3.0))},"
                f"Shadow={float(subtitle_profile.get('shadow', 1.0))},"
                f"PrimaryColour={subtitle_profile.get('primary_colour', '&H00FFFFFF')},"
                f"OutlineColour={subtitle_profile.get('outline_colour', '&H00111111')},"
                f"BackColour={subtitle_profile.get('back_colour', '&H8C000000')},"
                f"Bold={int(subtitle_profile.get('bold', 1))}"
            )
            filter_chain.append(f"[0:v]subtitles='{sub_safe}':force_style='{force_style}'[v]")
        else:
            filter_chain.append(f"[0:v]subtitles='{sub_safe}'[v]")
        video_map = "[v]"
    if bg_music_enabled:
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
