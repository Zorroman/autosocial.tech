from pathlib import Path
import re
import textwrap


SOCIAL_SUBTITLE_PROFILES = {
    "generic": {
        "font_name": "Arial",
        "font_size": 34,
        "max_chars": 28,
        "max_lines": 2,
        "max_words": 8,
        "margin_lr": 96,
        "margin_v": 120,
        "reveal_mode": "word",
        "bold": 1,
        "outline": 2.6,
        "shadow": 1,
        "alignment": 2,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00181818",
        "back_colour": "&H64000000",
        "highlight_words": True,
        "highlight_primary_colour": "&H00FF7A9E",
        "highlight_outline_colour": "&H006B2044",
        "highlight_back_colour": "&H640E0818",
        "highlight_outline": 5.6,
        "highlight_shadow": 0.0,
        "highlight_bold": 1,
        "safe_area": "standard_bottom",
    },
    "facebook": {
        "font_name": "Arial",
        "font_size": 66,
        "max_chars": 18,
        "max_lines": 2,
        "max_words": 7,
        "margin_lr": 84,
        "margin_v": 430,
        "reveal_mode": "plain",
        "bold": 1,
        "outline": 3.2,
        "shadow": 1,
        "alignment": 2,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00111111",
        "back_colour": "&H8C000000",
        "highlight_words": True,
        "highlight_primary_colour": "&H00FF7A9E",
        "highlight_outline_colour": "&H006B2044",
        "highlight_back_colour": "&H780E0818",
        "highlight_outline": 6.4,
        "highlight_shadow": 0.0,
        "highlight_bold": 1,
        "safe_area": "meta_reels_safe_lower_third",
    },
    "instagram": {
        "font_name": "Arial",
        "font_size": 66,
        "max_chars": 18,
        "max_lines": 2,
        "max_words": 7,
        "margin_lr": 84,
        "margin_v": 430,
        "reveal_mode": "plain",
        "bold": 1,
        "outline": 3.2,
        "shadow": 1,
        "alignment": 2,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00111111",
        "back_colour": "&H8C000000",
        "highlight_words": True,
        "highlight_primary_colour": "&H00FF7A9E",
        "highlight_outline_colour": "&H006B2044",
        "highlight_back_colour": "&H780E0818",
        "highlight_outline": 6.4,
        "highlight_shadow": 0.0,
        "highlight_bold": 1,
        "safe_area": "meta_reels_safe_lower_third",
    },
    "youtube": {
        "font_name": "Arial",
        "font_size": 58,
        "max_chars": 22,
        "max_lines": 2,
        "max_words": 8,
        "margin_lr": 80,
        "margin_v": 320,
        "reveal_mode": "plain",
        "bold": 1,
        "outline": 3.0,
        "shadow": 1,
        "alignment": 2,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00151515",
        "back_colour": "&H78000000",
        "highlight_words": True,
        "highlight_primary_colour": "&H00FF7A9E",
        "highlight_outline_colour": "&H006B2044",
        "highlight_back_colour": "&H780E0818",
        "highlight_outline": 5.8,
        "highlight_shadow": 0.0,
        "highlight_bold": 1,
        "safe_area": "shorts_safe_lower_third",
    },
}


def resolve_subtitle_profile(platform_target: str = "generic", orientation: str = "horizontal", subtitle_style: str = "social_default") -> dict:
    key = str(platform_target or "generic").strip().lower()
    if key not in SOCIAL_SUBTITLE_PROFILES:
        key = "generic"
    profile = dict(SOCIAL_SUBTITLE_PROFILES[key])
    style = str(subtitle_style or "social_default").strip().lower()
    if style == "clean_bold":
        profile.update({"font_size": 62 if str(orientation).lower() == "vertical" else 34, "outline": 2.2, "shadow": 0.6, "highlight_words": False, "back_colour": "&H50000000"})
    elif style == "creator_pop":
        profile.update({"font_size": 70 if str(orientation).lower() == "vertical" else 38, "outline": 4.0, "shadow": 1.4, "highlight_words": True, "highlight_primary_colour": "&H0000F5FF", "highlight_outline_colour": "&H00201800"})
    elif style == "luxury_minimal":
        profile.update({"font_size": 56 if str(orientation).lower() == "vertical" else 30, "outline": 1.8, "shadow": 0.4, "highlight_words": False, "back_colour": "&H38000000", "primary_colour": "&H00F7F2E8"})
    elif style == "mystical_glow":
        profile.update({"font_size": 64 if str(orientation).lower() == "vertical" else 34, "outline": 3.4, "shadow": 1.2, "highlight_words": True, "highlight_primary_colour": "&H00FFD6FF", "highlight_outline_colour": "&H006C2578", "back_colour": "&H6414071C"})
    if str(orientation or "").strip().lower() != "vertical":
        profile.update({
            "font_size": min(int(profile.get("font_size") or 34), 38),
            "max_chars": 30,
            "margin_lr": 120,
            "margin_v": 100,
            "reveal_mode": "word",
            "safe_area": "landscape_lower_third",
        })
    profile["style"] = style
    return profile


def _format_ass_time(seconds: float) -> str:
    total = max(0.0, float(seconds))
    h = int(total // 3600)
    total -= h * 3600
    m = int(total // 60)
    total -= m * 60
    s = int(total)
    cs = int(round((total - s) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _format_srt_time(seconds: float) -> str:
    total = max(0.0, float(seconds))
    hours = int(total // 3600)
    total -= hours * 3600
    minutes = int(total // 60)
    total -= minutes * 60
    secs = int(total)
    millis = int(round((total - secs) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _phrase_words_karaoke(phrase: str, duration_sec: float, reveal_mode: str) -> str:
    text = str(phrase or "").strip()
    if not text:
        return ""
    mode = str(reveal_mode or "").strip().lower()
    if mode not in {"word", "letter"}:
        return text
    rows = text.split("\\N")
    chunks: list[list[str]] = []
    total_units = 0
    for row in rows:
        parts = list(row) if mode == "letter" else row.split()
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
            rendered_rows.append("".join([f"{{\k{unit_centis}}}{ch}" for ch in parts]))
        else:
            rendered_rows.append(" ".join([f"{{\k{unit_centis}}}{w}" for w in parts]))
    return "\\N".join(rendered_rows)


def _subtitle_word_units(text: str) -> list[dict]:
    rows = str(text or "").split("\\N")
    units: list[dict] = []
    word_index = 0
    for row_index, row in enumerate(rows):
        words = [w for w in str(row or "").split() if w]
        for col_index, word in enumerate(words):
            clean = re.sub(r"[^\w\u0400-\u04FF-]+", "", word, flags=re.UNICODE)
            weight = max(1, len(clean or word))
            units.append(
                {
                    "word": word,
                    "row_index": row_index,
                    "col_index": col_index,
                    "word_index": word_index,
                    "weight": weight,
                }
            )
            word_index += 1
    return units


def _highlight_overlay_text(
    text: str,
    active_word_index: int,
    *,
    highlight_primary_colour: str,
    highlight_outline_colour: str,
    highlight_back_colour: str,
    highlight_outline: float,
    highlight_shadow: float,
    highlight_bold: int,
) -> str:
    rows = str(text or "").split("\\N")
    active_idx = int(active_word_index)
    out_rows: list[str] = []
    flat_index = 0
    for row in rows:
        words = [w for w in str(row or "").split() if w]
        rendered: list[str] = []
        for word in words:
            if flat_index == active_idx:
                rendered.append(
                    f"{{\\alpha&H00&\\1c{highlight_primary_colour}\\3c{highlight_outline_colour}\\4c{highlight_back_colour}"
                    f"\\bord{float(highlight_outline):.1f}\\shad{float(highlight_shadow):.1f}\\b{int(highlight_bold)}}}"
                    f"{word}{{\\rDefault}}"
                )
            else:
                rendered.append(f"{{\\alpha&HFF&}}{word}{{\\rDefault}}")
            flat_index += 1
        out_rows.append(" ".join(rendered))
    return "\\N".join(out_rows)


def _strip_ass_overrides(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\{[^}]*\}", "", value)
    value = value.replace("{", "").replace("}", "")
    return value


def _wrap_plain_text(text: str, width: int) -> list[str]:
    clean = " ".join(str(text or "").split()).strip()
    if not clean:
        return []
    return textwrap.wrap(clean, width=max(6, int(width)), break_long_words=False, break_on_hyphens=False) or [clean]


def _score_chunk(lines: list[str], max_lines: int, max_words: int, max_chars: int) -> float:
    if not lines or len(lines) > max_lines:
        return -999.0
    joined = " ".join(lines)
    words = [w for w in joined.split() if w]
    score = 0.0
    score -= max(0, len(words) - max_words) * 2.0
    score -= max(abs(len(lines[0]) - len(lines[-1])) - 6, 0) * 0.05
    if len(lines) == 2 and len(lines[-1].split()) == 1 and len(lines[-1]) <= 4:
        score -= 3.0
    if any(len(line) > max_chars for line in lines):
        score -= 999.0
    return score


def chunk_subtitle_text(text: str, *, max_chars: int = 18, max_lines: int = 2, max_words: int = 7) -> list[str]:
    clean = _strip_ass_overrides(text)
    words = [w for w in clean.split() if w]
    if not words:
        return []
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        probe = current + [word]
        joined = " ".join(probe)
        lines = _wrap_plain_text(joined, max_chars)
        if current and (len(lines) > max_lines or len(probe) > max_words + 1):
            best = " ".join(current)
            best_lines = _wrap_plain_text(best, max_chars)[:max_lines]
            chunks.append("\\N".join(best_lines))
            current = [word]
        else:
            current = probe
    if current:
        best = " ".join(current)
        best_lines = _wrap_plain_text(best, max_chars)
        if len(best_lines) > max_lines:
            collapsed = []
            start = 0
            while start < len(best_lines):
                window = best_lines[start : start + max_lines]
                collapsed.append("\\N".join(window))
                start += max_lines
            chunks.extend(collapsed)
        else:
            chunks.append("\\N".join(best_lines))
    normalized: list[str] = []
    for chunk in chunks:
        lines = str(chunk).split("\\N")
        scored = _score_chunk(lines, max_lines, max_words, max_chars)
        if scored <= -999.0:
            fallback_lines = _wrap_plain_text(" ".join(lines), max_chars)[:max_lines]
            normalized.append("\\N".join(fallback_lines))
        else:
            normalized.append(chunk)
    return [c for c in normalized if str(c or "").strip()]


def load_subtitle_lines(lecture_txt_path: Path | None, fallback_phrases: list[str]) -> list[str]:
    if lecture_txt_path and lecture_txt_path.exists():
        lines = [x.strip() for x in lecture_txt_path.read_text(encoding="utf-8").splitlines() if x.strip()]
        if lines:
            return lines
    return [str(x).strip() for x in fallback_phrases if str(x).strip()]


def build_subtitle_chunks(lines: list[str], phrase_durations: list[float], *, max_chars: int = 18, max_lines: int = 2, max_words: int = 7) -> list[dict]:
    cursor = 0.0
    chunks: list[dict] = []
    for idx, line in enumerate(lines):
        total_duration = max(0.4, float(phrase_durations[idx] if idx < len(phrase_durations) else 2.2))
        split = chunk_subtitle_text(line, max_chars=max_chars, max_lines=max_lines, max_words=max_words) or [str(line or "").strip()]
        raw_lengths = [max(1, len(_strip_ass_overrides(chunk).replace("\\N", " ").split())) for chunk in split]
        units = float(sum(raw_lengths) or 1)
        local_cursor = cursor
        for part, weight in zip(split, raw_lengths):
            part_duration = max(0.35, total_duration * (float(weight) / units))
            chunks.append({
                "text": part,
                "start": local_cursor,
                "end": local_cursor + part_duration,
                "phrase_index": idx,
            })
            local_cursor += part_duration
        if chunks:
            chunks[-1]["end"] = max(chunks[-1]["end"], cursor + total_duration)
        cursor += total_duration
    return chunks


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
    max_words: int = 8,
    margin_lr: int = 72,
    margin_v: int = 120,
    frame_width: int | None = None,
    frame_height: int | None = None,
    alignment: int = 2,
    outline: float = 2.0,
    shadow: float = 1.0,
    bold: int = 1,
    primary_colour: str = "&H00FFFFFF",
    outline_colour: str = "&H00202020",
    back_colour: str = "&H64000000",
    highlight_words: bool = False,
    highlight_primary_colour: str = "&H00FF7A9E",
    highlight_outline_colour: str = "&H006B2044",
    highlight_back_colour: str = "&H640E0818",
    highlight_outline: float = 5.6,
    highlight_shadow: float = 0.0,
    highlight_bold: int = 1,
) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    is_vertical = bool(frame_width and frame_height and int(frame_height) > int(frame_width))
    mode = str(reveal_mode or "word").strip().lower()
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
        f"Style: Default,{font_name},{font_size},{primary_colour},{primary_colour},{outline_colour},{back_colour},{int(bold)},0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},{margin_lr},{margin_lr},{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    chunks = build_subtitle_chunks(lines, phrase_durations, max_chars=max_chars, max_lines=max_lines, max_words=max_words)
    rows = []
    for chunk in chunks:
        start = _format_ass_time(chunk["start"])
        end = _format_ass_time(chunk["end"])
        text = _phrase_words_karaoke(chunk["text"], float(chunk["end"] - chunk["start"]), mode)
        rows.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
        if highlight_words:
            units = _subtitle_word_units(chunk["text"])
            total_weight = float(sum(int(unit["weight"]) for unit in units) or 0)
            if total_weight > 0:
                cursor = float(chunk["start"])
                total_duration = max(0.1, float(chunk["end"] - chunk["start"]))
                for unit in units:
                    duration = max(0.08, total_duration * (float(unit["weight"]) / total_weight))
                    overlay_text = _highlight_overlay_text(
                        chunk["text"],
                        int(unit["word_index"]),
                        highlight_primary_colour=highlight_primary_colour,
                        highlight_outline_colour=highlight_outline_colour,
                        highlight_back_colour=highlight_back_colour,
                        highlight_outline=highlight_outline,
                        highlight_shadow=highlight_shadow,
                        highlight_bold=highlight_bold,
                    )
                    rows.append(
                        f"Dialogue: 1,{_format_ass_time(cursor)},{_format_ass_time(min(float(chunk['end']), cursor + duration))},Default,,0,0,0,,{overlay_text}"
                    )
                    cursor += duration
    out_path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return str(out_path)


def build_srt_subtitles(
    lines: list[str],
    phrase_durations: list[float],
    out_path: Path,
    *,
    max_chars: int = 18,
    max_lines: int = 2,
    max_words: int = 7,
) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    chunks = build_subtitle_chunks(lines, phrase_durations, max_chars=max_chars, max_lines=max_lines, max_words=max_words)
    rows = []
    for idx, chunk in enumerate(chunks, start=1):
        rows.append(str(idx))
        rows.append(f"{_format_srt_time(chunk['start'])} --> {_format_srt_time(chunk['end'])}")
        rows.append(str(chunk['text']).replace("\\N", "\n"))
        rows.append("")
    out_path.write_text("\n".join(rows).strip() + "\n", encoding="utf-8")
    return str(out_path)
