import os
import subprocess
from pathlib import Path

from openai import OpenAI

from config import Config
from saas_settings import settings


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command_failed: {' '.join(cmd[:3])}: {(proc.stderr or proc.stdout)[:800]}")


def probe_duration(path: str) -> float:
    proc = subprocess.run(
        [settings.FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return 0.0
    try:
        return float((proc.stdout or "0").strip() or 0.0)
    except Exception:
        return 0.0


def _tts_phrase_openai(text: str, out_path: Path) -> None:
    key = (os.getenv("OPENAI_API_KEY") or Config.OPENAI_API_KEY or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured for TTS")
    client = OpenAI(api_key=key, timeout=120)
    with client.audio.speech.with_streaming_response.create(
        model=settings.OPENAI_TTS_MODEL,
        voice=settings.OPENAI_TTS_VOICE,
        input=text,
        format="mp3",
    ) as response:
        response.stream_to_file(str(out_path))


def _tts_phrase_fallback(text: str, out_path: Path) -> None:
    seconds = max(1.2, min(9.0, len(text) / 18.0))
    _run(
        [
            settings.FFMPEG_BIN,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=mono:sample_rate=44100",
            "-t",
            str(seconds),
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            str(out_path),
        ]
    )


def synthesize_voiceover(phrases: list[str], out_dir: Path, prefix: str) -> tuple[str, list[float]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    phrase_files: list[Path] = []
    durations: list[float] = []
    for idx, phrase in enumerate(phrases):
        line = str(phrase or "").strip()
        if not line:
            line = " "
        p = out_dir / f"{prefix}_phrase_{idx:03d}.mp3"
        try:
            _tts_phrase_openai(line, p)
        except Exception:
            _tts_phrase_fallback(line, p)
        d = probe_duration(str(p))
        durations.append(max(0.2, d))
        phrase_files.append(p)

    concat_list = out_dir / f"{prefix}_concat.txt"
    concat_list.write_text(
        "\n".join([f"file '{x.as_posix()}'" for x in phrase_files]),
        encoding="utf-8",
    )
    final_audio = out_dir / f"{prefix}_voiceover.mp3"
    _run(
        [
            settings.FFMPEG_BIN,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            str(final_audio),
        ]
    )
    return str(final_audio), durations
