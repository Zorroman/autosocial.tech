import json
import os
import subprocess
import asyncio
from pathlib import Path

from openai import OpenAI
import edge_tts

from config import Config
from app_settings import settings


_VOICE_BY_PROFILE = {
    "male": {
        "calm": "echo",
        "neutral": "onyx",
        "live": "fable",
    },
    "female": {
        "calm": "nova",
        "neutral": "alloy",
        "live": "shimmer",
    },
}

_EDGE_VOICE_BY_PROFILE = {
    "male": {
        "calm": "ru-RU-DmitryNeural",
        "neutral": "ru-RU-DmitryNeural",
        "live": "ru-RU-DmitryNeural",
    },
    "female": {
        "calm": "ru-RU-SvetlanaNeural",
        "neutral": "ru-RU-SvetlanaNeural",
        "live": "ru-RU-SvetlanaNeural",
    },
}


def _primary_tts_provider() -> str:
    raw = str(os.getenv("VIDEO_TTS_PRIMARY") or "").strip().lower()
    if raw in {"edge", "openai"}:
        return raw
    # Default to edge neural voices: they sound more natural for RU voiceover.
    return "edge"


def _normalize_voice_profile(voice_gender: str | None, voice_tone: str | None) -> tuple[str, str]:
    gender = str(voice_gender or "male").strip().lower()
    if gender not in {"male", "female"}:
        gender = "male"
    tone = str(voice_tone or "neutral").strip().lower()
    if tone not in {"calm", "neutral", "live"}:
        tone = "neutral"
    return gender, tone


def _resolve_openai_voice(voice_gender: str | None, voice_tone: str | None, voice_name: str | None = None) -> str:
    explicit = str(voice_name or "").strip()
    if explicit:
        return explicit
    gender, tone = _normalize_voice_profile(voice_gender, voice_tone)
    mapped = _VOICE_BY_PROFILE.get(gender, {}).get(tone)
    return str(mapped or settings.OPENAI_TTS_VOICE or "alloy")


def _resolve_edge_voice(voice_gender: str | None, voice_tone: str | None, voice_name: str | None = None) -> str:
    explicit = str(voice_name or "").strip()
    if explicit and "neural" in explicit.lower():
        return explicit
    gender, tone = _normalize_voice_profile(voice_gender, voice_tone)
    return str(_EDGE_VOICE_BY_PROFILE.get(gender, {}).get(tone) or "ru-RU-DmitryNeural")


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




def _speech_speed_factor(raw: str | float | int | None) -> float:
    key = str(raw or "normal").strip().lower()
    mapping = {"slow": 0.92, "normal": 1.0, "fast": 1.10}
    if key in mapping:
        return mapping[key]
    try:
        return max(0.85, min(1.15, float(key)))
    except Exception:
        return 1.0

def _atempo_chain(speed_factor: float) -> str:
    factor = max(0.5, float(speed_factor))
    parts: list[str] = []
    while factor > 2.0:
        parts.append("atempo=2.0")
        factor /= 2.0
    while factor < 0.5:
        parts.append("atempo=0.5")
        factor /= 0.5
    parts.append(f"atempo={factor:.6f}")
    return ",".join(parts)


# Valid OpenAI TTS voices — an unknown name (e.g. "eddy") makes the API 400,
# which is why every request fell back to the robotic offline engine.
_OPENAI_TTS_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "fable",
                      "onyx", "nova", "sage", "shimmer", "verse"}


def _tts_phrase_openai(
    text: str,
    out_path: Path,
    *,
    voice_name: str | None = None,
    voice_gender: str | None = None,
    voice_tone: str | None = None,
    instructions: str | None = None,
) -> None:
    key = (os.getenv("OPENAI_API_KEY") or Config.OPENAI_API_KEY or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured for TTS")
    client = OpenAI(api_key=key, timeout=120)
    selected_voice = _resolve_openai_voice(voice_gender=voice_gender, voice_tone=voice_tone, voice_name=voice_name)
    fallback_voice = str(settings.OPENAI_TTS_VOICE or "alloy")
    # keep only voices the API accepts; guarantee a valid default last.
    candidates = [v for v in (selected_voice, fallback_voice) if v in _OPENAI_TTS_VOICES]
    candidates.append("onyx")
    err: Exception | None = None
    for voice_try in dict.fromkeys(candidates):  # dedupe, keep order
        try:
            kwargs = dict(model=settings.OPENAI_TTS_MODEL, voice=voice_try,
                          input=text, response_format="mp3")
            if instructions and "gpt-4o-mini-tts" in (settings.OPENAI_TTS_MODEL or ""):
                kwargs["instructions"] = instructions
            with client.audio.speech.with_streaming_response.create(**kwargs) as response:
                response.stream_to_file(str(out_path))
            return
        except Exception as exc:
            err = exc
            continue
    if err:
        raise err


def _tts_phrase_edge(
    text: str,
    out_path: Path,
    *,
    voice_name: str | None = None,
    voice_gender: str | None = None,
    voice_tone: str | None = None,
) -> None:
    phrase = " ".join(str(text or "").split()).strip()
    if not phrase:
        phrase = "Контент готов."
    voice = _resolve_edge_voice(voice_gender=voice_gender, voice_tone=voice_tone, voice_name=voice_name)
    tone = str(voice_tone or "neutral").strip().lower()
    rate = "+0%" if tone == "neutral" else ("-1%" if tone == "calm" else "+7%")
    pitch = "+0Hz" if tone == "neutral" else ("-1Hz" if tone == "calm" else "+2Hz")

    async def _synth() -> None:
        communicate = edge_tts.Communicate(text=phrase, voice=voice, rate=rate, pitch=pitch)
        await communicate.save(str(out_path))

    asyncio.run(_synth())


class TTSProviderUnavailableError(RuntimeError):
    """Raised when no TTS provider can produce audio for a video. No silent
    fallback, no flite (not installed / not verified in production) -- the
    caller must surface this as a blocked state, not a video with dead air."""


# Per-phrase retries of the SAME provider before it's considered failed for
# this video. A single transient hiccup shouldn't switch providers (that's
# what caused inconsistent voices within one video); a provider that's
# genuinely down should fail fast rather than retry forever.
_MAX_PHRASE_RETRIES = 2


def _synthesize_one_phrase(provider: str, text: str, out_path: Path, *,
                           voice_name, voice_gender, voice_tone, instructions) -> None:
    if provider == "edge":
        _tts_phrase_edge(text, out_path, voice_name=voice_name,
                         voice_gender=voice_gender, voice_tone=voice_tone)
    else:
        _tts_phrase_openai(text, out_path, voice_name=voice_name, voice_gender=voice_gender,
                           voice_tone=voice_tone, instructions=instructions)


def _synthesize_all_with_provider(
    provider: str, lines: list[str], out_dir: Path, prefix: str, *,
    voice_name, voice_gender, voice_tone, instructions,
) -> list[Path]:
    """Synthesize every phrase with ONE provider, retrying the same provider
    on a transient per-phrase failure. Raises TTSProviderUnavailableError
    (and does not leave partial output for the caller to accidentally mix
    with another provider's files) if this provider can't complete the
    whole video."""
    paths: list[Path] = []
    for idx, line in enumerate(lines):
        p = out_dir / f"{prefix}_phrase_{idx:03d}.mp3"
        last_exc: Exception | None = None
        for _attempt in range(_MAX_PHRASE_RETRIES):
            try:
                _synthesize_one_phrase(provider, line, p, voice_name=voice_name,
                                       voice_gender=voice_gender, voice_tone=voice_tone,
                                       instructions=instructions)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
        if last_exc is not None:
            raise TTSProviderUnavailableError(
                f"{provider} failed on phrase {idx} after {_MAX_PHRASE_RETRIES} attempts: {last_exc}"
            )
        paths.append(p)
    return paths


def synthesize_voiceover(
    phrases: list[str],
    out_dir: Path,
    prefix: str,
    *,
    min_phrase_seconds: float | None = None,
    target_total_seconds: float | None = None,
    voice_gender: str | None = None,
    voice_tone: str | None = None,
    voice_name: str | None = None,
    speech_speed: str | float | int | None = None,
    gap_before: list[float] | None = None,
    instructions: str | None = None,
) -> tuple[str, list[float]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [str(phrase or "").strip() or " " for phrase in phrases]

    # Provider chosen ONCE for the whole video, not per phrase -- a single
    # transient failure on one phrase must never leave that one phrase in a
    # different voice than the rest. See TTSProviderUnavailableError.
    primary = _primary_tts_provider()
    # A tone `instructions` block is an OpenAI gpt-4o-mini-tts feature — when
    # supplied (long-form), prefer OpenAI for its warmer, controllable voice.
    order = ("openai", "edge") if instructions else (
        ("edge", "openai") if primary == "edge" else ("openai", "edge"))

    used_provider = order[0]
    switched_to_fallback = False
    try:
        phrase_paths = _synthesize_all_with_provider(
            order[0], lines, out_dir, prefix, voice_name=voice_name,
            voice_gender=voice_gender, voice_tone=voice_tone, instructions=instructions)
    except TTSProviderUnavailableError as exc1:
        try:
            phrase_paths = _synthesize_all_with_provider(
                order[1], lines, out_dir, prefix, voice_name=voice_name,
                voice_gender=voice_gender, voice_tone=voice_tone, instructions=instructions)
            used_provider = order[1]
            switched_to_fallback = True
        except TTSProviderUnavailableError as exc2:
            raise TTSProviderUnavailableError(
                f"both TTS providers unavailable ({order[0]}: {exc1}; {order[1]}: {exc2})"
            ) from exc2

    used_voice = (_resolve_edge_voice(voice_gender, voice_tone, voice_name) if used_provider == "edge"
                 else _resolve_openai_voice(voice_gender, voice_tone, voice_name))

    phrase_files: list[Path] = []
    durations: list[float] = []
    has_gap = False
    tts_log: list[dict] = []
    for idx, p in enumerate(phrase_paths):
        gap = 0.0
        if gap_before and idx < len(gap_before):
            try:
                gap = max(0.0, float(gap_before[idx]))
            except Exception:
                gap = 0.0
        if gap > 0:
            sil = out_dir / f"{prefix}_gap_{idx:03d}.mp3"
            _run([settings.FFMPEG_BIN, "-y", "-f", "lavfi",
                  "-i", f"anullsrc=r=44100:cl=mono:d={gap:.3f}",
                  "-c:a", "libmp3lame", "-q:a", "4", str(sil)])
            phrase_files.append(sil)
            has_gap = True
        d = probe_duration(str(p))
        d = max(0.2, d)
        if min_phrase_seconds is not None:
            d = max(d, float(min_phrase_seconds))
        durations.append(d + gap)  # the pause belongs to this phrase's slot
        phrase_files.append(p)
        tts_log.append({
            "phrase_index": idx,
            "text_start": lines[idx][:60],
            "provider": used_provider,
            "voice": used_voice,
            "duration": round(d, 2),
            "fallback_reason": ("primary provider unavailable, whole video switched to fallback"
                               if switched_to_fallback else None),
        })
    (out_dir / f"{prefix}_tts_log.json").write_text(
        json.dumps(tts_log, ensure_ascii=False, indent=1), encoding="utf-8")

    concat_list = out_dir / f"{prefix}_concat.txt"
    concat_list.write_text(
        "\n".join([f"file '{x.as_posix()}'" for x in phrase_files]),
        encoding="utf-8",
    )
    final_audio = out_dir / f"{prefix}_voiceover.mp3"
    # Copy-concat when all segments share codec params; re-encode when we inserted
    # silence gaps (mixed params) so the concat is always clean.
    codec_args = ["-c:a", "libmp3lame", "-q:a", "2"] if has_gap else ["-c", "copy"]
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
            *codec_args,
            str(final_audio),
        ]
    )
    speed_factor = _speech_speed_factor(speech_speed)
    if abs(speed_factor - 1.0) > 0.01:
        speed_audio = out_dir / f"{prefix}_voiceover_speed.mp3"
        _run(
            [
                settings.FFMPEG_BIN,
                "-y",
                "-i",
                str(final_audio),
                "-filter:a",
                _atempo_chain(speed_factor),
                "-q:a",
                "2",
                str(speed_audio),
            ]
        )
        final_audio = speed_audio
        durations = [max(0.2, float(d) / speed_factor) for d in durations]
    if target_total_seconds is not None:
        target_total = max(1.0, float(target_total_seconds))
        actual_total = probe_duration(str(final_audio))
        if actual_total > target_total + 0.05:
            # Speed up voiceover proportionally to fit the selected video duration.
            speedup = max(1.0, actual_total / max(0.1, target_total))
            adjusted_audio = out_dir / f"{prefix}_voiceover_fit.mp3"
            _run(
                [
                    settings.FFMPEG_BIN,
                    "-y",
                    "-i",
                    str(final_audio),
                    "-filter:a",
                    _atempo_chain(speedup),
                    "-t",
                    str(round(target_total, 3)),
                    "-q:a",
                    "2",
                    str(adjusted_audio),
                ]
            )
            final_audio = adjusted_audio
            scale = target_total / max(0.1, actual_total)
            durations = [max(0.2, float(d) * scale) for d in durations]
        elif actual_total + 0.05 < target_total:
            padded_audio = out_dir / f"{prefix}_voiceover_pad_target.mp3"
            _run(
                [
                    settings.FFMPEG_BIN,
                    "-y",
                    "-i",
                    str(final_audio),
                    "-af",
                    "apad",
                    "-t",
                    str(round(target_total, 3)),
                    "-q:a",
                    "2",
                    str(padded_audio),
                ]
            )
            final_audio = padded_audio
    if min_phrase_seconds is not None:
        target_total = max(0.0, float(min_phrase_seconds) * max(1, len(phrases)))
        actual_total = probe_duration(str(final_audio))
        if target_total > 0 and actual_total + 0.05 < target_total:
            padded_audio = out_dir / f"{prefix}_voiceover_padded.mp3"
            _run(
                [
                    settings.FFMPEG_BIN,
                    "-y",
                    "-i",
                    str(final_audio),
                    "-af",
                    "apad",
                    "-t",
                    str(round(target_total, 3)),
                    "-q:a",
                    "2",
                    str(padded_audio),
                ]
            )
            final_audio = padded_audio
    return str(final_audio), durations
