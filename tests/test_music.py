"""Background-music library + mix tests.

Uses ffmpeg to synthesise tiny audio/video so the mix path is exercised for
real (no network, no external API). Skips cleanly where ffmpeg is unavailable.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

pytestmark = pytest.mark.skipif(
    not (Path(FFMPEG).exists() and Path(FFPROBE).exists()),
    reason="ffmpeg/ffprobe not available",
)


def _mk_tone_mp3(path: Path, seconds: float, freq: int):
    subprocess.run([FFMPEG, "-y", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:duration={seconds}",
                    "-c:a", "libmp3lame", "-q:a", "5", str(path)],
                   capture_output=True, check=True)


def _mk_video_with_voice(path: Path, seconds: float):
    subprocess.run([FFMPEG, "-y",
                    "-f", "lavfi", "-i", f"color=c=black:s=320x568:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)],
                   capture_output=True, check=True)


def _probe(path):
    p = subprocess.run([FFPROBE, "-v", "quiet", "-print_format", "json",
                        "-show_streams", "-show_format", str(path)],
                       capture_output=True, text=True)
    return json.loads(p.stdout or "{}")


@pytest.fixture()
def lib(tmp_path, monkeypatch):
    import music_library as ml
    d = tmp_path / "calm"
    d.mkdir()
    monkeypatch.setattr(ml, "MUSIC_DIR", d)
    monkeypatch.setattr(ml, "_FFPROBE", FFPROBE)
    return ml, d


# ---- library: import / dedup / metadata -----------------------------------

def test_import_creates_metadata_and_hash(lib):
    ml, d = lib
    _mk_tone_mp3(d / "Calm One.mp3", 40, 300)
    metas = ml.import_dir(d)
    assert len(metas) == 1
    m = metas[0]
    assert m["source_type"] == "user_provided" and m["source"] == "Suno"
    assert m["content_id_safe"] == "unknown"          # not claimed verified
    assert m["instrumental_expected"] is True
    assert len(m["sha256"]) == 64 and m["duration_seconds"] >= 30
    assert m["enabled"] is True and m["usage_count"] == 0
    assert (d / "Calm One.json").exists()


def test_dedup_same_content_imported_once(lib):
    ml, d = lib
    _mk_tone_mp3(d / "A.mp3", 40, 300)
    shutil.copyfile(d / "A.mp3", d / "A copy.mp3")   # identical bytes → same sha
    metas = ml.import_dir(d)
    # two files, one unique sha → exactly one new metadata sidecar written
    shas = {m["sha256"] for m in metas}
    assert len(shas) == 1


def test_different_content_kept_separately(lib):
    ml, d = lib
    _mk_tone_mp3(d / "A.mp3", 40, 300)
    _mk_tone_mp3(d / "B.mp3", 40, 500)   # different freq → different bytes
    ml.import_dir(d)
    assert len(ml.list_tracks()) == 2


# ---- selection: no-repeat window ------------------------------------------

def test_select_excludes_recent(lib):
    ml, d = lib
    for i, fr in enumerate((300, 400, 500)):
        _mk_tone_mp3(d / f"T{i}.mp3", 40, fr)
    ml.import_dir(d)
    ids = [t["id"] for t in ml.list_tracks()]
    chosen = ml.select_track(exclude_ids=ids[:2])
    assert chosen["id"] == ids[2]          # only the non-excluded one


def test_select_falls_back_when_all_excluded(lib):
    ml, d = lib
    _mk_tone_mp3(d / "Only.mp3", 40, 300)
    ml.import_dir(d)
    ids = [t["id"] for t in ml.list_tracks()]
    chosen = ml.select_track(exclude_ids=ids)   # everything on cooldown
    assert chosen is not None and chosen["id"] == ids[0]


# ---- mix: real ffmpeg ducking + verification ------------------------------

class _Proj:
    def __init__(self):
        self.channel_id = 1
        for f in ("music_track_id", "music_title", "music_provider",
                  "music_start_seconds", "music_end_seconds", "music_gain_db",
                  "music_status", "music_mix_version"):
            setattr(self, f, None)


def test_mix_adds_quiet_bed_and_preserves_duration(tmp_path, monkeypatch):
    import music_library as ml
    import music_mix as mx
    d = tmp_path / "calm"; d.mkdir()
    monkeypatch.setattr(ml, "MUSIC_DIR", d)
    monkeypatch.setattr(ml, "_FFPROBE", FFPROBE)
    monkeypatch.setattr(mx, "_FFMPEG", FFMPEG)
    monkeypatch.setattr(mx, "_FFPROBE", FFPROBE)
    monkeypatch.setattr(mx, "recent_track_ids", lambda *a, **k: [])
    _mk_tone_mp3(d / "Bed.mp3", 60, 330)
    ml.import_dir(d)

    video = tmp_path / "vid.mp4"
    _mk_video_with_voice(video, 6.0)
    before = float(_probe(video)["format"]["duration"])

    res = mx.add_music_bed(_Proj(), video, db=None)
    assert res["music_status"] == "mixed"
    info = _probe(video)
    dur = float(info["format"]["duration"])
    assert abs(dur - before) <= 1.0                       # duration preserved
    assert any(s["codec_type"] == "audio" for s in info["streams"])  # has audio


def test_broken_music_falls_back_to_no_music(tmp_path, monkeypatch):
    import music_library as ml
    import music_mix as mx
    d = tmp_path / "calm"; d.mkdir()
    monkeypatch.setattr(ml, "MUSIC_DIR", d)
    monkeypatch.setattr(mx, "_FFMPEG", FFMPEG)
    monkeypatch.setattr(mx, "_FFPROBE", FFPROBE)
    monkeypatch.setattr(mx, "recent_track_ids", lambda *a, **k: [])
    # a bogus "track" whose file is not real audio
    bad = d / "bad.mp3"; bad.write_bytes(b"not audio")
    monkeypatch.setattr(ml, "select_track",
                        lambda exclude_ids=None: {"id": "x", "title": "bad",
                                                  "file_path": str(bad),
                                                  "duration_seconds": 60, "source": "Suno"})
    monkeypatch.setattr(mx, "music_library", ml)

    video = tmp_path / "vid.mp4"
    _mk_video_with_voice(video, 6.0)
    res = mx.add_music_bed(_Proj(), video, db=None)
    assert res["music_status"] == "no_music"      # fallback: video kept intact
    assert any(s["codec_type"] == "audio" for s in _probe(video)["streams"])
