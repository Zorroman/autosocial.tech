"""Technical render test: produces a real 1080x1920 MP4 through the production
render_video() path using locally generated fixtures (no external providers).

Run: python -m pytest tests/test_render_fixture.py -q
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app_settings import settings
from video.render.render_video import _run, render_video

# video/render/__init__.py does `from .render_video import render_video`,
# which shadows the render_video submodule's own name in the package
# namespace with the function -- fetch the real submodule via sys.modules.
render_video_module = sys.modules["video.render.render_video"]

FIXTURES = Path(__file__).parent / "render_fixtures"


def test_run_reports_the_actual_ffmpeg_error_not_the_version_banner(monkeypatch):
    """ffmpeg always opens stderr with its version/build-configuration banner
    (regularly >1200 chars on its own) before any real error line -- a head
    slice of stderr can never surface the actual failure reason. Regression
    test for a bug where every render failure's stored error was just this
    banner, making every real ffmpeg error undiagnosable in production."""
    banner = "ffmpeg version 7.1.5 ...\n" + ("configuration: --enable-x\n" * 100)
    real_error = "Unknown encoder 'libx264'"
    fake_stderr = banner + real_error

    class _Proc:
        returncode = 1
        stderr = fake_stderr
        stdout = ""

    monkeypatch.setattr(render_video_module.subprocess, "run", lambda *a, **kw: _Proc())
    with pytest.raises(RuntimeError) as exc_info:
        _run(["ffmpeg", "-y"])
    assert real_error in str(exc_info.value)


def _ffmpeg(*args):
    subprocess.run([settings.FFMPEG_BIN, "-y", *args], check=True, capture_output=True)


def test_short_final_encode_bounds_ffmpeg_parallelism(monkeypatch, tmp_path):
    calls = []

    def _capture(cmd):
        calls.append(cmd)

    monkeypatch.setattr(render_video_module, "_run", _capture)

    source = tmp_path / "source.mp4"
    voice = tmp_path / "voice.mp3"
    subs = tmp_path / "subs.ass"
    source.write_bytes(b"not executed")
    voice.write_bytes(b"not executed")
    subs.write_text("[Script Info]\n", encoding="utf-8")

    out = tmp_path / "out.mp4"
    render_video(
        clips=[{"clip_path": str(source), "duration_target": 3.0}],
        voiceover_path=str(voice),
        subtitles_path=str(subs),
        out_path=str(out),
        orientation="vertical",
        fps=30,
        resolution="1080x1920",
    )

    final_cmd = calls[-1]
    assert final_cmd[:2] == [settings.FFMPEG_BIN, "-y"]
    assert final_cmd[final_cmd.index("-filter_threads") + 1] == "1"
    assert final_cmd[final_cmd.index("-filter_complex_threads") + 1] == "1"
    assert final_cmd.index("-filter_threads") < final_cmd.index("-filter_complex")
    assert final_cmd.index("-filter_complex_threads") < final_cmd.index("-filter_complex")
    assert final_cmd[final_cmd.index("-threads") + 1] == "1"
    assert final_cmd.index("-c:v") < final_cmd.index("-threads") < final_cmd.index("-preset")
    assert final_cmd[final_cmd.index("-c:v") + 1] == "libx264"
    assert final_cmd[final_cmd.index("-preset") + 1] == "veryfast"
    assert final_cmd[final_cmd.index("-crf") + 1] == "22"
    assert final_cmd[final_cmd.index("-c:a") + 1] == "aac"
    assert final_cmd[final_cmd.index("-r") + 1] == "30"
    assert final_cmd[final_cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert "subtitles='" in final_cmd[final_cmd.index("-filter_complex") + 1]
    assert final_cmd[-1] == str(out)


def test_long_form_final_encode_keeps_existing_thread_defaults(monkeypatch, tmp_path):
    calls = []

    def _capture(cmd):
        calls.append(cmd)

    monkeypatch.setattr(render_video_module, "_run", _capture)

    source = tmp_path / "source.mp4"
    voice = tmp_path / "voice.mp3"
    source.write_bytes(b"not executed")
    voice.write_bytes(b"not executed")

    render_video(
        clips=[{"clip_path": str(source), "duration_target": 61.0}],
        voiceover_path=str(voice),
        subtitles_path=None,
        out_path=str(tmp_path / "out.mp4"),
        orientation="horizontal",
        fps=30,
        resolution="1920x1080",
    )

    final_cmd = calls[-1]
    assert "-threads" not in final_cmd
    assert "-filter_threads" not in final_cmd
    assert "-filter_complex_threads" not in final_cmd
    assert final_cmd[final_cmd.index("-preset") + 1] == "fast"


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
