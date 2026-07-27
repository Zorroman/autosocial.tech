"""Branded full-frame cards for long-form videos — style "Звёздная ночь".

Locally-authored typographic graphics (NO AI images): deep indigo gradient +
starfield + gold accent + Nunito. Each card is a single 1920x1080 PNG rendered
by one short ffmpeg process, then overlaid onto the finished video during its
time window in longform_pipeline.final_mix (memory-safe: still images).

Kinds: intro (channel open), chapter (chapter title), insight (authorial
takeaway), outro (thanks + subscribe).
"""
from __future__ import annotations

import os
import random
import subprocess
from pathlib import Path

_FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
FONT = os.getenv("LONGFORM_CARD_FONT", "/app/assets/fonts/Nunito.ttf")

W, H = 1920, 1080
GOLD = "0xE6B84F"
WHITE = "0xF1EFFA"
MUTED = "0xB0A8CC"
_BG = f"gradients=s={W}x{H}:c0=0x1a1440:c1=0x0a0820:x0=0:y0=0:x1=1400:y1={H}"


def _sp(s: str) -> str:
    """Letter-space a short label/eyebrow."""
    return " ".join(list(s))


def _tf(work: Path, name: str, text: str) -> str:
    p = Path(work) / f"card_{name}.txt"
    p.write_text(text, encoding="utf-8")
    return str(p)


def _dt(tf: str, color: str, size: int, x: str, y: str, extra: str = "") -> str:
    return f"drawtext=fontfile={FONT}:textfile={tf}:fontcolor={color}:fontsize={size}:x={x}:y={y}{extra}"


def _stars(seed: int) -> list[str]:
    r = random.Random(seed)
    out = []
    for _ in range(70):
        x = r.randint(30, W - 30)
        y = r.randint(30, H - 30)
        s = r.choice([2, 2, 3, 4])
        a = r.choice([0.35, 0.5, 0.7])
        c = r.choice(["0xFFFFFF", "0xFFFFFF", GOLD])
        out.append(f"drawbox=x={x}:y={y}:w={s}:h={s}:color={c}@{a}:t=fill")
    return out


def _render(out_png: Path, layers: list[str]) -> bool:
    cmd = [_FFMPEG, "-y", "-f", "lavfi", "-i", _BG,
           "-vf", ",".join(layers), "-frames:v", "1", str(out_png)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return p.returncode == 0 and Path(out_png).exists()
    except Exception:
        return False


def _fit(text: str, big: int, small: int, cutoff: int) -> int:
    return small if len(text) > cutoff else big


def _wrap(text: str, width: int, max_lines: int) -> str:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
        else:
            cur = (cur + " " + w) if cur else w
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return "\n".join(lines)


def intro_card(work: Path, out: Path, title: str,
               eyebrow: str = "ТАЙНЫ · ЗНАКИ · ОСОЗНАННОСТЬ",
               tagline: str = "Голос древних знаний") -> bool:
    t = (title or "AURORA SECRETUM").upper()
    return _render(out, _stars(7) + [
        _dt(_tf(work, "i_e", _sp(eyebrow)), GOLD, 32, "(w-text_w)/2", "372"),
        _dt(_tf(work, "i_t", t), WHITE, _fit(t, 132, 92, 18), "(w-text_w)/2", "430"),
        f"drawbox=x=(iw-300)/2:y=618:w=300:h=4:color={GOLD}:t=fill",
        _dt(_tf(work, "i_g", tagline), MUTED, 40, "(w-text_w)/2", "660"),
    ])


def chapter_card(work: Path, out: Path, index: int, title: str) -> bool:
    t = (title or "").strip() or "Глава"
    return _render(out, _stars(21 + index) + [
        _dt(_tf(work, f"c_l{index}", _sp(f"ГЛАВА {index:02d}")), GOLD, 40, "(w-text_w)/2", "420"),
        _dt(_tf(work, f"c_t{index}", t), WHITE, _fit(t, 100, 72, 26), "(w-text_w)/2", "490"),
        f"drawbox=x=(iw-260)/2:y=650:w=260:h=4:color={GOLD}:t=fill",
    ])


def insight_card(work: Path, out: Path, quote: str, brand: str) -> bool:
    q = "«" + _wrap((quote or "").strip().strip("«»\"'"), 30, 3) + "»"
    return _render(out, _stars(42) + [
        f"drawbox=x=210:y=350:w=6:h=420:color={GOLD}:t=fill",
        _dt(_tf(work, "s_l", _sp("АВТОРСКИЙ ВЫВОД")), GOLD, 30, "268", "366"),
        _dt(_tf(work, "s_q", q), WHITE, 62, "268", "440", ":line_spacing=18"),
        _dt(_tf(work, "s_b", f"— {brand}"), MUTED, 32, "268", "718"),
    ])


def outro_card(work: Path, out: Path, brand: str,
               line: str = "Спасибо за просмотр",
               sub: str = "Подпишись, чтобы не пропустить новое") -> bool:
    return _render(out, _stars(99) + [
        _dt(_tf(work, "o_e", _sp((brand or "AURORA SECRETUM").upper())), GOLD, 30, "(w-text_w)/2", "376"),
        _dt(_tf(work, "o_t", line), WHITE, 92, "(w-text_w)/2", "430"),
        f"drawbox=x=(iw-300)/2:y=580:w=300:h=4:color={GOLD}:t=fill",
        _dt(_tf(work, "o_s", sub), MUTED, 40, "(w-text_w)/2", "622"),
    ])
