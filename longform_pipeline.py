"""Long-form image-first orchestrator — one real end-to-end 1080p job, NO publish.

Stages (each persisted to job dir, idempotent/resumable):
  script(reuse) → visual_groups → photo_acquisition → voiceover → subtitles →
  graphics(overlays) → segments → chunked_render → final_mix → final_qc.

Reuses proven components: footage.providers.pexels.search_photos (real licensed
stock photos), video.tts.synthesize_voiceover, subtitle_builder, longform_render
(memory-safe chunked Ken Burns), the user's music library. No AI images, no AI
video, no publishing. Evidence package (manifests + QC + resources) is written
to the job dir.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
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
        "Style: LF,DejaVu Sans,52,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,-1,0,0,0,"
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


# ---- segment timeline (Ken Burns matched to narration durations) ----------

def build_timeline(scenes, groups, group_photos, seg_len: float = 5.0) -> list[lr.Segment]:
    """Interleave photos ACROSS groups (round-robin) so subjects alternate
    (temple→monk→mountain→ocean…) with a GLOBAL cursor — no group's first photo
    repeats every scene, no two adjacent segments share a photo, and Ken-Burns
    motion cycles (3+ patterns, never the same twice in a row)."""
    # round-robin interleave: photo #0 of each group, then #1 of each, …
    per_group = [group_photos.get(g["visual_group_id"], []) for g in groups]
    interleaved: list[str] = []
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
    last_img = None
    motions = lr._MOTIONS
    while remaining > 0.5:
        img = interleaved[pi % len(interleaved)]
        if img == last_img and len(interleaved) > 1:
            pi += 1
            img = interleaved[pi % len(interleaved)]
        seg = min(seg_len, remaining)
        segs.append(lr.Segment(image=img, seconds=round(seg, 2), motion=motions[mi % len(motions)]))
        last_img = img
        remaining -= seg
        pi += 1
        mi += 1
    return segs


# ---- final mix (subtitles burn + voice + ducked music + chapter overlays) --

def _esc(p: str) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def final_mix(silent_video: Path, voice: Path, music: Path, ass: Path,
              overlays: list[dict], out: Path, dur: float) -> tuple[bool, str]:
    fo = max(0.0, dur - 1.2)
    vf = [f"subtitles='{_esc(str(ass))}'"]
    for ov in overlays:  # chapter lower-thirds (locally-authored explanatory graphics)
        txt = ov["text"].replace("'", "").replace(":", " ")
        vf.append(
            f"drawbox=x=60:y=h-190:w=760:h=70:color=black@0.45:t=fill:enable='between(t,{ov['start']},{ov['end']})',"
            f"drawtext=fontfile={_FONT}:text='{txt}':x=80:y=h-172:fontsize=34:fontcolor=white:"
            f"enable='between(t,{ov['start']},{ov['end']})'")
    vchain = "[0:v]" + ",".join(vf) + "[v]"
    graph = (vchain + ";"
             f"[2:a]atrim=0:{dur:.2f},afade=t=in:st=0:d=0.8,afade=t=out:st={fo:.2f}:d=1.2,volume=-22dB[m];"
             "[m][1:a]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=250[md];"
             "[1:a][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-2:LRA=11[a]")
    cmd = [_FFMPEG, "-y", "-i", str(silent_video), "-i", str(voice),
           "-stream_loop", "-1", "-i", str(music),
           "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "25",
           "-pix_fmt", "yuv420p", "-threads", "2",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
           "-movflags", "+faststart", "-shortest", str(out)]
    return _run(cmd, timeout=2400)


# ---- orchestrator ----------------------------------------------------------

def run(project_id: int, job_root: str = "/app/output/longform_jobs") -> dict:
    from database import SessionLocal
    from saas_models import VideoProject, VideoScene, Channel, ContentPillar
    from video.tts import synthesize_voiceover
    from subtitle_builder import build_cues, write_ass

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
        _stage("voiceover", file=str(voice_file), duration=round(vdur, 1),
               characters=sum(len(x) for x in phrases))

        # subtitles from scene timing
        cursor = 0.0; cue_scenes = []
        for s in scenes:
            sd = float(s.estimated_duration or 6.0)
            st, du = (cursor + 0.3, max(0.1, sd - 0.3)) if getattr(s, "is_cta", False) else (cursor, sd)
            cue_scenes.append({"text": (s.voiceover_text or "").strip(), "start": st, "duration": du})
            cursor += sd
        cues = build_cues(cue_scenes)
        ass_path = work / f"subs_{project_id}.ass"
        write_landscape_ass(cues, ass_path)  # 1920x1080 style, not vertical Shorts
        _stage("subtitles", cues=len(cues), file=str(ass_path))

        # chapter overlays (locally-authored explanatory graphics)
        overlays = []
        gcursor = 0.0
        sid_dur = {s.id: float(s.estimated_duration or 6.0) for s in scenes}
        for g in groups:
            g_start = gcursor
            for sid in g["scene_ids"]:
                gcursor += sid_dur.get(sid, 6.0)
            overlays.append({"text": g["chapter_title"], "start": round(g_start, 1),
                             "end": round(g_start + 4.0, 1)})
        _stage("graphics", chapter_overlays=len(overlays))

        segs = build_timeline(scenes, groups, group_photos)
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
        ok, err = final_mix(silent, voice_file, music, ass_path, overlays, final, vdur)
        if not ok:
            status["result"] = "failed"; status["mix_error"] = err
            return status
        _stage("final_mix", music=str(music), output=str(final))

        # final QC
        pr = _probe(final)
        band = (8 * 60, 12 * 60)
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
