import subprocess
from pathlib import Path

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
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(dst),
            ]
        )
        normalized.append(dst)

    concat_txt = temp_dir / "concat.txt"
    concat_txt.write_text("\n".join([f"file '{x.as_posix()}'" for x in normalized]) + "\n", encoding="utf-8")
    stitched = temp_dir / "stitched.mp4"
    _run(
        [
            settings.FFMPEG_BIN,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(stitched),
        ]
    )

    cmd = [
        settings.FFMPEG_BIN,
        "-y",
        "-i",
        str(stitched),
        "-i",
        str(voiceover_path),
    ]
    filter_chain = []
    if subtitles_path:
        sub_safe = str(subtitles_path).replace("\\", "/").replace(":", "\\:")
        filter_chain.append(f"[0:v]subtitles='{sub_safe}'[v]")
        cmd.extend(["-filter_complex", ";".join(filter_chain), "-map", "[v]", "-map", "1:a"])
    else:
        cmd.extend(["-map", "0:v", "-map", "1:a"])
    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            "-r",
            str(fps),
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            "4500k" if orientation == "horizontal" else "3200k",
            str(out),
        ]
    )
    _run(cmd)
    return str(out)
