from pathlib import Path
import re
import textwrap


def _format_ass_time(seconds: float) -> str:
    total = max(0.0, float(seconds))
    h = int(total // 3600)
    total -= h * 3600
    m = int(total // 60)
    total -= m * 60
    s = int(total)
    cs = int(round((total - s) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _phrase_words_karaoke(phrase: str, duration_sec: float, reveal_mode: str) -> str:
    text = str(phrase or "").strip()
    if not text:
        return ""
    mode = str(reveal_mode or "").strip().lower()
    if mode not in {"word", "letter"}:
        return text
    # Preserve manual line breaks (\N) so wrapping stays inside frame bounds.
    rows = text.split("\\N")
    chunks: list[list[str]] = []
    total_units = 0
    for row in rows:
        if mode == "letter":
            parts = list(row)
        else:
            parts = row.split()
        if not parts:
            parts = [""]
        chunks.append(parts)
        total_units += len(parts)
    if total_units <= 0:
        return text
    unit_centis = max(1, int((duration_sec * 100) / total_units))
    rendered_rows: list[str] = []
    for parts in chunks:
        if mode == "letter":
            rendered_rows.append("".join([f"{{\\k{unit_centis}}}{ch}" for ch in parts]))
        else:
            rendered_rows.append(" ".join([f"{{\\k{unit_centis}}}{w}" for w in parts]))
    return "\\N".join(rendered_rows)


def _strip_ass_overrides(text: str) -> str:
    value = str(text or "")
    # Remove any embedded ASS override blocks like {\k20}, {\fs48}, etc.
    value = re.sub(r"\{\\[^}]*\}", "", value)
    # Remove any remaining raw braces to avoid accidental ASS parsing.
    value = value.replace("{", "").replace("}", "")
    return value


def _chunk_long_token(token: str, chunk_size: int) -> list[str]:
    token = str(token or "")
    if len(token) <= chunk_size:
        return [token]
    return [token[i : i + chunk_size] for i in range(0, len(token), chunk_size)]


def _wrap_for_subtitles(text: str, max_chars: int = 34, max_lines: int = 3) -> str:
    clean = " ".join(str(text or "").split()).strip()
    if not clean:
        return ""
    width = max(6, int(max_chars))
    lines: list[str] = []
    # First pass: wrap while allowing hard split of overlong tokens.
    raw = textwrap.wrap(clean, width=width, break_long_words=True, break_on_hyphens=False)
    for line in raw:
        # Guard against rare extremely long "word" fragments.
        parts = re.split(r"(\s+)", line)
        rebuilt: list[str] = []
        for part in parts:
            if not part or part.isspace():
                rebuilt.append(part)
                continue
            if len(part) > width:
                rebuilt.append(" ".join(_chunk_long_token(part, width)))
            else:
                rebuilt.append(part)
        normalized = "".join(rebuilt).strip()
        if normalized:
            lines.extend(
                textwrap.wrap(normalized, width=width, break_long_words=True, break_on_hyphens=False) or [normalized]
            )
    if not lines:
        return ""
    # Keep subtitles inside safe area and only use ellipsis when we really dropped content.
    max_lines_int = max(1, int(max_lines))
    had_overflow = len(lines) > max_lines_int
    lines = lines[:max_lines_int]
    width = max(6, int(max_chars))
    if lines and had_overflow:
        lines[-1] = lines[-1][:width].rstrip()
        if len(lines[-1]) >= width - 1:
            lines[-1] = f"{lines[-1][:max(1, width - 3)].rstrip()}..."
    return "\\N".join(lines)


def load_subtitle_lines(lecture_txt_path: Path | None, fallback_phrases: list[str]) -> list[str]:
    if lecture_txt_path and lecture_txt_path.exists():
        lines = [x.strip() for x in lecture_txt_path.read_text(encoding="utf-8").splitlines() if x.strip()]
        if lines:
            return lines
    return [str(x).strip() for x in fallback_phrases if str(x).strip()]


def build_ass_subtitles(
    lines: list[str],
    phrase_durations: list[float],
    out_path: Path,
    *,
    reveal_mode: str = "word",
    font_name: str = "Arial",
    font_size: int = 38,
    max_chars: int = 34,
    max_lines: int = 3,
    margin_lr: int = 72,
    margin_v: int = 120,
    frame_width: int | None = None,
    frame_height: int | None = None,
) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    is_vertical = bool(frame_width and frame_height and int(frame_height) > int(frame_width))
    mode = str(reveal_mode or "word").strip().lower()
    # Hard safety: disable karaoke for vertical videos to prevent overflow/highlight artifacts.
    if is_vertical:
        mode = "plain"
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        f"PlayResX: {int(frame_width or 1920)}\n"
        f"PlayResY: {int(frame_height or 1080)}\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.601\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,"
        "MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Default,{font_name},{font_size},&H00FFFFFF,&H00FFFFFF,&H00202020,&H64000000,1,0,0,0,100,100,0,0,1,2,1,2,{margin_lr},{margin_lr},{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    cursor = 0.0
    rows = []
    safe_chars = int(max_chars)
    if frame_width and int(frame_width) > 0:
        # Approximate char capacity from visible width and font size.
        usable_width = max(320, int(frame_width) - (int(margin_lr) * 2))
        approx_capacity = int(usable_width / max(10.0, float(font_size) * 0.62))
        safe_chars = max(6, min(int(max_chars), approx_capacity))
    for idx, line in enumerate(lines):
        d = float(phrase_durations[idx] if idx < len(phrase_durations) else 2.2)
        d = max(0.4, d)
        start = _format_ass_time(cursor)
        end = _format_ass_time(cursor + d)
        cleaned = _strip_ass_overrides(line)
        wrapped = _wrap_for_subtitles(cleaned, int(safe_chars), int(max_lines))
        text = _phrase_words_karaoke(wrapped, d, mode)
        rows.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
        cursor += d
    out_path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return str(out_path)
