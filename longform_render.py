"""Long-form image-first renderer — memory-safe chunked 1080p (CPX22, ~3.8 GB).

Isolated from the Shorts render path (video/render/render_video.py is untouched).
The whole point: NEVER hold many decoded video streams or run one giant
filter_complex. Instead:

  1. each base still photo is pre-scaled once to a small over-size canvas
     (2400x1350) on disk;
  2. each timeline segment is a Ken-Burns animation of ONE still (zoom/pan/crop)
     rendered by ONE short ffmpeg process to a segment .mp4 — peak memory is a
     single 2400x1350 image + the encoder, which cannot OOM;
  3. segments are grouped into ~30–60s chunks and concatenated (stream copy,
     no re-encode); each chunk is ffprobe-verified;
  4. chunks are concatenated (stream copy) into the final silent 1080p video.

Audio (voiceover + music) is mixed in a separate, later step so the video render
and the audio mix never peak together. No AI image generation, no AI video.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

_FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
_FFPROBE = os.getenv("FFPROBE_BIN", "ffprobe")

W = int(os.getenv("LONGFORM_RENDER_WIDTH", "1920"))
H = int(os.getenv("LONGFORM_RENDER_HEIGHT", "1080"))
FPS = int(os.getenv("LONGFORM_RENDER_FPS", "25"))
THREADS = max(1, min(2, int(os.getenv("LONGFORM_MAX_RENDER_THREADS", "2"))))
CHUNK_SECONDS = int(os.getenv("LONGFORM_RENDER_CHUNK_SECONDS", "40"))
# Over-size canvas gives room to pan/zoom to 1920x1080 without upscaling blur,
# while staying small in memory (~10 MB decoded).
_PREP_W, _PREP_H = 2400, 1350

# Only smooth horizontal pans — no zoom (zoompan zoom causes the jitter/shake
# the user disliked). A crop window slides across the oversize canvas: no zoom,
# no sub-pixel jitter, just a calm left↔right glide.
_MOTIONS = ("pan_right", "pan_left")


@dataclass
class Segment:
    image: str
    seconds: float
    motion: str
    # "photo" (Ken-Burns pan of a still, via render_segment) or "clip" (real
    # video footage, via render_clip_segment -- no Ken-Burns, the clip's own
    # motion is the motion). Defaults to "photo" so every existing caller
    # that only ever built photo segments keeps working unchanged.
    kind: str = "photo"
    clip_start: float = 0.0


@dataclass
class ChunkState:
    order: int
    file_path: str = ""
    status: str = "pending"        # pending|rendering|succeeded|failed
    start_seconds: float = 0.0
    duration_seconds: float = 0.0
    attempts: int = 0
    ffprobe_passed: bool = False
    file_size_bytes: int = 0
    error: str | None = None


def _run(cmd: list[str], timeout: int = 900) -> tuple[bool, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode == 0, (p.stderr or "")[-500:]
    except Exception as exc:
        return False, str(exc)[:300]


def prep_image(src: Path, dst: Path) -> bool:
    """Scale+center-crop a photo to the over-size canvas once, on disk."""
    ok, _ = _run([
        _FFMPEG, "-y", "-i", str(src),
        "-vf", (f"scale={_PREP_W}:{_PREP_H}:force_original_aspect_ratio=increase,"
                f"crop={_PREP_W}:{_PREP_H}"),
        "-frames:v", "1", str(dst),
    ], timeout=120)
    return ok and dst.exists()


def _pan_vf(motion: str, seconds: float) -> str:
    """A jitter-free horizontal pan: slide a WxH crop window across the oversize
    2400x1350 canvas. No zoom, so no sub-pixel shake — just a calm glide.
    y is centre-cropped; the ~480px of extra width is traversed over `seconds`."""
    dur = max(0.5, float(seconds))
    if motion == "pan_left":   # image content moves left→right (camera pans right→left)
        x = f"(iw-{W})*(1-t/{dur:.3f})"
    else:                       # pan_right: camera glides left→right
        x = f"(iw-{W})*(t/{dur:.3f})"
    return (f"crop={W}:{H}:x='max(0,min(iw-{W},{x}))':y='(ih-{H})/2',format=yuv420p")


def render_segment(prepped_image: Path, out: Path, seconds: float, motion: str) -> tuple[bool, str]:
    """Animate one still with a smooth horizontal pan → a WxH segment. One ffmpeg
    process, low memory, no jitter."""
    return _run([
        _FFMPEG, "-y", "-loop", "1", "-i", str(prepped_image),
        "-t", f"{seconds:.3f}", "-r", str(FPS),
        "-vf", _pan_vf(motion, seconds),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-threads", str(THREADS),
        "-video_track_timescale", "90000", "-an", str(out),
    ], timeout=600)


def render_clip_segment(clip_path: Path, out: Path, seconds: float, start: float = 0.0) -> tuple[bool, str]:
    """Normalize ONE real video clip → a WxH/FPS segment (scale-cover + centre-crop,
    trimmed to `seconds`). One ffmpeg process = one decoded stream, so peak memory
    stays bounded exactly like a still segment — this is what keeps mixing real
    footage OOM-safe on the 3.8 GB box (vs the old all-clips-at-once filter graph)."""
    return _run([
        _FFMPEG, "-y", "-ss", f"{max(0.0, start):.3f}", "-i", str(clip_path),
        "-t", f"{seconds:.3f}", "-r", str(FPS),
        "-vf", (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},format=yuv420p"),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-threads", str(THREADS),
        "-video_track_timescale", "90000", "-an", str(out),
    ], timeout=600)


def _concat_copy(parts: list[Path], out: Path, work: Path) -> tuple[bool, str]:
    lst = work / f"concat_{out.stem}.txt"
    lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts) + "\n", encoding="utf-8")
    return _run([_FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                 "-c", "copy", str(out)], timeout=600)


def _probe(path: Path) -> dict:
    ok, _ = _run([_FFPROBE, "-v", "quiet", str(path)], timeout=30)
    try:
        p = subprocess.run([_FFPROBE, "-v", "quiet", "-print_format", "json",
                            "-show_streams", "-show_format", str(path)],
                           capture_output=True, text=True, timeout=30)
        info = json.loads(p.stdout or "{}")
        v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        return {"ok": bool(v), "duration": float(info.get("format", {}).get("duration") or 0),
                "width": int(v.get("width") or 0), "height": int(v.get("height") or 0)}
    except Exception:
        return {"ok": False, "duration": 0, "width": 0, "height": 0}


def render_video(segments: list[Segment], out_path: Path, work_dir: Path,
                 chunk_seconds: int = CHUNK_SECONDS) -> dict:
    """Render the full silent 1080p video from still-image segments, chunked.
    Returns a manifest (chunks, sizes, ffprobe). Resumable: existing good
    segment/chunk files are reused."""
    work_dir.mkdir(parents=True, exist_ok=True)
    seg_dir = work_dir / "segments"; seg_dir.mkdir(exist_ok=True)
    chunk_dir = work_dir / "chunks"; chunk_dir.mkdir(exist_ok=True)

    # 1) render each segment (memory-safe, one source at a time; resumable)
    seg_files: list[Path] = []
    for i, s in enumerate(segments):
        sf = seg_dir / f"seg_{i:04d}.mp4"
        if not (sf.exists() and sf.stat().st_size > 2000):
            if s.kind == "clip":
                ok, err = render_clip_segment(Path(s.image), sf, s.seconds, s.clip_start)
            else:
                ok, err = render_segment(Path(s.image), sf, s.seconds, s.motion)
            if not ok:
                return {"status": "failed", "stage": "segment", "index": i, "error": err}
        seg_files.append(sf)

    # 2) group segments into chunks, concat each (stream copy), ffprobe each
    chunks: list[ChunkState] = []
    order = 0
    cur: list[Path] = []
    cur_dur = 0.0
    start = 0.0

    def _flush(cur_files, order, start, cur_dur):
        cs = ChunkState(order=order, start_seconds=round(start, 2),
                        duration_seconds=round(cur_dur, 2))
        cf = chunk_dir / f"chunk_{order:03d}.mp4"
        cs.attempts = 1
        if not (cf.exists() and cf.stat().st_size > 2000):
            ok, err = _concat_copy(cur_files, cf, work_dir)
            if not ok:
                cs.status = "failed"; cs.error = err; chunks.append(cs); return cs
        pr = _probe(cf)
        cs.file_path = str(cf); cs.file_size_bytes = cf.stat().st_size if cf.exists() else 0
        cs.ffprobe_passed = bool(pr["ok"] and pr["width"] == W and pr["height"] == H)
        cs.status = "succeeded" if cs.ffprobe_passed else "failed"
        if not cs.ffprobe_passed:
            cs.error = f"ffprobe/res mismatch {pr}"
        chunks.append(cs)
        return cs

    for sf, s in zip(seg_files, segments):
        cur.append(sf); cur_dur += s.seconds
        if cur_dur >= chunk_seconds:
            cs = _flush(cur, order, start, cur_dur)
            if cs.status != "succeeded":
                return {"status": "failed", "stage": "chunk", "chunks": [c.__dict__ for c in chunks]}
            order += 1; start += cur_dur; cur = []; cur_dur = 0.0
    if cur:
        cs = _flush(cur, order, start, cur_dur)
        if cs.status != "succeeded":
            return {"status": "failed", "stage": "chunk", "chunks": [c.__dict__ for c in chunks]}

    # 3) concat all chunks (stream copy) → final silent video
    good = [Path(c.file_path) for c in chunks if c.status == "succeeded"]
    if not good:
        return {"status": "failed", "stage": "no_chunks", "chunks": [c.__dict__ for c in chunks]}
    ok, err = _concat_copy(good, Path(out_path), work_dir)
    if not ok:
        return {"status": "failed", "stage": "final_concat", "error": err}
    final = _probe(Path(out_path))
    return {
        "status": "succeeded" if (final["ok"] and final["width"] == W and final["height"] == H) else "failed",
        "output": str(out_path),
        "duration": round(final["duration"], 2),
        "width": final["width"], "height": final["height"], "fps": FPS,
        "chunk_count": len(chunks),
        "chunks": [c.__dict__ for c in chunks],
    }


def build_segments(image_paths: list[str], total_seconds: float,
                   min_seg: float = 5.0, max_seg: float = 10.0) -> list[Segment]:
    """Spread the base images across the timeline as Ken-Burns segments,
    cycling motion patterns and reusing images (a curated set), no adjacent
    identical motion."""
    if not image_paths:
        return []
    segs: list[Segment] = []
    seg_len = max(min_seg, min(max_seg, 8.0))
    n = max(1, int(round(total_seconds / seg_len)))
    for i in range(n):
        img = image_paths[i % len(image_paths)]
        motion = _MOTIONS[i % len(_MOTIONS)]
        segs.append(Segment(image=img, seconds=seg_len, motion=motion))
    return segs
