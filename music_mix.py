"""Content Factory — quiet background-music bed for rendered Shorts.

Mixes a calm user-provided track UNDER the voiceover after render:
  * voiceover stays the main, intelligible layer;
  * music is faded in/out and ducked (sidechain) or held at a constant low
    level if sidechain is unavailable;
  * final loudness ~-14 LUFS, true peak <= -1 dBTP (loudnorm guarantees it, so
    the mix never clips);
  * video duration is unchanged (music trimmed/looped to the video length), so
    the 27–33s publish gate still holds.

Never breaks render: if no track is available or the mix fails to verify, the
original voiceover-only video is kept and music_status is set to 'no_music'.
"""
from __future__ import annotations

import os
import random
import subprocess
import tempfile
from pathlib import Path

import music_library

_FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
_FFPROBE = os.getenv("FFPROBE_BIN", "ffprobe")
MUSIC_MIX_VERSION = "1"
_MUSIC_BED_DB = os.getenv("MUSIC_BED_DB", "-20")           # music attenuation pre-mix
_MUSIC_ENABLED = (os.getenv("MUSIC_ENABLED", "true").lower() in {"1", "true", "yes"})


def _probe_dims(path: Path) -> dict:
    import json
    try:
        proc = subprocess.run(
            [_FFPROBE, "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        info = json.loads(proc.stdout or "{}")
        v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
        a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
        dur = float(info.get("format", {}).get("duration") or 0.0)
        return {
            "duration": dur,
            "has_video": v is not None,
            "has_audio": a is not None,
            "audio_duration": float((a or {}).get("duration") or 0.0),
        }
    except Exception:
        return {"duration": 0.0, "has_video": False, "has_audio": False, "audio_duration": 0.0}


def recent_track_ids(db, channel_id: int, window: int) -> list[str]:
    from saas_models import VideoProject
    rows = (db.query(VideoProject.music_track_id)
            .filter(VideoProject.channel_id == channel_id,
                    VideoProject.music_track_id.isnot(None))
            .order_by(VideoProject.id.desc())
            .limit(window).all())
    return [r[0] for r in rows if r[0]]


def _run(cmd: list[str]) -> bool:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return p.returncode == 0
    except Exception:
        return False


def _mix_cmd(video: Path, music: Path, start: float, dur: float, out: Path,
            loop: bool, sidechain: bool) -> list[str]:
    fade_out_start = max(0.0, dur - 1.2)
    music_chain = (
        f"[1:a]atrim=0:{dur:.3f},afade=t=in:st=0:d=0.8,"
        f"afade=t=out:st={fade_out_start:.3f}:d=1.2,volume={_MUSIC_BED_DB}dB[m];"
    )
    if sidechain:
        graph = (music_chain
                 + "[m][0:a]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=250[md];"
                 + "[0:a][md]amix=inputs=2:duration=longest:normalize=0,"
                   "loudnorm=I=-14:TP=-2:LRA=11[a]")
    else:
        graph = (music_chain
                 + "[0:a][m]amix=inputs=2:duration=longest:normalize=0,"
                   "loudnorm=I=-14:TP=-2:LRA=11[a]")
    cmd = [_FFMPEG, "-y"]
    cmd += ["-i", str(video)]
    if loop:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
    else:
        cmd += ["-ss", f"{start:.3f}", "-i", str(music)]
    cmd += ["-filter_complex", graph,
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-ar", "48000", "-ac", "2",   # YouTube-standard stereo 48kHz
            "-movflags", "+faststart", str(out)]
    return cmd


def add_music_bed(project, video_abs: Path, db) -> dict:
    """Mix a quiet music bed into the rendered video (in place on success).
    Returns a status dict and updates the project's music_* fields. Never raises
    to the caller — render must not be broken by music."""
    result = {"music_status": "no_music", "track_id": None, "title": None}

    def _set_project(**kw):
        for k, v in kw.items():
            if hasattr(project, k):
                setattr(project, k, v)

    if not _MUSIC_ENABLED:
        _set_project(music_status="disabled")
        result["music_status"] = "disabled"
        return result

    video_abs = Path(video_abs)
    dims = _probe_dims(video_abs)
    if not dims["has_audio"] or dims["duration"] <= 0:
        # no voiceover to sit under — leave as-is (audio gate handles it later)
        _set_project(music_status="no_music")
        return result

    try:
        recent = recent_track_ids(db, project.channel_id, music_library.NO_REPEAT_WINDOW)
    except Exception:
        recent = []
    track = music_library.select_track(exclude_ids=recent)
    if not track:
        _set_project(music_status="no_music")
        return result

    music_file = Path(track["file_path"])
    if not music_file.exists():
        _set_project(music_status="no_music")
        return result

    vid_dur = dims["duration"]
    track_dur = float(track.get("duration_seconds") or 0.0)
    loop = track_dur < (vid_dur + 0.5)
    start = 0.0 if loop else round(random.uniform(0.0, max(0.0, track_dur - vid_dur)), 2)

    tmp_out = Path(tempfile.mkstemp(suffix=".mp4", dir=str(video_abs.parent))[1])
    ok = False
    for sidechain in (True, False):  # prefer ducking, fall back to constant low level
        if _run(_mix_cmd(video_abs, music_file, start, vid_dur, tmp_out, loop, sidechain)):
            v = _probe_dims(tmp_out)
            # verify: audio present, duration preserved (band unchanged), audio ~ video
            if (v["has_audio"] and v["has_video"]
                    and abs(v["duration"] - vid_dur) <= 1.0
                    and v["audio_duration"] >= vid_dur - 1.0):
                ok = True
                break
        try:
            tmp_out.unlink(missing_ok=True)
            tmp_out = Path(tempfile.mkstemp(suffix=".mp4", dir=str(video_abs.parent))[1])
        except Exception:
            pass

    if not ok:
        try:
            tmp_out.unlink(missing_ok=True)
        except Exception:
            pass
        _set_project(music_status="no_music")  # fallback: keep voiceover-only video
        result["music_status"] = "no_music"
        return result

    # success — replace the render with the mixed version
    os.replace(str(tmp_out), str(video_abs))
    try:
        music_library.mark_used(track)
    except Exception:
        pass
    _set_project(
        music_track_id=track.get("id"),
        music_title=track.get("title"),
        music_provider=track.get("source", "Suno"),
        music_start_seconds=start,
        music_end_seconds=round(start + vid_dur, 2),
        music_gain_db=float(_MUSIC_BED_DB),
        music_status="mixed",
        music_mix_version=MUSIC_MIX_VERSION,
    )
    result.update({"music_status": "mixed", "track_id": track.get("id"),
                   "title": track.get("title"), "start": start})
    return result
