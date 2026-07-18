"""Professional subtitle builder for vertical Shorts (1080x1920).

- splits voiceover text into readable cues (1-2 lines, <=SUBTITLE_MAX_LINE_CHARS
  per line) respecting punctuation and never leaving a short orphan word;
- timing: proportional to word lengths inside each scene's real audio duration
  (Edge TTS word boundaries are not captured by the current video/tts.py, so
  the proportional fallback is the active mechanism — honest limitation);
- renders an .ass file: bold white text, black outline + soft shadow, bottom
  third, MarginV = SUBTITLE_MARGIN_BOTTOM_PX (default 380 px from the bottom
  of a 1920 px frame, inside the YouTube Shorts safe zone 320-420);
- optional yellow highlight of the key word of each cue
  (SUBTITLE_HIGHLIGHT_KEYWORD, off by default);
- UTF-8 throughout; Cyrillic/German/English safe.
"""
import re
from pathlib import Path

from saas_settings import settings

_SENT_SPLIT = re.compile(r"(?<=[.!?…;:])\s+")
_WORD = re.compile(r"\S+")

MIN_CUE_SECONDS = 0.7
MAX_CUE_SECONDS = 5.0
ORPHAN_MIN_CHARS = 4  # a trailing line shorter than this gets merged back


def split_into_cue_texts(text: str, max_chars: int | None = None) -> list[str]:
    """Split text into cue chunks of at most 2 lines x max_chars, preferring
    sentence and clause boundaries. Returns cue texts with '\n' line breaks."""
    max_chars = max_chars or settings.SUBTITLE_MAX_LINE_CHARS
    max_cue = max_chars * 2
    text = " ".join((text or "").split())
    if not text:
        return []
    # sentence-first chunks, then pack into cue-sized pieces on word boundaries
    parts: list[str] = []
    for sent in _SENT_SPLIT.split(text):
        sent = sent.strip()
        if not sent:
            continue
        if len(sent) <= max_cue:
            parts.append(sent)
            continue
        words = sent.split()
        cur = ""
        for w in words:
            if cur and len(cur) + 1 + len(w) > max_cue:
                parts.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        if cur:
            # avoid a tiny orphan chunk
            if parts and len(cur) < ORPHAN_MIN_CHARS + 3:
                parts[-1] = f"{parts[-1]} {cur}"
            else:
                parts.append(cur)
    # merge very short neighbours
    merged: list[str] = []
    for p in parts:
        if merged and len(p) <= max_chars // 2 and len(merged[-1]) + len(p) + 1 <= max_cue:
            merged[-1] = f"{merged[-1]} {p}"
        else:
            merged.append(p)
    return [_wrap_two_lines(p, max_chars) for p in merged]


def _wrap_two_lines(chunk: str, max_chars: int) -> str:
    """Wrap a cue into 1-2 balanced lines; never orphan a short last word."""
    if len(chunk) <= max_chars:
        return chunk
    words = chunk.split()
    best, best_diff = None, 10**9
    for i in range(1, len(words)):
        l1 = " ".join(words[:i])
        l2 = " ".join(words[i:])
        if len(l1) > max_chars or len(l2) > max_chars:
            continue
        if len(l2) < ORPHAN_MIN_CHARS:  # no lonely short word on line 2
            continue
        diff = abs(len(l1) - len(l2))
        if diff < best_diff:
            best, best_diff = (l1, l2), diff
    if best:
        return f"{best[0]}\n{best[1]}"
    # cannot fit nicely -> shrink by splitting at max width (renderer scales)
    mid = len(words) // 2
    return " ".join(words[:mid]) + "\n" + " ".join(words[mid:])


def build_cues(scenes: list[dict]) -> list[dict]:
    """scenes: [{"text": str, "start": float, "duration": float}].
    Returns cues [{"start","end","text"}] with word-length-proportional timing
    inside each scene."""
    cues = []
    for scene in scenes:
        text = (scene.get("text") or "").strip()
        dur = float(scene.get("duration") or 0.0)
        start = float(scene.get("start") or 0.0)
        if not text or dur <= 0:
            continue
        chunk_texts = split_into_cue_texts(text)
        if not chunk_texts:
            continue
        weights = [max(1, len(re.sub(r"\s", "", c))) for c in chunk_texts]
        total_w = sum(weights)
        cursor = start
        for c, w in zip(chunk_texts, weights):
            cdur = dur * w / total_w
            cdur = max(MIN_CUE_SECONDS, min(MAX_CUE_SECONDS, cdur))
            end = min(start + dur, cursor + cdur)
            if end - cursor < 0.3:
                end = min(start + dur, cursor + 0.3)
            cues.append({"start": round(cursor, 2), "end": round(end - 0.05, 2), "text": c})
            cursor = end
    return [c for c in cues if c["end"] > c["start"]]


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_escape(text: str) -> str:
    """Neutralize characters with special meaning in ASS dialogue text.
    Braces open override blocks and backslash starts control codes; there is
    no in-band escape, so map them to safe lookalikes."""
    return text.replace("\\", "/").replace("{", "(").replace("}", ")")


def _highlight_keyword(line: str) -> str:
    """Wrap the longest word in ASS yellow. Optional feature."""
    words = line.split(" ")
    if not words:
        return line
    idx = max(range(len(words)), key=lambda i: len(re.sub(r"\W", "", words[i])))
    words[idx] = r"{\c&H00FFFF&}" + words[idx] + r"{\c&HFFFFFF&}"
    return " ".join(words)


def write_ass(cues: list[dict], out_path: Path, *, highlight: bool | None = None,
              font_size: int = 64) -> Path:
    """1080x1920 ASS with bottom-third placement inside the Shorts safe zone."""
    highlight = settings.SUBTITLE_HIGHLIGHT_KEYWORD if highlight is None else highlight
    margin_v = settings.SUBTITLE_MARGIN_BOTTOM_PX
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Shorts,{settings.SUBTITLE_FONT_NAME},{font_size},&H00FFFFFF,&H00FFFFFF,&H00111111,&H8C000000,-1,0,0,0,100,100,0,0,1,3,1,2,84,84,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # usable width between L/R margins; ~0.52*font_size per bold Cyrillic char
    usable_px = 1080 - 2 * 84
    char_w = 0.52
    lines = []
    for c in cues:
        text = _ass_escape(c["text"])
        if highlight:
            text = "\n".join(_highlight_keyword(l) for l in text.split("\n"))
        # auto-shrink any line that would overflow the safe width (no clipping)
        widest = max((len(l) for l in text.split("\n")), default=1)
        fit_fs = int(usable_px / (char_w * max(1, widest)))
        fs_tag = ""
        if fit_fs < font_size:
            fs_tag = rf"{{\fs{max(40, fit_fs)}}}"
        ass_text = fs_tag + text.replace("\n", r"\N")
        lines.append(f"Dialogue: 0,{_ass_time(c['start'])},{_ass_time(c['end'])},Shorts,,0,0,0,,{ass_text}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out_path
