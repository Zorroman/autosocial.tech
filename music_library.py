"""Content Factory — background-music library (user-provided tracks).

Music is NOT generated. The user drops calm/ambient MP3s (e.g. from Suno) into a
persistent volume; this module imports them into a simple file-based library
(one JSON sidecar per track), lists the enabled ones, and selects a track for a
new Short with a no-repeat window. Mixing lives in music_mix.py.

No external API, no scraping, no key handling here — just local files + ffprobe.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

MUSIC_DIR = Path(os.getenv("MUSIC_LIBRARY_DIR", "/app/assets/music/calm"))
NO_REPEAT_WINDOW = int(os.getenv("MUSIC_NO_REPEAT_WINDOW", "6") or 6)
_FFPROBE = os.getenv("FFPROBE_BIN", "ffprobe")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_audio(path: Path) -> dict:
    """duration/codec/sample_rate/channels via ffprobe (empty dict on failure)."""
    try:
        proc = subprocess.run(
            [_FFPROBE, "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        info = json.loads(proc.stdout or "{}")
        a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
        if not a:
            return {}
        return {
            "duration_seconds": round(float(info.get("format", {}).get("duration") or 0.0), 2),
            "codec": a.get("codec_name"),
            "sample_rate": int(a.get("sample_rate") or 0) or None,
            "channels": int(a.get("channels") or 0) or None,
        }
    except Exception:
        return {}


def _meta_path(mp3: Path) -> Path:
    return mp3.with_suffix(".json")


def _existing_shas() -> set[str]:
    shas = set()
    for jf in MUSIC_DIR.glob("*.json"):
        try:
            shas.add(json.loads(jf.read_text(encoding="utf-8")).get("sha256"))
        except Exception:
            continue
    return {s for s in shas if s}


def import_file(mp3_path: Path) -> dict | None:
    """Import one MP3 into the library. Idempotent by SHA-256 (same content →
    imported once). Returns the metadata dict, or None if the file is unusable."""
    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        return None
    probe = probe_audio(mp3_path)
    if not probe or not probe.get("duration_seconds"):
        return None  # no audio stream / unreadable
    sha = _sha256_file(mp3_path)
    if sha in _existing_shas():
        # already imported (possibly under a different name) — skip duplicate
        for jf in MUSIC_DIR.glob("*.json"):
            try:
                m = json.loads(jf.read_text(encoding="utf-8"))
                if m.get("sha256") == sha:
                    return m
            except Exception:
                continue
        return None
    meta = {
        "id": f"suno_{sha[:12]}",
        "title": mp3_path.stem,
        "original_filename": mp3_path.name,
        "source": "Suno",
        "source_type": "user_provided",
        "commercial_use_confirmed_by_user": True,
        "content_id_safe": "unknown",  # Content ID not separately verified
        "instrumental_expected": True,
        "mood": "calm",
        "duration_seconds": probe["duration_seconds"],
        "codec": probe.get("codec"),
        "sample_rate": probe.get("sample_rate"),
        "channels": probe.get("channels"),
        "sha256": sha,
        "enabled": True,
        "imported_at": datetime.utcnow().isoformat() + "Z",
        "file_path": str(mp3_path),
        "usage_count": 0,
        "last_used_at": None,
    }
    _meta_path(mp3_path).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def import_dir(directory: Path | None = None) -> list[dict]:
    directory = Path(directory or MUSIC_DIR)
    out = []
    for mp3 in sorted(directory.glob("*.mp3")):
        m = import_file(mp3)
        if m:
            out.append(m)
    return out


def list_tracks(enabled_only: bool = True) -> list[dict]:
    tracks = []
    for jf in sorted(MUSIC_DIR.glob("*.json")):
        try:
            m = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if enabled_only and not m.get("enabled", True):
            continue
        # only surface tracks whose audio file still exists
        if not Path(m.get("file_path", "")).exists():
            continue
        m["_meta_file"] = str(jf)
        tracks.append(m)
    return tracks


def select_track(exclude_ids: list[str] | None = None) -> dict | None:
    """Pick one enabled track, avoiding the given recently-used ids while the
    library is large enough. Falls back to the least-recently-used track when
    every candidate is excluded (small library)."""
    import random

    exclude = set(exclude_ids or [])
    tracks = list_tracks(enabled_only=True)
    if not tracks:
        return None
    fresh = [t for t in tracks if t.get("id") not in exclude]
    if fresh:
        return random.choice(fresh)
    # everything is on cooldown → least-recently-used
    tracks.sort(key=lambda t: (t.get("last_used_at") or ""))
    return tracks[0]


def mark_used(track: dict) -> None:
    """Bump usage_count / last_used_at on the track's sidecar."""
    jf = track.get("_meta_file")
    if not jf or not Path(jf).exists():
        return
    try:
        m = json.loads(Path(jf).read_text(encoding="utf-8"))
        m["usage_count"] = int(m.get("usage_count") or 0) + 1
        m["last_used_at"] = datetime.utcnow().isoformat() + "Z"
        Path(jf).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
