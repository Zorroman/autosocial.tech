"""Technical render test: produces a real 1080x1920 MP4 through the production
render_video() path using locally generated fixtures (no external providers).

Run: python -m pytest tests/test_render_fixture.py -q
"""
import json
import subprocess
from pathlib import Path

import pytest

from saas_settings import settings
from video.render.render_video import render_video

FIXTURES = Path(__file__).parent / "render_fixtures"


def _ffmpeg(*args):
    subprocess.run([settings.FFMPEG_BIN, "-y", *args], check=True, capture_output=True)


@pytest.fixture(scope="module")
def fixtures():
    FIXTURES.mkdir(exist_ok=True)
    clips = []
    for i, color in enumerate(["0x1a1a2e", "0x16213e", "0x0f3460"]):
        p = FIXTURES / f"clip{i}.mp4"
        if not p.exists():
            _ffmpeg("-f", "lavfi", "-i", f"color=c={color}:s=640x1136:d=4:r=30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p))
        clips.append(p)
    voice = FIXTURES / "voice.wav"
    if not voice.exists():
        _ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=9", "-ar", "44100", str(voice))
    srt = FIXTURES / "subs.srt"
    srt.write_text(
        "1\n00:00:00,200 --> 00:00:02,800\nЗнаки и символы\n\n"
        "2\n00:00:03,000 --> 00:00:05,800\nИстория мистических традиций\n\n"
        "3\n00:00:06,000 --> 00:00:08,800\nСмотрите до конца\n",
        encoding="utf-8",
    )
    return {"clips": clips, "voice": voice, "srt": srt}


def test_render_produces_valid_short(fixtures, tmp_path):
    out = tmp_path / "test_short.mp4"
    render_video(
        clips=[{"clip_path": str(c), "duration_target": 3.0} for c in fixtures["clips"]],
        voiceover_path=str(fixtures["voice"]),
        subtitles_path=str(fixtures["srt"]),
        out_path=str(out),
        orientation="vertical",
        fps=30,
        resolution="1080x1920",
    )
    assert out.exists() and out.stat().st_size > 50_000

    probe = subprocess.run(
        [settings.FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(out)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(probe.stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert v["codec_name"] == "h264"
    assert (v["width"], v["height"]) == (1080, 1920)
    assert v["pix_fmt"] == "yuv420p"
    assert a["codec_name"] == "aac"
    duration = float(info["format"]["duration"])
    assert 7.0 <= duration <= 10.0
