import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

from footage_matcher import match_shots
from footage.shots import expand_short_shot_specs, normalize_shot_specs
from footage.types import VideoResult
from app_settings import settings
from style_packs import get_style_pack, snapshot_style_pack
from video.render.render_video import render_video
from video.subtitles import build_ass_subtitles, build_srt_subtitles, load_subtitle_lines, resolve_subtitle_profile
from video.tts import synthesize_voiceover
from video_script_generator import ScriptBundle, generate as generate_script
from video_niches_config import resolve_video_niche_profile


_RENDER_SEMAPHORE = threading.Semaphore(settings.VIDEO_RENDER_CONCURRENCY)


def _safe_slug(text: str) -> str:
    raw = str(text or "").strip().lower()
    ascii_only = raw.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9_-]+", "-", ascii_only).strip("-")
    return value[:80] or "video"


def _public_media_url(path: Path) -> str:
    rel = _to_rel(path)
    return f"{settings.API_BASE_URL}/api/media/{rel}"


def _manifest_path(job_id: int) -> Path:
    return settings.OUTPUT_MANIFESTS_DIR / f"{int(job_id)}.json"


def _to_rel(path: str | Path) -> str:
    p = Path(path).resolve()
    try:
        return str(p.relative_to(settings.BASE_DIR)).replace("\\", "/")
    except Exception:
        try:
            return str(p.relative_to(Path.cwd().resolve())).replace("\\", "/")
        except Exception:
            return str(p).replace("\\", "/")


def _from_rel(path_rel: str) -> Path:
    return (settings.BASE_DIR / str(path_rel or "").strip()).resolve()


def _load_manifest_if_possible(job_id: int) -> dict | None:
    path = _manifest_path(job_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _find_reusable_manifest(topic: str, orientation: str, target_seconds: int) -> dict | None:
    manifests = sorted(settings.OUTPUT_MANIFESTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in manifests:
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("topic") or "").strip().lower() != str(topic or "").strip().lower():
            continue
        if str(payload.get("orientation") or "").strip().lower() != str(orientation or "").strip().lower():
            continue
        if int(payload.get("target_seconds") or 0) != int(target_seconds):
            continue
        out_rel = ((payload.get("render") or {}).get("out_path") or "").strip()
        if out_rel and _from_rel(out_rel).exists():
            return payload
    return None


def _effective_platform_target(platform_target: str | None, orientation: str, target_seconds: int) -> str:
    target = str(platform_target or settings.VIDEO_PLATFORM_TARGET or "generic").strip().lower()
    if target in {"facebook", "instagram", "youtube", "generic"}:
        return target
    if orientation == "vertical" and int(target_seconds or 0) <= 70:
        return "facebook"
    return "generic"


def _effective_subtitle_mode(subtitle_mode: str | None, platform_target: str, captions_enabled: bool = True) -> str:
    if not captions_enabled:
        return "off"
    mode = str(subtitle_mode or settings.VIDEO_SUBTITLE_MODE or "auto").strip().lower()
    if mode in {"burned", "external", "off"}:
        return mode
    if platform_target in {"facebook", "instagram", "youtube"}:
        return "burned+external"
    return "burned"


def _subtitle_mode_flags(mode: str) -> tuple[bool, bool]:
    normalized = str(mode or "off").strip().lower()
    burned = normalized in {"burned", "burned+external"}
    external = normalized in {"external", "burned+external"}
    return burned, external


def _clip_debug_entry(clip) -> dict:
    score_breakdown = dict(getattr(clip, "score_breakdown", {}) or {})
    return {
        "provider": getattr(clip, "provider", ""),
        "clip_id": getattr(clip, "clip_id", ""),
        "query_used": getattr(clip, "query_used", ""),
        "clip_path": _to_rel(getattr(clip, "clip_path", "")),
        "query_bucket": score_breakdown.get("query_bucket", ""),
        "shot_size": score_breakdown.get("shot_size", ""),
        "motion_hint": score_breakdown.get("motion_hint", ""),
    }


def _build_recent_selection_memory(
    *,
    user_id: int | None,
    orientation: str,
    style_pack_id: str,
    lookback_days: int = 30,
    max_manifests: int = 120,
) -> dict:
    memory = {
        "ids": set(),
        "authors": set(),
        "tag_signatures": [],
        "query_groups_used": {},
        "selected_results": [],
        "recent_query_buckets": [],
        "recent_scene_keys": [],
        "recent_shot_sizes": [],
        "recent_motion_hints": [],
        "recent_visual_buckets": [],
    }
    if not user_id:
        return memory
    if int(lookback_days or 0) <= 0:
        return memory
    cutoff = datetime.utcnow() - timedelta(days=max(1, int(lookback_days or 30)))
    scanned = 0
    manifests = sorted(settings.OUTPUT_MANIFESTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in manifests:
        if scanned >= max_manifests:
            break
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        try:
            if int(payload.get("user_id") or 0) != int(user_id):
                continue
        except Exception:
            continue
        if str(payload.get("orientation") or "").strip().lower() != str(orientation or "").strip().lower():
            continue
        if str(payload.get("style_pack_id") or "").strip().lower() != str(style_pack_id or "").strip().lower():
            continue
        created_raw = str(payload.get("created_at") or "").strip()
        if created_raw:
            try:
                created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00").replace("+00:00", ""))
                if created_dt < cutoff:
                    continue
            except Exception:
                pass
        for clip in (payload.get("clips") or []):
            if not isinstance(clip, dict):
                continue
            provider = str(clip.get("provider") or "").strip().lower()
            clip_id = str(clip.get("clip_id") or "").strip()
            if provider and clip_id:
                memory["ids"].add(f"{provider}:{clip_id}")
            q = str(clip.get("query_used") or "").strip().lower()
            if q:
                memory["query_groups_used"][q] = int(memory["query_groups_used"].get(q, 0)) + 1
                memory["recent_query_buckets"].append(q.split()[0])
                memory["recent_query_buckets"] = memory["recent_query_buckets"][-6:]
            score_breakdown = clip.get("score_breakdown") if isinstance(clip.get("score_breakdown"), dict) else {}
            for field, key in (
                ("recent_scene_keys", "query_bucket"),
                ("recent_shot_sizes", "shot_size"),
                ("recent_motion_hints", "motion_hint"),
                ("recent_visual_buckets", "visual_bucket"),
            ):
                value = str(score_breakdown.get(key) or "").strip().lower()
                if value:
                    memory[field].append(value)
                    memory[field] = memory[field][-6:]
            title = str(clip.get("title") or "").strip()
            tags = clip.get("tags") if isinstance(clip.get("tags"), list) else []
            if title or tags:
                memory["selected_results"].append(
                    VideoResult(
                        provider=provider or "unknown",
                        video_id=clip_id or "unknown",
                        duration=0,
                        width=0,
                        height=0,
                        page_url="",
                        download_url="",
                        tags=[str(x).strip() for x in tags if str(x).strip()],
                        orientation=orientation,
                        title=title,
                        description="",
                        author="",
                    )
                )
                memory["tag_signatures"].append(f"{title}|{' '.join(sorted([str(x).strip().lower() for x in tags if str(x).strip()]))}")
        scanned += 1
    return memory


def generate_video_job_payload(
    *,
    job_id: int,
    campaign_id: int,
    user_id: int | None = None,
    topic: str,
    offer: str | None,
    language: str,
    target_seconds: int,
    aspect_ratio: str,
    style: str,
    style_pack_id: str | None = None,
    use_lecture_txt: bool = True,
    reuse_manifest: bool = False,
    reuse_from_job_id: int | None = None,
    scene_seconds: int | None = None,
    minimize_repeats: bool = True,
    realistic_only: bool = True,
    progress_callback=None,
    custom_scenes: list[dict] | None = None,
    custom_title: str | None = None,
    custom_description: str | None = None,
    custom_hashtags: list[str] | None = None,
    custom_cta: str | None = None,
    voice_gender: str | None = None,
    voice_tone: str | None = None,
    voice_name: str | None = None,
    speech_speed: str | float | int | None = None,
    avoid_duplicate_footage: bool | None = None,
    subtitle_mode: str | None = None,
    platform_target: str | None = None,
    subtitle_style: str | None = None,
    min_unique_clips_short: int | None = None,
    fallback_related_keywords: bool | None = None,
    niche_visual_profile: str | None = None,
    diversity_mode: str | None = None,
    allow_emergency_reuse: bool | None = None,
    batch_footage_memory: dict | None = None,
    footage_intent: str | None = None,
    style_preset: str | None = None,
) -> dict:
    target_seconds = max(20, min(480, int(target_seconds or 30)))
    orientation = "vertical" if aspect_ratio == "9:16" else "horizontal"
    style_pack = get_style_pack(style_pack_id)
    avoid_duplicate_footage = bool(settings.VIDEO_AVOID_DUPLICATE_FOOTAGE if avoid_duplicate_footage is None else avoid_duplicate_footage)
    fallback_related_keywords = bool(settings.VIDEO_FALLBACK_RELATED_KEYWORDS if fallback_related_keywords is None else fallback_related_keywords)
    min_unique_clips_short = max(4, int(min_unique_clips_short or settings.VIDEO_MIN_UNIQUE_CLIPS_SHORT or 8))
    diversity_mode = str(diversity_mode or settings.VIDEO_DIVERSITY_MODE or "balanced").strip().lower() or "balanced"
    if orientation == "vertical" and target_seconds <= 40 and diversity_mode == "balanced":
        diversity_mode = "high"
    if allow_emergency_reuse is None:
        allow_emergency_reuse = bool(settings.VIDEO_ALLOW_EMERGENCY_REUSE)
        if orientation == "vertical" and target_seconds <= 40:
            allow_emergency_reuse = False
    niche_profile = resolve_video_niche_profile(niche_visual_profile, topic, offer or "")
    effective_platform_target = _effective_platform_target(platform_target, orientation, target_seconds)
    effective_subtitle_mode = _effective_subtitle_mode(subtitle_mode, effective_platform_target, captions_enabled=True)
    subtitle_profile = resolve_subtitle_profile(effective_platform_target, orientation, subtitle_style or settings.VIDEO_SUBTITLE_STYLE)
    burned_subtitles_enabled, external_srt_enabled = _subtitle_mode_flags(effective_subtitle_mode)
    cta_text = " ".join(str(custom_cta or "").split()).strip()
    if cta_text and cta_text[-1] not in ".!?":
        cta_text = f"{cta_text}."
    cta_text = cta_text[:180]
    if callable(progress_callback):
        progress_callback("structure", 5, "Формируем структуру ролика")
    if reuse_manifest:
        old = None
        if reuse_from_job_id:
            old = _load_manifest_if_possible(int(reuse_from_job_id))
        if not old:
            old = _load_manifest_if_possible(job_id)
        if not old:
            old = _find_reusable_manifest(topic=topic, orientation=orientation, target_seconds=target_seconds)
        if old:
            out_rel = ((old.get("render") or {}).get("out_path") or "").strip()
            if out_rel:
                out_abs = _from_rel(out_rel)
                if out_abs.exists():
                    reused_manifest = dict(old)
                    reused_manifest["job_id"] = str(job_id)
                    reused_manifest_path = _manifest_path(job_id)
                    reused_manifest_path.write_text(json.dumps(reused_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                    audio_rel = ((old.get("audio") or {}).get("local_path") or "").strip()
                    sub_rel = ((old.get("subtitles") or {}).get("local_path") or "").strip()
                    srt_rel = ((old.get("subtitles") or {}).get("srt_local_path") or "").strip()
                    return {
                        "video_local_path": str(out_abs),
                        "video_url": _public_media_url(out_abs),
                        "audio_url": _public_media_url(_from_rel(audio_rel)) if audio_rel else "",
                        "subtitles_url": _public_media_url(_from_rel(sub_rel)) if sub_rel else "",
                        "subtitles_srt_url": _public_media_url(_from_rel(srt_rel)) if srt_rel else "",
                        "manifest_url": _public_media_url(reused_manifest_path),
                        "title": str(old.get("title") or ""),
                        "description": str(old.get("description") or ""),
                        "hashtags": list(old.get("hashtags") or []),
                        "safety_rules": list(old.get("safety_rules") or []),
                        "target_seconds": int(old.get("target_seconds") or target_seconds),
                        "style_pack_id": str(old.get("style_pack_id") or style_pack["id"]),
                        "debug": dict(old.get("debug") or {}),
                    }

    if isinstance(custom_scenes, list) and custom_scenes:
        fixed_scene_seconds = float(scene_seconds) if scene_seconds and float(scene_seconds) > 0 else 0.0
        min_scene_seconds = fixed_scene_seconds if fixed_scene_seconds > 0 else 2.0
        max_scene_count = max(1, int(target_seconds / max(1.0, min_scene_seconds)))
        words_per_second = 2.2
        phrases: list[str] = []
        shotlist: list[dict] = []
        for idx, scene in enumerate(custom_scenes[:max_scene_count]):
            if not isinstance(scene, dict):
                continue
            text = str(scene.get("text") or "").strip()
            if not text:
                continue
            slot_seconds = fixed_scene_seconds if fixed_scene_seconds > 0 else max(2.0, float(target_seconds) / float(max_scene_count))
            max_words = max(6, int(slot_seconds * words_per_second))
            words = [w for w in text.split() if w]
            if len(words) > max_words:
                text = " ".join(words[:max_words]).strip()
            queries_raw = scene.get("queries")
            queries = list(queries_raw) if isinstance(queries_raw, list) else []
            queries = [str(x).strip() for x in queries if str(x).strip()][:3]
            intent = str(scene.get("footage_intent") or footage_intent or "").strip()
            if intent:
                queries = [f"{intent} {q}".strip() for q in (queries or [text])][:3]
            scene_type = str(scene.get("scene_type") or "work").strip() or "work"
            phrases.append(text)
            shotlist.append(
                {
                    "phrase_index": idx,
                    "queries": queries or ["real life", "business people"],
                    "mood": str(scene.get("mood") or style_pack.get("mood") or "neutral"),
                    "scene_type": scene_type,
                }
            )
        if not phrases:
            phrases = [f"Разбираем тему: {topic}"]
            shotlist = [{"phrase_index": 0, "queries": ["real life"], "mood": "neutral", "scene_type": "work"}]
        if cta_text:
            phrases[-1] = cta_text
        script = ScriptBundle(
            phrases=phrases,
            shotlist=shotlist,
            title=str(custom_title or topic or "Видео")[:70],
            description=str(custom_description or f"Видео по теме: {topic}")[:5000],
            hashtags=[str(x).strip() for x in (custom_hashtags or []) if str(x).strip()][:20],
            safety_rules=["only realistic scenes"],
        )
    else:
        script = generate_script(
            topic=topic,
            offer=offer,
            language=language or "ru",
            target_seconds=target_seconds,
            style=style or "educational",
            style_pack=style_pack,
        )
        if cta_text:
            phrases = [str(x or "").strip() for x in (script.phrases or []) if str(x or "").strip()]
            if phrases:
                phrases[-1] = cta_text
            else:
                phrases = [cta_text]
            script = ScriptBundle(
                phrases=phrases,
                shotlist=script.shotlist,
                title=script.title,
                description=script.description,
                hashtags=script.hashtags,
                safety_rules=script.safety_rules,
            )
    intent_text = " ".join(str(footage_intent or "").split()).strip()
    if intent_text and getattr(script, "shotlist", None):
        for shot in script.shotlist:
            if isinstance(shot, dict):
                base_queries = [str(q or "").strip() for q in (shot.get("queries") or []) if str(q or "").strip()]
                shot["queries"] = [f"{intent_text} {q}".strip() for q in (base_queries or [topic])][:4]
    run_id = f"job{job_id}_camp{campaign_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{_safe_slug(topic)}"
    if callable(progress_callback):
        progress_callback("structure", 10, "Сценарий готов, создаем озвучку")

    audio_path, phrase_durations = synthesize_voiceover(
        script.phrases,
        out_dir=settings.OUTPUT_AUDIO_DIR,
        prefix=run_id,
        min_phrase_seconds=(float(scene_seconds) if scene_seconds and float(scene_seconds) > 0 else None),
        target_total_seconds=float(target_seconds),
        voice_gender=voice_gender,
        voice_tone=voice_tone,
        voice_name=voice_name,
        speech_speed=speech_speed,
    )
    if callable(progress_callback):
        progress_callback("footage", 18, "Подбираем футажи под сцены")

    shot_specs = normalize_shot_specs(
        script.phrases,
        script.shotlist[: len(script.phrases)],
        phrase_durations,
        style_pack=style_pack,
        niche_visual_profile=str(niche_profile.get("id") or ""),
    )
    if orientation == "vertical" and target_seconds <= 40:
        shot_specs = expand_short_shot_specs(shot_specs, target_seconds=target_seconds, min_segments=min_unique_clips_short)
    recent_memory = _build_recent_selection_memory(
        user_id=user_id,
        orientation=orientation,
        style_pack_id=str(style_pack.get("id") or "default_pro"),
        lookback_days=int(getattr(settings, "VIDEO_CROSS_VIDEO_DEDUP_DAYS", 30) or 30),
        max_manifests=int(getattr(settings, "VIDEO_CROSS_VIDEO_DEDUP_MAX_MANIFESTS", 200) or 200),
    )
    if isinstance(batch_footage_memory, dict):
        for key in ["ids", "authors", "tag_signatures", "recent_query_buckets", "recent_visual_buckets"]:
            vals = batch_footage_memory.get(key)
            if vals:
                base = recent_memory.get(key) or ([] if key != "query_groups_used" else {})
                if isinstance(base, set):
                    base.update(vals)
                elif isinstance(base, list):
                    base.extend([str(x) for x in vals if str(x)])
                recent_memory[key] = base
    selection_diagnostics = {
        "keywords_used": [],
        "duplicate_filtered": 0,
        "found_clips": 0,
        "unique_selected": 0,
        "reuse_fallback": False,
        "exact_duplicate_filtered": 0,
        "near_duplicate_filtered": 0,
        "fallback_steps": [],
        "warnings": [],
        "timeline_segment_count": len(shot_specs),
        "niche_profile": str(niche_profile.get("id") or "generic"),
        "diversity_mode": diversity_mode,
    }
    clips = match_shots(
        shot_specs=shot_specs,
        orientation=orientation,
        style_pack=style_pack,
        minimize_repeats=bool(minimize_repeats),
        initial_memory=recent_memory,
        diagnostics=selection_diagnostics,
        avoid_duplicate_footage=avoid_duplicate_footage,
        min_unique_clips_short=min_unique_clips_short,
        fallback_related_keywords=fallback_related_keywords,
        diversity_mode=diversity_mode,
        allow_emergency_reuse=bool(allow_emergency_reuse),
    )
    if callable(progress_callback):
        progress_callback("footage", 35, "Футажи подобраны")
    lecture_path = (settings.BASE_DIR / "lecture.txt") if (use_lecture_txt and not cta_text) else None
    subtitle_lines = load_subtitle_lines(lecture_path, script.phrases)
    subtitles_path = settings.OUTPUT_SUBTITLES_DIR / f"{run_id}.ass"
    subtitles_srt_path = settings.OUTPUT_SUBTITLES_DIR / f"{run_id}.srt"
    subtitle_chunks_count = 0
    if burned_subtitles_enabled:
        build_ass_subtitles(
            lines=subtitle_lines,
            phrase_durations=phrase_durations,
            out_path=subtitles_path,
            reveal_mode=str(subtitle_profile.get("reveal_mode") or ("plain" if orientation == "vertical" else "word")),
            font_name=str(subtitle_profile.get("font_name") or "Arial"),
            font_size=int(subtitle_profile.get("font_size") or (64 if orientation == "vertical" else 30)),
            max_chars=int(subtitle_profile.get("max_chars") or (20 if orientation == "vertical" else 30)),
            max_lines=int(subtitle_profile.get("max_lines") or 2),
            max_words=int(subtitle_profile.get("max_words") or 8),
            margin_lr=int(subtitle_profile.get("margin_lr") or (72 if orientation == "vertical" else 120)),
            margin_v=int(subtitle_profile.get("margin_v") or (430 if orientation == "vertical" else 100)),
            frame_width=(1080 if orientation == "vertical" else 1920),
            frame_height=(1920 if orientation == "vertical" else 1080),
            alignment=int(subtitle_profile.get("alignment") or 2),
            outline=float(subtitle_profile.get("outline") or 3.0),
            shadow=float(subtitle_profile.get("shadow") or 1.0),
            bold=int(subtitle_profile.get("bold") or 1),
            primary_colour=str(subtitle_profile.get("primary_colour") or "&H00FFFFFF"),
            outline_colour=str(subtitle_profile.get("outline_colour") or "&H00111111"),
            back_colour=str(subtitle_profile.get("back_colour") or "&H8C000000"),
            highlight_words=bool(subtitle_profile.get("highlight_words")),
            highlight_primary_colour=str(subtitle_profile.get("highlight_primary_colour") or "&H00FF7A9E"),
            highlight_outline_colour=str(subtitle_profile.get("highlight_outline_colour") or "&H006B2044"),
            highlight_back_colour=str(subtitle_profile.get("highlight_back_colour") or "&H640E0818"),
            highlight_outline=float(subtitle_profile.get("highlight_outline") or 5.6),
            highlight_shadow=float(subtitle_profile.get("highlight_shadow") or 0.0),
            highlight_bold=int(subtitle_profile.get("highlight_bold") or 1),
        )
    if external_srt_enabled:
        build_srt_subtitles(
            lines=subtitle_lines,
            phrase_durations=phrase_durations,
            out_path=subtitles_srt_path,
            max_chars=int(subtitle_profile.get("max_chars") or 18),
            max_lines=int(subtitle_profile.get("max_lines") or 2),
            max_words=int(subtitle_profile.get("max_words") or 7),
        )
    if subtitles_srt_path.exists():
        subtitle_chunks_count = max(1, len([x for x in subtitles_srt_path.read_text(encoding="utf-8").splitlines() if x.strip().isdigit()]))
    out_video = settings.OUTPUT_VIDEOS_DIR / f"{run_id}.mp4"

    if callable(progress_callback):
        progress_callback("render", 40, "Собираем видео и накладываем субтитры")
    with _RENDER_SEMAPHORE:
        render_video(
            clips=[{"clip_path": c.clip_path, "duration_target": c.duration_target} for c in clips],
            voiceover_path=audio_path,
            subtitles_path=(str(subtitles_path) if burned_subtitles_enabled else ""),
            out_path=str(out_video),
            orientation=orientation,
            fps=30,
            resolution="1080x1920" if orientation == "vertical" else "1920x1080",
            subtitle_profile=subtitle_profile,
        )
    if callable(progress_callback):
        progress_callback("render", 85, "Рендер завершен, готовим экспорт")

    if effective_platform_target in {"facebook", "instagram"} and not burned_subtitles_enabled:
        selection_diagnostics.setdefault("warnings", []).append("captions_disabled_for_meta")
    if subtitle_chunks_count and subtitle_chunks_count > max(24, len(script.phrases) * 4):
        selection_diagnostics.setdefault("warnings", []).append("subtitle_chunks_dense")
    if len(clips) < min_unique_clips_short and target_seconds <= 40:
        selection_diagnostics.setdefault("warnings", []).append("limited_visual_pool")

    unique_clips_used = [_clip_debug_entry(c) for c in clips]
    manifest = {
        "job_id": str(job_id),
        "run_id": run_id,
        "created_at": datetime.utcnow().isoformat(),
        "user_id": int(user_id) if user_id else None,
        "campaign_id": campaign_id,
        "topic": topic,
        "offer": offer,
        "language": language,
        "target_seconds": target_seconds,
        "aspect_ratio": aspect_ratio,
        "orientation": orientation,
        "style_pack_id": style_pack["id"],
        "niche_profile": niche_profile,
        "style_pack_rules": snapshot_style_pack(style_pack),
        "script": {
            "phrases": script.phrases,
            "shotlist": script.shotlist,
            "title": script.title,
            "description": script.description,
            "hashtags": script.hashtags,
            "cta": cta_text,
            "safety_rules": script.safety_rules,
        },
        "phrases": script.phrases,
        "title": script.title,
        "description": script.description,
        "hashtags": script.hashtags,
        "cta": cta_text,
        "safety_rules": script.safety_rules,
        "shots": [
            {
                "phrase_index": c.phrase_index,
                "phrase_text": c.phrase_text,
                "duration_s": c.duration_target,
                "queries": [c.query_used],
                "chosen_clip": {
                    "provider": c.provider,
                    "id": c.clip_id,
                    "url": c.clip_url,
                    "local_path": _to_rel(c.clip_path),
                    "start_trim_s": c.start_trim_s,
                    "end_trim_s": c.end_trim_s,
                    "score_breakdown": c.score_breakdown,
                },
            }
            for c in clips
        ],
        "audio": {
            "voice": str(voice_name or ""),
            "voice_gender": str(voice_gender or "male"),
            "voice_tone": str(voice_tone or "neutral"),
            "speech_speed": str(speech_speed or "normal"),
            "local_path": _to_rel(audio_path),
            "duration_s": round(sum(phrase_durations), 3),
        },
        "subtitles": {
            "mode": effective_subtitle_mode,
            "style": str(subtitle_style or settings.VIDEO_SUBTITLE_STYLE),
            "platform_target": effective_platform_target,
            "safe_area": str(subtitle_profile.get("safe_area") or ""),
            "caption_profile": subtitle_profile,
            "burned_enabled": burned_subtitles_enabled,
            "external_srt_enabled": external_srt_enabled,
            "local_path": (_to_rel(subtitles_path) if burned_subtitles_enabled else ""),
            "srt_local_path": (_to_rel(subtitles_srt_path) if subtitles_srt_path.exists() else ""),
            "chunks_count": subtitle_chunks_count,
        },
        "render": {
            "fps": 30,
            "resolution": "1080x1920" if orientation == "vertical" else "1920x1080",
            "out_path": _to_rel(out_video),
        },
        "clips": [
            {
                "shot_index": c.shot_index,
                "phrase_index": c.phrase_index,
                "clip_path": _to_rel(c.clip_path),
                "provider": c.provider,
                "clip_id": c.clip_id,
                "duration_target": c.duration_target,
                "query_used": c.query_used,
                "score": c.score,
                "score_breakdown": c.score_breakdown,
            }
            for c in clips
        ],
        "debug": {
            "unique_clips_used": unique_clips_used,
            "unique_clip_count": len({_clip_debug_entry(c)["clip_path"] for c in clips}),
            "selection": selection_diagnostics,
            "subtitle_mode": effective_subtitle_mode,
            "external_srt_generated": bool(subtitles_srt_path.exists()),
            "subtitle_safe_area": str(subtitle_profile.get("safe_area") or ""),
            "subtitle_style": str(subtitle_style or settings.VIDEO_SUBTITLE_STYLE),
            "quality_standard": {
                "avoid_duplicate_footage": bool(avoid_duplicate_footage),
                "diversity_mode": diversity_mode,
                "min_unique_clips_short": int(min_unique_clips_short),
                "allow_emergency_reuse": bool(allow_emergency_reuse),
                "related_keyword_expansion": bool(fallback_related_keywords),
                "platform_target": effective_platform_target,
                "niche_profile": str(niche_profile.get("id") or "generic"),
            },
        },
    }
    manifest_path = _manifest_path(job_id)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if callable(progress_callback):
        progress_callback("export", 92, "Экспорт и манифест готовы")

    return {
        "video_local_path": str(out_video),
        "video_url": _public_media_url(out_video),
        "audio_url": _public_media_url(Path(audio_path)),
        "subtitles_url": (_public_media_url(subtitles_path) if burned_subtitles_enabled else ""),
        "subtitles_srt_url": (_public_media_url(subtitles_srt_path) if subtitles_srt_path.exists() else ""),
        "manifest_url": _public_media_url(manifest_path),
        "phrases": list(script.phrases or []),
        "spoken_text": " ".join([str(x or "").strip() for x in (script.phrases or []) if str(x or "").strip()]).strip(),
        "title": script.title,
        "description": script.description,
        "hashtags": script.hashtags,
        "cta": cta_text,
        "safety_rules": script.safety_rules,
        "target_seconds": target_seconds,
        "style_pack_id": style_pack["id"],
        "realistic_only": bool(realistic_only),
        "voice_gender": str(voice_gender or "male"),
        "voice_tone": str(voice_tone or "neutral"),
        "voice_name": str(voice_name or ""),
        "speech_speed": str(speech_speed or "normal"),
        "debug": manifest.get("debug", {}),
    }

