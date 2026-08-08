"""Long-form real-footage orchestrator — one real end-to-end 1080p job, NO publish.

Stages (each persisted to job dir, idempotent/resumable):
  script(reuse) → visual_groups → photo_acquisition → clip_acquisition →
  voiceover → subtitles → graphics(overlays) → segments → chunked_render →
  final_mix → final_qc.

Reuses proven components: footage.providers.pexels.search_photos (real
licensed stock photos), media_diversity.search_both_providers (real licensed
Pexels+Pixabay video clips, same dual-provider search Shorts uses),
video.tts.synthesize_voiceover, subtitle_builder, longform_render
(memory-safe chunked rendering -- Ken Burns pan for photos, straight
scale+crop+trim for clips), the user's music library. No AI images, no AI
video, no publishing. Real video clips are preferred per visual group;
photos remain the required, always-available fallback (acquire_clips() is
best-effort and never blocks the pipeline the way photo acquisition does).
Evidence package (manifests + QC + resources) is written to the job dir.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import requests

import longform_render as lr

_FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
_FFPROBE = os.getenv("FFPROBE_BIN", "ffprobe")
_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _ass_t(s: float) -> str:
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"


def _word_slices(words: list[str], start: float, dur: float) -> list[tuple[float, float]]:
    """Per-word [start, end] windows across the phrase, proportional to length."""
    weights = [max(2, len(w)) for w in words]
    wsum = sum(weights) or 1
    out = []
    t = start
    for i, wt in enumerate(weights):
        seg = (dur - (t - start)) if i == len(words) - 1 else dur * wt / wsum
        out.append((t, t + seg))
        t += seg
    return out


def _pop_line(words: list[str], active: int) -> str:
    """Full line with the ACTIVE word slightly bigger + thicker outline (a gentle
    'pop'), the rest normal. No colour fill — just scale + border emphasis."""
    parts = []
    for i, w in enumerate(words):
        if i == active:
            parts.append(f"{{\\fscx116\\fscy116\\bord6\\shad2}}{w}{{\\r}}")
        else:
            parts.append(w)
    return " ".join(parts)


# ---- forced-alignment subtitles (real word timings from the audio) ---------
# The proportional path below distributes words evenly inside each scene's
# window; over long (~40s) narration scenes that drifts audibly out of sync.
# These transcribe the FINISHED voiceover and time every word from the actual
# audio, so captions land exactly on the spoken word.

_LF_MAX_LINE_CHARS = 40  # per subtitle line at 1920x1080 / Nunito 54


def _transcribe_words(audio_path: str, language: str = "ru") -> list[dict]:
    """Word-level timestamps for the voiceover via OpenAI whisper-1. Returns
    [{'w','s','e'}] in spoken order, or [] on any failure (caller falls back)."""
    try:
        from openai_client import _client, is_openai_enabled
        if not is_openai_enabled():
            return []
        with open(audio_path, "rb") as fh:
            resp = _client().audio.transcriptions.create(
                model="whisper-1", file=fh, response_format="verbose_json",
                timestamp_granularities=["word"], language=(language or "ru"))
        raw = getattr(resp, "words", None)
        if raw is None and isinstance(resp, dict):
            raw = resp.get("words")
        out: list[dict] = []
        for w in (raw or []):
            g = (lambda k: w.get(k) if isinstance(w, dict) else getattr(w, k, None))
            txt = str(g("word") or "").strip()
            if not txt:
                continue
            out.append({"w": txt, "s": float(g("start") or 0.0), "e": float(g("end") or 0.0)})
        return out
    except Exception:
        return []


def _pack_aligned_cues(words: list[dict], max_chars: int = _LF_MAX_LINE_CHARS) -> list[dict]:
    """Group timestamped words into ≤2-line cues on sentence/width boundaries.
    Each cue carries its words (with real timings) and the line-1 word count."""
    from subtitle_builder import _wrap_two_lines
    cues: list[dict] = []
    cur: list[dict] = []

    def _flush():
        if not cur:
            return
        text = " ".join(x["w"] for x in cur)
        wrapped = _wrap_two_lines(text, max_chars)
        split = len(wrapped.split("\n", 1)[0].split()) if "\n" in wrapped else len(cur)
        cues.append({"words": cur[:], "split": max(1, min(split, len(cur)))})

    for w in words:
        tentative = len(" ".join(x["w"] for x in cur) + " " + w["w"])
        if cur and tentative > max_chars * 2:
            _flush(); cur = []
        cur.append(w)
        line = " ".join(x["w"] for x in cur)
        if w["w"].rstrip().endswith((".", "!", "?", "…", ":")) and len(line) >= max_chars:
            _flush(); cur = []
    _flush()
    return cues


def _pop_two_line(words: list[dict], active: int, split: int) -> str:
    """Full cue (two lines via \\N) with the ACTIVE word popped."""
    def _fmt(i, w):
        return (f"{{\\fscx116\\fscy116\\bord6\\shad2}}{w}{{\\r}}" if i == active else w)
    line1 = " ".join(_fmt(i, words[i]["w"]) for i in range(0, split))
    line2 = " ".join(_fmt(i, words[i]["w"]) for i in range(split, len(words)))
    return line1 + ("\\N" + line2 if line2 else "")


# Curated esoteric glossary (channel niche). Keys are lowercase STEMS so Russian
# inflections match (карма/кармы/карму → "карм"). Each term gets a brief, neutral
# one-line gloss shown as a top banner when the word is first spoken.
_GLOSSARY: dict[str, tuple[str, str]] = {
    "карм": ("Карма", "закон причины и следствия"),
    "чакр": ("Чакра", "энергетический центр тела"),
    "медитац": ("Медитация", "практика сосредоточения ума"),
    "интуиц": ("Интуиция", "внутреннее знание без анализа"),
    "подсознан": ("Подсознание", "скрытый слой психики"),
    "аур": ("Аура", "энергетическое поле человека"),
    "реинкарнац": ("Реинкарнация", "перерождение души"),
    "нирван": ("Нирвана", "освобождение от страданий"),
    "мантр": ("Мантра", "звуковая формула для сосредоточения"),
    "дхарм": ("Дхарма", "путь и внутренний закон"),
    "просветлен": ("Просветление", "пробуждение сознания"),
    "осознанн": ("Осознанность", "полное присутствие в моменте"),
    "нумеролог": ("Нумерология", "значение чисел судьбы"),
    "астролог": ("Астрология", "влияние светил на судьбу"),
    "рун": ("Руны", "древние символы-знаки"),
    "тар": ("Таро", "система символических карт"),
    "кристалл": ("Кристаллы", "камни с приписываемой энергией"),
    "ритуал": ("Ритуал", "символическое действие-практика"),
    "вибрац": ("Вибрация", "тонкая энергия-частота"),
    "предназначен": ("Предназначение", "жизненный смысл и путь"),
}


def _term_callouts(words: list[dict], max_n: int = 8, min_gap: float = 18.0,
                   dur: float = 2.6) -> list[dict]:
    """Find first spoken occurrence of each glossary term (well-spaced) and turn
    it into a top-banner callout timed to the real audio."""
    outs: list[dict] = []
    used: set[str] = set()
    last = -1e9
    for w in words:
        if float(w["s"]) < 3.0:  # don't spend a term under the intro card
            continue
        wn = w["w"].lower().strip(".,!?;:—«»\"'()").strip()
        if len(wn) < 4:
            continue
        for stem, (term, defi) in _GLOSSARY.items():
            if stem in used or not wn.startswith(stem):
                continue
            if float(w["s"]) - last < min_gap:
                break
            outs.append({"term": term, "defi": defi,
                         "start": round(float(w["s"]), 2), "end": round(float(w["s"]) + dur, 2)})
            used.add(stem); last = float(w["s"])
            break
        if len(outs) >= max_n:
            break
    return outs


def write_aligned_ass(cues: list[dict], path: Path, callouts: list[dict] | None = None) -> None:
    """ASS from real word timings: each word is shown for [word.start, next
    word.start) so the caption tracks the voice exactly, active word popped."""
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: LF,Nunito,54,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,-1,0,0,0,"
        "100,100,0,0,1,4,1,2,140,140,92,1\n"
        # KEY: top-centre glossary banner in a dark box. BorderStyle=3 draws the
        # box in OutlineColour, padded by Outline px — so it reads over ANY
        # footage, and never collides with the bottom-centre narration subtitles.
        "Style: KEY,Nunito,40,&H00FAEFF1,&H00FAEFF1,&H1A140A05,&H00000000,0,0,0,0,"
        "100,100,0,0,3,10,0,8,90,90,84,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    for c in cues:
        ws = c["words"]; split = c["split"]
        for i, wd in enumerate(ws):
            start = float(wd["s"])
            end = float(ws[i + 1]["s"]) if i + 1 < len(ws) else float(wd["e"])
            if end <= start:
                end = start + 0.15
            lines.append(f"Dialogue: 0,{_ass_t(start)},{_ass_t(end)},LF,,0,0,0,,{_pop_two_line(ws, i, split)}")
    for c in (callouts or []):
        # term in gold + bold, gloss in the style's white; \r resets to style
        txt = f"{{\\b1\\c&H004FB8E6&}}{c['term']}{{\\r}}  —  {c['defi']}"
        lines.append(f"Dialogue: 0,{_ass_t(float(c['start']))},{_ass_t(float(c['end']))},KEY,,0,0,0,,{txt}")
    path.write_text("".join(l if l.endswith('\n') else l + '\n' for l in lines), encoding="utf-8")


def write_landscape_ass(cues: list[dict], path: Path) -> None:
    """Subtitles for 1920x1080 (not the narrow vertical Shorts layout): large,
    bottom-centre, wide margins, white, with the spoken word emphasised by a
    gentle scale-up + thicker outline (word 'pop'), advancing word by word."""
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: LF,Nunito,54,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,-1,0,0,0,"
        "100,100,0,0,1,4,1,2,140,140,92,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    for c in cues:
        raw = str(c.get("text", "")).strip()
        if not raw:
            continue
        start = float(c["start"])
        dur = float(c["duration"]) if "duration" in c else (float(c["end"]) - start)
        words = raw.split()
        if not words:
            continue
        # one event per word: the full line stays on screen, the active word pops
        for i, (ws, we) in enumerate(_word_slices(words, start, dur)):
            lines.append(f"Dialogue: 0,{_ass_t(ws)},{_ass_t(we)},LF,,0,0,0,,{_pop_line(words, i)}")
    path.write_text("".join(l if l.endswith('\n') else l + '\n' for l in lines), encoding="utf-8")


def _probe(path: Path) -> dict:
    try:
        p = subprocess.run([_FFPROBE, "-v", "quiet", "-print_format", "json",
                            "-show_streams", "-show_format", str(path)],
                           capture_output=True, text=True, timeout=60)
        info = json.loads(p.stdout or "{}")
        v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
        return {"duration": float(info.get("format", {}).get("duration") or 0),
                "width": int(v.get("width") or 0), "height": int(v.get("height") or 0),
                "vcodec": v.get("codec_name"), "acodec": a.get("codec_name"),
                "has_v": bool(v), "has_a": bool(a),
                "adur": float(a.get("duration") or 0)}
    except Exception:
        return {"duration": 0, "width": 0, "height": 0, "has_v": False, "has_a": False}


def _run(cmd, timeout=1800):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode == 0, (p.stderr or "")[-600:]


# ---- visual groups (narration-tied) ---------------------------------------

def build_visual_groups(scenes, pillar_keywords: list[str]) -> list[dict]:
    """Group narration scenes into ~7 chapters; each group gets a concrete photo
    query tied to its narration (keyword pool + the group's own text)."""
    narr = [s for s in scenes if not getattr(s, "is_cta", False)]
    n_groups = max(5, min(8, round(len(narr) / 3)))
    per = max(1, round(len(narr) / n_groups))
    kws = [k.strip() for k in (pillar_keywords or []) if k.strip()] or ["buddhist temple"]
    groups = []
    for gi in range(0, len(narr), per):
        chunk = narr[gi:gi + per]
        idx = len(groups)
        query = kws[idx % len(kws)]
        groups.append({
            "visual_group_id": f"g{idx:02d}",
            "scene_ids": [s.id for s in chunk],
            "query": query,
            "chapter_title": f"Глава {idx + 1}",
        })
    return groups


def acquire_photos(groups, work: Path, per_group: int = 4) -> tuple[list[dict], dict]:
    """Download real licensed Pexels photos per group; prep to canvas; manifest."""
    from footage.providers.pexels import search_photos
    raw = work / "raw"; raw.mkdir(parents=True, exist_ok=True)
    prep = work / "prep"; prep.mkdir(parents=True, exist_ok=True)
    manifest = []
    group_photos: dict[str, list[str]] = {}
    seen_ids = set()
    for g in groups:
        got = []
        for cand in search_photos(g["query"], per_page=per_group + 3):
            if cand["provider_asset_id"] in seen_ids:
                continue
            aid = cand["provider_asset_id"]
            rawf = raw / f"{aid}.jpg"
            try:
                if not rawf.exists():
                    r = requests.get(cand["download_url"], timeout=40)
                    if not r.ok:
                        continue
                    rawf.write_bytes(r.content)
                dst = prep / f"{aid}.jpg"
                if not dst.exists() and not lr.prep_image(rawf, dst):
                    continue
                seen_ids.add(aid)
                got.append(str(dst))
                manifest.append({
                    "asset_id": f"px_{aid}", "provider": "pexels",
                    "provider_asset_id": aid, "source_url": cand["page_url"],
                    "download_url": cand["download_url"], "author": cand["author"],
                    "author_url": cand.get("author_url", ""),
                    "license_name": "Pexels License",
                    "license_url": "https://www.pexels.com/license/",
                    "commercial_use_allowed": True, "search_query": g["query"],
                    "visual_group_id": g["visual_group_id"],
                    "downloaded_at": datetime.utcnow().isoformat() + "Z",
                    "file_path": str(dst), "file_hash": _sha(dst), "reused": False,
                })
                if len(got) >= per_group:
                    break
            except Exception:
                continue
        group_photos[g["visual_group_id"]] = got
    return manifest, group_photos


# ---- real video clips (preferred; photos remain the required fallback) ----
# Downloads real licensed footage per visual group, same dual-provider search
# Shorts already uses (media_diversity.search_both_providers), normalized via
# longform_render.render_clip_segment -- one ffmpeg process per clip, which is
# what keeps this OOM-safe on the 3.8 GB box (see that function's docstring).
# Best-effort and fully optional: acquire_photos() above is still called
# unconditionally and still gates the pipeline (n_photos < 12 -> blocked), so
# a total clip-acquisition failure (network, both providers down, no results
# for the niche) degrades silently to the existing all-photo behaviour rather
# than blocking a video that would otherwise render fine.
LONGFORM_MIN_CLIP_SECONDS = 6.0  # margin over seg_len so a full segment always fits


def acquire_clips(groups, work: Path, per_group: int = 2) -> tuple[list[dict], dict]:
    """Download real video clips per group; manifest mirrors acquire_photos()'s
    shape (asset_id/provider/license/...) for the same evidence-package use."""
    from media_diversity import search_both_providers
    clips_dir = work / "clips"; clips_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    group_clips: dict[str, list[tuple[str, float]]] = {}
    seen_ids: set[str] = set()
    for g in groups:
        got: list[tuple[str, float]] = []
        try:
            results = search_both_providers(
                g["query"], orientation="horizontal",
                min_duration=int(LONGFORM_MIN_CLIP_SECONDS), max_duration=40,
                limit=per_group + 4, page=1,
            )
        except Exception:
            results = []
        for r in results:
            key = f"{r.provider}_{r.video_id}"
            if key in seen_ids:
                continue
            target = clips_dir / f"{key}.mp4"
            try:
                if r.provider == "pixabay":
                    from footage.providers.pixabay import download_video as _dl
                    license_name, license_url = "Pixabay License", "https://pixabay.com/service/license/"
                else:
                    from footage.providers.pexels import download_video as _dl
                    license_name, license_url = "Pexels License", "https://www.pexels.com/license/"
                # download_video() ignores most of `target` (it has its own
                # stable cache path, keyed by provider+id) and returns the
                # REAL saved path -- must use the return value, not assume
                # `target` itself got written.
                dst = Path(_dl(r, target))
                if not dst.exists() or dst.stat().st_size < 10_000:
                    continue
                probed = lr._probe(dst)
                real_dur = float(probed.get("duration") or r.duration or 0)
                if real_dur < LONGFORM_MIN_CLIP_SECONDS:
                    continue
                seen_ids.add(key)
                got.append((str(dst), real_dur))
                manifest.append({
                    "asset_id": key, "provider": r.provider,
                    "provider_asset_id": r.video_id, "source_url": r.page_url,
                    "download_url": r.download_url, "author": r.author,
                    "license_name": license_name, "license_url": license_url,
                    "commercial_use_allowed": True, "search_query": g["query"],
                    "visual_group_id": g["visual_group_id"],
                    "downloaded_at": datetime.utcnow().isoformat() + "Z",
                    "file_path": str(dst), "duration": round(real_dur, 2),
                })
                if len(got) >= per_group:
                    break
            except Exception:
                continue
        group_clips[g["visual_group_id"]] = got
    return manifest, group_clips


# ---- segment timeline (Ken Burns matched to narration durations) ----------

def build_timeline(scenes, groups, group_photos, group_clips=None, seg_len: float = 5.0) -> list[lr.Segment]:
    """Interleave real footage ACROSS groups (round-robin) so subjects alternate
    (temple→monk→mountain→ocean…) with a GLOBAL cursor — no group's first asset
    repeats every scene, no two adjacent segments share an asset, and Ken-Burns
    motion cycles (3+ patterns, never the same twice in a row).

    Each group's own asset list is video clips first, photos after -- so the
    round-robin naturally prefers real footage everywhere it's available and
    only reaches for a photo once a group's clips run out (or it has none)."""
    group_clips = group_clips or {}
    # (path, kind, max_seconds) -- max_seconds is None for photos (unbounded;
    # Ken-Burns can stretch a still across any segment length) and the real
    # ffprobe'd clip duration for clips (a segment can never ask for more of
    # a clip than it actually contains).
    per_group: list[list[tuple[str, str, float | None]]] = []
    for g in groups:
        gid = g["visual_group_id"]
        assets = [(path, "clip", dur) for path, dur in group_clips.get(gid, [])]
        assets += [(path, "photo", None) for path in group_photos.get(gid, [])]
        per_group.append(assets)
    interleaved: list[tuple[str, str, float | None]] = []
    for j in range(max((len(p) for p in per_group), default=0)):
        for gp in per_group:
            if j < len(gp):
                interleaved.append(gp[j])
    if not interleaved:
        return []
    total = sum(float(getattr(s, "estimated_duration", None) or 6.0) for s in scenes)
    segs: list[lr.Segment] = []
    pi = mi = 0
    remaining = total
    last_path = None
    motions = lr._MOTIONS
    while remaining > 0.5:
        path, kind, max_seconds = interleaved[pi % len(interleaved)]
        if path == last_path and len(interleaved) > 1:
            pi += 1
            path, kind, max_seconds = interleaved[pi % len(interleaved)]
        cap = min(seg_len, max_seconds) if max_seconds is not None else seg_len
        seg = min(cap, remaining)
        segs.append(lr.Segment(image=path, seconds=round(seg, 2),
                               motion=motions[mi % len(motions)], kind=kind))
        last_path = path
        remaining -= seg
        pi += 1
        mi += 1
    return segs


# ---- final mix (subtitles burn + voice + ducked music + chapter overlays) --

def _esc(p: str) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def final_mix(silent_video: Path, voice: Path, music: Path, ass: Path,
              cards: list[dict], out: Path, dur: float) -> tuple[bool, str]:
    """Burn aligned subtitles, then overlay full-frame branded cards (intro /
    chapter / insight / outro) on top during their time windows, and mix voice
    + ducked music. Cards are opaque stills, so they cover the photo AND the
    subtitles inside their window — no separate subtitle suppression needed.
    Inputs: 0=silent video, 1=voice, 2=music, 3..=card PNGs (looped stills)."""
    fo = max(0.0, dur - 1.2)
    parts = [f"[0:v]subtitles='{_esc(str(ass))}':fontsdir=/app/assets/fonts[vbase]"]
    label = "vbase"
    for i, c in enumerate(cards):
        idx = 3 + i
        nxt = f"vc{i}"
        parts.append(
            f"[{label}][{idx}:v]overlay=0:0:enable='between(t,{float(c['start']):.2f},{float(c['end']):.2f})'[{nxt}]")
        label = nxt
    vgraph = ";".join(parts)
    agraph = (f"[2:a]atrim=0:{dur:.2f},afade=t=in:st=0:d=0.8,afade=t=out:st={fo:.2f}:d=1.2,volume=-22dB[m];"
              "[m][1:a]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=250[md];"
              "[1:a][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-2:LRA=11[a]")
    graph = vgraph + ";" + agraph
    cmd = [_FFMPEG, "-y", "-i", str(silent_video), "-i", str(voice),
           "-stream_loop", "-1", "-i", str(music)]
    for c in cards:
        # single frame (NOT -loop 1): overlay's default repeatlast holds it for
        # the whole clip, so the image decodes once instead of generating frames
        # for the entire timeline (the -loop 1 version OOM'd on the 3.8 GB box).
        cmd += ["-i", str(c["png"])]
    cmd += ["-filter_complex", graph, "-map", f"[{label}]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "25",
            "-pix_fmt", "yuv420p", "-threads", "2",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", "-shortest", str(out)]
    return _run(cmd, timeout=2400)


# ---- orchestrator ----------------------------------------------------------

def run(project_id: int, job_root: str = "/app/output/longform_jobs") -> dict:
    from database import SessionLocal
    from app_models import VideoProject, VideoScene, Channel, ContentPillar
    from video.tts import synthesize_voiceover
    from subtitle_builder import build_cues

    db = SessionLocal()
    work = Path(job_root) / f"job_{project_id}"
    work.mkdir(parents=True, exist_ok=True)
    status = {"project_id": project_id, "stages": {}, "started_at": datetime.utcnow().isoformat()}

    def _stage(name, **kw):
        status["stages"][name] = {"status": "succeeded", **kw}

    try:
        p = db.query(VideoProject).filter_by(id=project_id).first()
        ch = db.query(Channel).filter_by(id=p.channel_id).first()
        pillar = db.query(ContentPillar).filter_by(id=p.content_pillar_id).first() if p.content_pillar_id else None
        kws = [k.strip() for k in ((pillar.visual_keywords or "").split(",") if pillar else []) if k.strip()]
        scenes = (db.query(VideoScene).filter_by(project_id=p.id)
                  .order_by(VideoScene.order_index.asc()).all())
        phrases = [(s.voiceover_text or "").strip() for s in scenes]
        _stage("script", scenes=len(scenes), reused_project=project_id, cta=bool(p.cta_text))

        groups = build_visual_groups(scenes, kws)
        _stage("visual_groups", count=len(groups))

        manifest, group_photos = acquire_photos(groups, work)
        (work / "photo_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
        n_photos = len(manifest)
        if n_photos < 12:
            status["result"] = "blocked"; status["reason"] = f"only {n_photos} photos"
            return status
        _stage("photo_acquisition", photos=n_photos, manifest="photo_manifest.json")

        # Real video clips, preferred over the photos above wherever available
        # (build_timeline() picks clips first per group, falls back to photos).
        # Best-effort: photos already satisfied the n_photos>=12 gate above, so
        # a clip-acquisition failure just means an all-photo render, not a
        # blocked one.
        try:
            clip_manifest, group_clips = acquire_clips(groups, work)
        except Exception:
            clip_manifest, group_clips = [], {}
        if clip_manifest:
            (work / "clip_manifest.json").write_text(json.dumps(clip_manifest, ensure_ascii=False, indent=1))
        _stage("clip_acquisition", clips=len(clip_manifest), manifest="clip_manifest.json")

        # voiceover (cache: reuse if present)
        audio_dir = work / "audio"; audio_dir.mkdir(exist_ok=True)
        voice_file = audio_dir / f"project_{project_id}_voiceover.mp3"
        if voice_file.exists() and voice_file.stat().st_size > 5000:
            durations = None
            voice_str = str(voice_file)
        else:
            voice_str, durations = synthesize_voiceover(
                phrases, audio_dir, f"project_{project_id}",
                voice_name="onyx",  # warm, calm narrator (valid OpenAI voice)
                voice_tone="calm",  # was never actually passed before -- the
                # `instructions` text alone asked for calm delivery but had no
                # native pacing lever backing it; voice_tone="calm" now also
                # applies a native, slightly slower `speed` (see
                # _tts_phrase_openai), which reads as genuinely calmer than
                # instructions text alone.
                instructions=("Читай спокойно, тепло и размеренно, как опытный "
                              "рассказчик-документалист. Естественные паузы между "
                              "мыслями, живая интонация, без спешки и без монотонности."),
                gap_before=[0.3 if getattr(s, "is_cta", False) else 0.0 for s in scenes])
            voice_file = Path(voice_str)
        vdur = _probe(voice_file).get("duration", 0)
        if durations:
            for s, d in zip(scenes, durations):
                if d and d > 0:
                    s.estimated_duration = float(d)
        elif vdur and scenes:
            # Cached voiceover: no per-phrase timing returned. Distribute the
            # ACTUAL probed voice duration across scenes proportional to
            # narration length, so the timeline length, subtitle timing and
            # chapter overlays all match the real audio (otherwise scenes keep
            # their short pre-TTS estimates and -shortest truncates the video).
            weights = [max(1, len((s.voiceover_text or "").strip())) for s in scenes]
            wsum = float(sum(weights)) or 1.0
            for s, w in zip(scenes, weights):
                s.estimated_duration = round(vdur * (w / wsum), 3)
        _stage("voiceover", file=str(voice_file), duration=round(vdur, 1),
               characters=sum(len(x) for x in phrases))

        # subtitles: forced-alignment first — transcribe the finished voiceover
        # so every word is timed from the ACTUAL audio (fixes drift on long
        # narration scenes). Fall back to the proportional scene-timing path if
        # transcription is unavailable.
        ass_path = work / f"subs_{project_id}.ass"
        aligned = _transcribe_words(str(voice_file), language=(ch.language or "ru"))
        if aligned:
            acues = _pack_aligned_cues(aligned)
            callouts = _term_callouts(aligned)
            write_aligned_ass(acues, ass_path, callouts=callouts)
            _stage("subtitles", cues=len(acues), words=len(aligned),
                   callouts=len(callouts), mode="aligned", file=str(ass_path))
        else:
            cursor = 0.0; cue_scenes = []
            for s in scenes:
                sd = float(s.estimated_duration or 6.0)
                st, du = (cursor + 0.3, max(0.1, sd - 0.3)) if getattr(s, "is_cta", False) else (cursor, sd)
                cue_scenes.append({"text": (s.voiceover_text or "").strip(), "start": st, "duration": du})
                cursor += sd
            cues = build_cues(cue_scenes)
            write_landscape_ass(cues, ass_path)  # 1920x1080 style, not vertical Shorts
            _stage("subtitles", cues=len(cues), mode="proportional", file=str(ass_path))

        # branded full-frame cards (intro / chapter / insight / outro) — style C
        import longform_cards as lc
        cards_dir = work / "cards"; cards_dir.mkdir(exist_ok=True)
        brand = (getattr(ch, "youtube_channel_title", None) or getattr(ch, "name", None)
                 or "Aurora Secretum")
        scene_start = {}; _cur = 0.0
        for s in scenes:
            scene_start[s.id] = _cur
            _cur += float(s.estimated_duration or 6.0)
        cards: list[dict] = []
        _ip = cards_dir / "intro.png"
        if lc.intro_card(cards_dir, _ip, brand):
            cards.append({"png": _ip, "start": 0.0, "end": 2.8})
        for gi, g in enumerate(groups):
            g_start = min((scene_start.get(sid, 0.0) for sid in g["scene_ids"]), default=0.0)
            if g_start < 3.0:  # first chapter coincides with the intro card — skip
                continue
            _cp = cards_dir / f"chapter_{gi}.png"
            if lc.chapter_card(cards_dir, _cp, gi + 1, g.get("chapter_title") or ""):
                cards.append({"png": _cp, "start": round(g_start, 2), "end": round(g_start + 2.4, 2)})
        # insight card on the authorial-takeaway scene (marked visual_type=insight;
        # fall back to the last non-CTA scene = the closing synthesis).
        insight = next((s for s in scenes if getattr(s, "visual_type", "") == "insight"
                        and not getattr(s, "is_cta", False)), None)
        if insight is None:
            _noncta = [s for s in scenes if not getattr(s, "is_cta", False)]
            insight = _noncta[-1] if _noncta else None
        if insight is not None:
            _ist = scene_start.get(insight.id, 0.0)
            _iend = min(_ist + max(3.5, min(6.0, float(insight.estimated_duration or 5.0))),
                        vdur - 3.6)
            if _iend > _ist + 2.0:
                _quote = ((insight.voiceover_text or "").strip().split(".")[0])[:150]
                _sp = cards_dir / "insight.png"
                if _quote and lc.insight_card(cards_dir, _sp, _quote, brand):
                    cards.append({"png": _sp, "start": round(_ist, 2), "end": round(_iend, 2)})
        _op = cards_dir / "outro.png"
        if lc.outro_card(cards_dir, _op, brand):
            cards.append({"png": _op, "start": round(max(0.0, vdur - 3.4), 2), "end": round(vdur, 2)})
        _stage("graphics", cards=len(cards))

        segs = build_timeline(scenes, groups, group_photos, group_clips)
        _stage("segments", count=len(segs))

        # chunked silent render
        silent = work / f"silent_{project_id}.mp4"
        rres = lr.render_video(segs, silent, work / "render", chunk_seconds=40)
        if rres.get("status") != "succeeded":
            status["result"] = "failed"; status["render"] = rres
            return status
        _stage("chunked_render", chunks=rres.get("chunk_count"), video_dur=rres.get("duration"))

        # final mix (subtitles + voice + music)
        music = _pick_music()
        final = work / f"longform_{project_id}_final.mp4"
        ok, err = final_mix(silent, voice_file, music, ass_path, cards, final, vdur)
        if not ok:
            status["result"] = "failed"; status["mix_error"] = err
            return status
        _stage("final_mix", music=str(music), output=str(final))

        # final QC — band is relative to the project's duration target with
        # tolerance, not a hard 12-min ceiling: a 720s-target script that lands
        # a little long (e.g. 750s) is fine content-wise. Reject only clearly
        # truncated (<75%) or runaway (>125%) durations, floored at 5 min.
        pr = _probe(final)
        _tgt = int(getattr(p, "duration_target_seconds", 0) or 720)
        band = (max(300, int(_tgt * 0.75)), int(_tgt * 1.25))
        qc = {"file": str(final), "exists": final.exists(),
              "width": pr["width"], "height": pr["height"],
              "duration": round(pr["duration"], 1), "vcodec": pr.get("vcodec"),
              "acodec": pr.get("acodec"), "has_video": pr["has_v"], "has_audio": pr["has_a"],
              "file_size_mb": round(final.stat().st_size / 1e6, 1) if final.exists() else 0}
        qc["passed"] = bool(pr["has_v"] and pr["has_a"] and pr["width"] == 1920
                            and pr["height"] == 1080 and band[0] <= pr["duration"] <= band[1])
        (work / "qc.json").write_text(json.dumps(qc, ensure_ascii=False, indent=1))
        status["qc"] = qc
        status["result"] = "ready_for_manual_review" if qc["passed"] else "needs_revision"
        status["publication_allowed"] = False
        (work / "job_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1))
        return status
    finally:
        db.close()


def _pick_music() -> Path:
    import random
    d = Path(os.getenv("MUSIC_LIBRARY_DIR", "/app/assets/music/calm"))
    tracks = sorted(d.glob("*.mp3"))
    return random.choice(tracks) if tracks else Path("")
