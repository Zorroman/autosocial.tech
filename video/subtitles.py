from pathlib import Path


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
    if reveal_mode == "letter":
        parts = list(text)
    else:
        parts = text.split()
    if not parts:
        return text
    unit_centis = max(1, int((duration_sec * 100) / len(parts)))
    if reveal_mode == "letter":
        return "".join([f"{{\\k{unit_centis}}}{ch}" for ch in parts])
    return " ".join([f"{{\\k{unit_centis}}}{w}" for w in parts])


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
    font_size: int = 54,
) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.601\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,"
        "MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Default,{font_name},{font_size},&H00FFFFFF,&H0000FFFF,&H00202020,&H64000000,1,0,0,0,100,100,0,0,1,2,1,2,60,60,70,1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    cursor = 0.0
    rows = []
    for idx, line in enumerate(lines):
        d = float(phrase_durations[idx] if idx < len(phrase_durations) else 2.2)
        d = max(0.4, d)
        start = _format_ass_time(cursor)
        end = _format_ass_time(cursor + d)
        text = _phrase_words_karaoke(line, d, reveal_mode)
        rows.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
        cursor += d
    out_path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return str(out_path)
