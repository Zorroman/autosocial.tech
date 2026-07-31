import logging
from dataclasses import dataclass
from pathlib import Path

from footage.providers.pexels import download_video as download_pexels_video
from footage.providers.pexels import search_videos as search_pexels_videos
from footage.providers.pixabay import download_video as download_pixabay_video
from footage.providers.pixabay import search_videos as search_pixabay_videos
from footage.ranking import (
    BANNED_TOKENS,
    SCENE_KEYWORDS,
    candidate_unique_key,
    is_rejected,
    near_duplicate,
    penalty_score,
    rank_candidates,
)
from footage.shots import ShotSpec
from footage.types import VideoResult
from saas_settings import settings
from style_packs import get_style_pack, normalize_scene


logger = logging.getLogger(__name__)

MIN_ACCEPT_SCORE = 58.0
MIN_ACCEPT_SEMANTIC = 0.18
MIN_ACCEPT_SCENE = 0.12


@dataclass
class MatchedClip:
    shot_index: int
    phrase_index: int
    phrase_text: str
    clip_path: str
    provider: str
    clip_id: str
    clip_url: str
    duration_target: float
    start_trim_s: float
    end_trim_s: float
    query_used: str
    score: float
    score_breakdown: dict


def _search_all(query: str, orientation: str, min_duration: int, max_duration: int, limit: int, page: int = 1) -> list[VideoResult]:
    if settings.USE_MOCK_PROVIDERS:
        return _mock_local_videos(query, orientation, limit, page=page)
    out = []
    out.extend(search_pexels_videos(query, orientation, min_duration, max_duration, limit, page=page))
    out.extend(search_pixabay_videos(query, orientation, min_duration, max_duration, limit, page=page))
    return out


def _mock_local_videos(query: str, orientation: str, limit: int, page: int = 1) -> list[VideoResult]:
    roots = [settings.FOOTAGE_CACHE_DIR, settings.BASE_DIR / "tmp_video_diag"]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(p for p in root.glob("*.mp4") if p.is_file() and p.stat().st_size > 64 * 1024))
    if not files:
        return []
    terms = [x for x in str(query or "").lower().replace("_", " ").replace("-", " ").split() if len(x) > 2]

    def score(path: Path) -> tuple[int, str]:
        name = path.stem.lower().replace("_", " ").replace("-", " ")
        return (-sum(1 for term in terms if term in name), name)

    ordered = sorted(files, key=score)
    per_page = max(1, int(limit or 8))
    start = (max(1, int(page or 1)) - 1) * per_page
    selected = [ordered[(start + idx) % len(ordered)] for idx in range(per_page)]
    vertical = str(orientation or "").lower() == "vertical"
    out: list[VideoResult] = []
    for idx, path in enumerate(selected, start=start):
        tags = [x for x in path.stem.replace("_", "-").split("-") if x]
        out.append(
            VideoResult(
                provider="safe_broll",
                video_id=f"{path.stem}-mock-{idx}",
                duration=8,
                width=1080 if vertical else 1920,
                height=1920 if vertical else 1080,
                page_url=f"local://mock/{idx}",
                download_url=str(path.resolve()),
                tags=[*tags, *(terms[:3]), f"variant{idx}"],
                orientation="vertical" if vertical else "horizontal",
                title=f"{str(query or '').strip()} {path.stem} variant {idx}".strip(),
                description="local_mock_footage_valid_mp4",
                author=f"local_mock_{idx}",
                shot_size="medium" if idx % 2 else "wide",
                motion_hint="motion" if idx % 2 else "static",
                source_query=str(query or "").strip(),
            )
        )
    return out


def _download(result: VideoResult) -> str:
    ext = ".mp4"
    target = Path(settings.FOOTAGE_CACHE_DIR) / f"{result.provider}_{result.video_id}{ext}"
    if result.provider == "pexels":
        return download_pexels_video(result, target)
    return download_pixabay_video(result, target)


def _safe_library_dir(orientation: str) -> Path:
    d = settings.CACHE_DIR / "safe_broll" / orientation
    d.mkdir(parents=True, exist_ok=True)
    return d


def _neutral_query_for_scene(scene: str) -> str:
    scene = str(scene or "").strip().lower()
    if scene == "work":
        return "office work"
    if scene == "city":
        return "city street"
    if scene == "nature":
        return "nature landscape"
    if scene == "product":
        return "hands holding product"
    if scene == "home":
        return "home interior"
    if scene == "people":
        return "people walking"
    return "real life broll"


def _metadata_text(candidate: VideoResult) -> str:
    return " ".join(
        [
            candidate.title or "",
            candidate.description or "",
            candidate.page_url or "",
            candidate.download_url or "",
            " ".join(candidate.tags or []),
            candidate.source_query or "",
        ]
    ).lower()


def _query_bucket(query: str, fallback: str = "generic") -> str:
    value = str(query or "").strip().lower()
    if not value:
        return str(fallback or "generic").strip().lower() or "generic"
    return value.split()[0]


def _candidate_in_allowed_scenes(candidate: VideoResult, allowed_scenes: set[str]) -> bool:
    if not allowed_scenes:
        return True
    hay = _metadata_text(candidate)
    if not hay.strip():
        return True
    for scene in allowed_scenes:
        keywords = SCENE_KEYWORDS.get(scene, set())
        if any(k in hay for k in keywords):
            return True
    return False


def _ensure_safe_library(orientation: str, allowed_scenes: set[str], spec: ShotSpec | None = None) -> list[VideoResult]:
    lib_dir = _safe_library_dir(orientation)
    niche_profile = str(getattr(spec, "niche_profile_id", "") or "").strip().lower()
    present = sorted([x for x in lib_dir.glob("*.mp4") if x.is_file()])
    if len(present) >= 20 and niche_profile in {"", "generic"}:
        return [
            VideoResult(
                provider="safe_broll",
                video_id=p.stem,
                duration=8,
                width=1080 if orientation == "vertical" else 1920,
                height=1920 if orientation == "vertical" else 1080,
                page_url="",
                download_url=str(p),
                tags=["safe", "neutral"],
                orientation=orientation,
                title=p.stem,
                description="safe_broll",
                author="safe_library",
                shot_size="medium",
                motion_hint="motion",
            )
            for p in present[:20]
        ]

    if niche_profile not in {"", "generic"} and spec is not None:
        neutral_queries = []
        for q in [*(spec.queries or []), *(spec.fallback_queries or []), *(spec.must_include or [])]:
            cur = str(q or "").strip()
            if cur and cur not in neutral_queries:
                neutral_queries.append(cur)
        neutral_queries = neutral_queries[:12]
    else:
        query_scenes = [s for s in allowed_scenes if s in {"work", "city", "nature", "people", "home", "product", "abstract_real"}]
        if not query_scenes:
            query_scenes = ["work", "city", "nature", "people"]
        neutral_queries = [_neutral_query_for_scene(s) for s in query_scenes]

    gathered: list[VideoResult] = []
    used = set()
    for q in neutral_queries:
        for page in range(1, 3):
            candidates = _search_all(q, orientation, 3, 20, 8, page=page)
            for c in candidates:
                cid = candidate_unique_key(c)
                if cid in used or is_rejected(c):
                    continue
                if not _candidate_in_allowed_scenes(c, allowed_scenes):
                    continue
                used.add(cid)
                gathered.append(c)
                if len(gathered) >= 20:
                    break
            if len(gathered) >= 20:
                break
        if len(gathered) >= 20:
            break

    out = []
    for idx, c in enumerate(gathered):
        local = _download(c)
        src = Path(local)
        dst = lib_dir / f"safe_{idx:03d}_{c.provider}_{c.video_id or idx}.mp4"
        if src.exists() and src.resolve() != dst.resolve() and not dst.exists():
            dst.write_bytes(src.read_bytes())
        out.append(
            VideoResult(
                provider="safe_broll",
                video_id=dst.stem,
                duration=max(3, int(c.duration or 8)),
                width=int(c.width or (1080 if orientation == "vertical" else 1920)),
                height=int(c.height or (1920 if orientation == "vertical" else 1080)),
                page_url=c.page_url,
                download_url=str(dst),
                tags=["safe", "neutral", *(c.tags or [])[:4]],
                orientation=orientation,
                title=c.title or dst.stem,
                description="safe_broll",
                author=c.author or "safe_library",
                shot_size=c.shot_size,
                motion_hint=c.motion_hint,
                source_query=c.source_query,
            )
        )
    return out


def _filter_duplicates(candidates: list[VideoResult], already_selected: dict, diagnostics: dict | None = None) -> list[VideoResult]:
    out = []
    seen = set()
    exact_duplicate_hits = 0
    near_duplicate_hits = 0
    for c in candidates:
        cid = candidate_unique_key(c)
        if cid in seen:
            exact_duplicate_hits += 1
            continue
        seen.add(cid)
        if cid in already_selected.get("ids", set()):
            exact_duplicate_hits += 1
            continue
        duplicate = False
        for old in already_selected.get("selected_results", []):
            if near_duplicate(c, old):
                duplicate = True
                break
        if duplicate:
            near_duplicate_hits += 1
            continue
        out.append(c)
    if isinstance(diagnostics, dict):
        diagnostics["duplicate_filtered"] = int(diagnostics.get("duplicate_filtered") or 0) + exact_duplicate_hits + near_duplicate_hits
        diagnostics["exact_duplicate_filtered"] = int(diagnostics.get("exact_duplicate_filtered") or 0) + exact_duplicate_hits
        diagnostics["near_duplicate_filtered"] = int(diagnostics.get("near_duplicate_filtered") or 0) + near_duplicate_hits
    return out


def _update_memory(chosen: VideoResult, query_used: str, spec: ShotSpec, already_selected: dict, score_breakdown: dict | None = None) -> None:
    already_selected.setdefault("ids", set()).add(candidate_unique_key(chosen))
    author = str(chosen.author or "").strip().lower()
    if author:
        already_selected.setdefault("authors", set()).add(author)
    sig = f"{chosen.title}|{' '.join(sorted(chosen.tags or []))}".lower()
    already_selected.setdefault("tag_signatures", []).append(sig)
    qkey = _query_bucket(query_used, spec.query_bucket)
    if qkey:
        groups = already_selected.setdefault("query_groups_used", {})
        groups[qkey] = int(groups.get(qkey, 0)) + 1
        already_selected.setdefault("recent_query_buckets", []).append(qkey)
        already_selected["recent_query_buckets"] = already_selected["recent_query_buckets"][-3:]
    if spec.query_bucket:
        already_selected.setdefault("recent_scene_keys", []).append(spec.query_bucket)
        already_selected["recent_scene_keys"] = already_selected["recent_scene_keys"][-3:]
    shot_size = str((chosen.shot_size or "")).strip().lower() or str((chosen.description or "")).strip().lower()
    if shot_size:
        already_selected.setdefault("recent_shot_sizes", []).append(shot_size)
        already_selected["recent_shot_sizes"] = already_selected["recent_shot_sizes"][-3:]
    motion_hint = str(chosen.motion_hint or "").strip().lower()
    if motion_hint:
        already_selected.setdefault("recent_motion_hints", []).append(motion_hint)
        already_selected["recent_motion_hints"] = already_selected["recent_motion_hints"][-3:]
    visual_bucket = str((score_breakdown or {}).get("visual_bucket") or spec.visual_bucket or "").strip().lower()
    if not visual_bucket:
        visual_bucket = str((spec.visual_bucket or spec.query_bucket or spec.desired_scene or "generic")).strip().lower()
    already_selected.setdefault("recent_visual_buckets", []).append(visual_bucket)
    already_selected["recent_visual_buckets"] = already_selected["recent_visual_buckets"][-3:]
    already_selected.setdefault("selected_results", []).append(chosen)


def _build_hard_tokens(spec: ShotSpec, style_pack: dict) -> list[str]:
    out = [*(BANNED_TOKENS or []), *((style_pack.get("banned_tokens") or [])), *((spec.must_exclude or []))]
    uniq = []
    for token in out:
        t = str(token or "").strip().lower()
        if t and t not in uniq:
            uniq.append(t)
    return uniq


def _build_soft_tokens(spec: ShotSpec, style_pack: dict) -> list[str]:
    out = [*((style_pack.get("soft_banned_tokens") or [])), *((spec.soft_exclude or []))]
    uniq = []
    for token in out:
        t = str(token or "").strip().lower()
        if t and t not in uniq:
            uniq.append(t)
    return uniq


def _build_query_order(spec: ShotSpec, style_pack: dict, allowed_scenes: set[str], fallback_related_keywords: bool = True) -> list[str]:
    desired = normalize_scene(spec.desired_scene, list(allowed_scenes))
    scene_overrides = style_pack.get("scene_query_overrides") if isinstance(style_pack.get("scene_query_overrides"), dict) else {}
    overrides = scene_overrides.get(desired) if isinstance(scene_overrides, dict) else []
    if isinstance(overrides, str):
        overrides = [overrides]
    override_queries = [str(x).strip() for x in (overrides or []) if str(x).strip()][:3]
    fallback_scene_queries = [_neutral_query_for_scene(desired)]
    query_order = [*spec.queries, *override_queries, *(spec.fallback_queries if fallback_related_keywords else []), *fallback_scene_queries]
    final = []
    for q in query_order:
        cur = str(q or "").strip()
        if cur and cur not in final:
            final.append(cur)
    return final


def _reselect_for_business_clean(
    spec: ShotSpec,
    candidate_pool: list[VideoResult],
    already_selected: dict,
    orientation: str,
    hard_tokens: list[str],
    soft_tokens: list[str],
) -> tuple[VideoResult | None, float, dict]:
    ranked = rank_candidates(
        spec,
        candidate_pool,
        already_selected=already_selected,
        orientation=orientation,
        hard_banned_tokens=hard_tokens,
        soft_banned_tokens=soft_tokens,
    )
    for item in ranked:
        if is_rejected(item.candidate, hard_banned_tokens=hard_tokens):
            continue
        if penalty_score(item.candidate, soft_banned_tokens=soft_tokens) > 0:
            continue
        return item.candidate, float(item.score), dict(item.breakdown or {})
    if ranked:
        return ranked[0].candidate, float(ranked[0].score), dict(ranked[0].breakdown or {})
    return None, 0.0, {}


def _is_ranked_good(best) -> bool:
    if not best:
        return False
    score = float(getattr(best, "score", 0.0) or 0.0)
    breakdown = dict(getattr(best, "breakdown", {}) or {})
    semantic = float(breakdown.get("semantic_relevance", 0.0) or 0.0)
    scene = float(breakdown.get("scene_match", 0.0) or 0.0)
    return score >= MIN_ACCEPT_SCORE and semantic >= MIN_ACCEPT_SEMANTIC and scene >= MIN_ACCEPT_SCENE


def _select_candidate(
    spec: ShotSpec,
    candidates: list[VideoResult],
    *,
    already_selected: dict,
    orientation: str,
    hard_tokens: list[str],
    soft_tokens: list[str],
    diversity_mode: str,
):
    ranked = rank_candidates(
        spec,
        candidates,
        already_selected=already_selected,
        orientation=orientation,
        hard_banned_tokens=hard_tokens,
        soft_banned_tokens=soft_tokens,
    )
    if not ranked:
        return None
    if str(diversity_mode or "").strip().lower() != "high":
        return ranked[0]
    recent_visual = list(already_selected.get("recent_visual_buckets", []) or [])[-2:]
    recent_query = list(already_selected.get("recent_query_buckets", []) or [])[-2:]
    preferred = []
    acceptable = []
    for item in ranked:
        bucket = str((item.breakdown or {}).get("visual_bucket") or "").strip().lower()
        query_bucket = str((item.breakdown or {}).get("query_bucket") or "").strip().lower()
        bucket_is_fresh = not bucket or bucket not in recent_visual
        query_is_fresh = not query_bucket or query_bucket not in recent_query
        if bucket_is_fresh and query_is_fresh:
            preferred.append(item)
        elif bucket_is_fresh or query_is_fresh:
            acceptable.append(item)
    if preferred:
        return preferred[0]
    if acceptable:
        return acceptable[0]
    return ranked[0]


def match_shots(
    shot_specs: list[ShotSpec],
    orientation: str,
    style_pack: dict | None = None,
    minimize_repeats: bool = True,
    initial_memory: dict | None = None,
    diagnostics: dict | None = None,
    avoid_duplicate_footage: bool = True,
    min_unique_clips_short: int = 8,
    fallback_related_keywords: bool = True,
    diversity_mode: str = "balanced",
    allow_emergency_reuse: bool = True,
) -> list[MatchedClip]:
    style_pack = get_style_pack((style_pack or {}).get("id") if isinstance(style_pack, dict) else None)
    allowed_scenes = set(style_pack.get("allowed_scenes") or [])
    seed = initial_memory if isinstance(initial_memory, dict) else {}
    already_selected = {
        "ids": set(seed.get("ids") or []),
        "authors": set(seed.get("authors") or []),
        "tag_signatures": list(seed.get("tag_signatures") or []),
        "query_groups_used": dict(seed.get("query_groups_used") or {}),
        "selected_results": list(seed.get("selected_results") or []),
        "recent_query_buckets": list(seed.get("recent_query_buckets") or []),
        "recent_scene_keys": list(seed.get("recent_scene_keys") or []),
        "recent_shot_sizes": list(seed.get("recent_shot_sizes") or []),
        "recent_motion_hints": list(seed.get("recent_motion_hints") or []),
        "recent_visual_buckets": list(seed.get("recent_visual_buckets") or []),
    }
    diag = diagnostics if isinstance(diagnostics, dict) else {}
    diag.setdefault("keywords_used", [])
    diag.setdefault("duplicate_filtered", 0)
    diag.setdefault("exact_duplicate_filtered", 0)
    diag.setdefault("near_duplicate_filtered", 0)
    diag.setdefault("found_clips", 0)
    diag.setdefault("unique_selected", 0)
    diag.setdefault("reuse_fallback", False)
    diag.setdefault("fallback_steps", [])
    diag.setdefault("warnings", [])
    diag.setdefault("timeline_segment_count", len(shot_specs))
    diag.setdefault("niche_profile", "")
    diag.setdefault("diversity_mode", str(diversity_mode or "balanced"))
    matches: list[MatchedClip] = []
    expected_unique = max(int(min_unique_clips_short or 8), len(shot_specs)) if orientation == "vertical" else len(shot_specs)

    for shot_index, spec in enumerate(shot_specs):
        candidate_pool: list[VideoResult] = []
        raw_pool: list[VideoResult] = []
        rejected_count = 0
        duplicate_before_filter = 0
        used_query = ""
        spec.desired_scene = normalize_scene(spec.desired_scene, list(allowed_scenes))
        hard_tokens = _build_hard_tokens(spec, style_pack)
        soft_tokens = _build_soft_tokens(spec, style_pack)
        query_order = _build_query_order(spec, style_pack, allowed_scenes, fallback_related_keywords=fallback_related_keywords)
        primary_queries = [q for q in query_order if q in (spec.queries or [])]
        expanded_queries = [q for q in query_order if q not in primary_queries]
        ordered_query_stages = [
            ("current_pool", primary_queries),
            ("related_keywords", expanded_queries),
        ]
        target_pool = 16 if str(diversity_mode or "").strip().lower() == "high" and orientation == "vertical" else (12 if orientation == "vertical" else 8)

        for stage_name, stage_queries in ordered_query_stages:
            if not stage_queries:
                continue
            if stage_name not in diag["fallback_steps"]:
                diag["fallback_steps"].append(stage_name)
            for query in stage_queries:
                q = str(query or "").strip()
                if not q:
                    continue
                qlow = q.lower()
                if any(tok in qlow for tok in hard_tokens):
                    continue
                bucket = _query_bucket(q, spec.query_bucket)
                if bucket in diag["keywords_used"] and len(candidate_pool) >= target_pool:
                    continue
                diag["keywords_used"].append(bucket)
                used_query = q
                for page in range(1, 4):
                    if page > 1 and "next_pages" not in diag["fallback_steps"]:
                        diag["fallback_steps"].append("next_pages")
                    fetched = _search_all(
                        query=q,
                        orientation=orientation,
                        min_duration=max(2, int(spec.duration_s) - 1),
                        max_duration=max(8, int(spec.duration_s) + 30),
                        limit=12,
                        page=page,
                    )
                    diag["found_clips"] = int(diag.get("found_clips") or 0) + len(fetched)
                    rejected_count += sum(1 for x in fetched if is_rejected(x, hard_banned_tokens=hard_tokens))
                    clean = [x for x in fetched if not is_rejected(x, hard_banned_tokens=hard_tokens)]
                    if allowed_scenes:
                        clean = [x for x in clean if _candidate_in_allowed_scenes(x, allowed_scenes)]
                    raw_pool.extend(clean)
                    filtered = _filter_duplicates(clean, already_selected, diag) if (minimize_repeats and avoid_duplicate_footage) else list(clean)
                    duplicate_before_filter += max(0, len(clean) - len(filtered))
                    candidate_pool.extend(filtered)
                    candidate_pool = _filter_duplicates(candidate_pool, {**already_selected, "selected_results": []}, diag)
                    best = _select_candidate(
                        spec,
                        candidate_pool,
                        already_selected=already_selected,
                        orientation=orientation,
                        hard_tokens=hard_tokens,
                        soft_tokens=soft_tokens,
                        diversity_mode=diversity_mode,
                    )
                    if best and _is_ranked_good(best) and len(candidate_pool) >= min(4, target_pool):
                        break
                    if len(candidate_pool) >= target_pool:
                        break
                best = _select_candidate(
                    spec,
                    candidate_pool,
                    already_selected=already_selected,
                    orientation=orientation,
                    hard_tokens=hard_tokens,
                    soft_tokens=soft_tokens,
                    diversity_mode=diversity_mode,
                )
                if best and _is_ranked_good(best) and len(candidate_pool) >= min(4, target_pool):
                    break
            best = _select_candidate(
                spec,
                candidate_pool,
                already_selected=already_selected,
                orientation=orientation,
                hard_tokens=hard_tokens,
                soft_tokens=soft_tokens,
                diversity_mode=diversity_mode,
            )
            if best and _is_ranked_good(best) and len(candidate_pool) >= min(4, target_pool):
                break

        best = _select_candidate(
            spec,
            candidate_pool,
            already_selected=already_selected,
            orientation=orientation,
            hard_tokens=hard_tokens,
            soft_tokens=soft_tokens,
            diversity_mode=diversity_mode,
        )
        if best and not _is_ranked_good(best):
            logger.info(
                "shot %s: best clip below strict threshold score=%s semantic=%s scene=%s; keep provider clip for better topical relevance",
                shot_index,
                best.score,
                (best.breakdown or {}).get("semantic_relevance"),
                (best.breakdown or {}).get("scene_match"),
            )
        chosen = best.candidate if best else None
        score = float(best.score) if best else 0.0
        score_breakdown = dict(best.breakdown or {}) if best else {}

        if str(style_pack.get("id") or "") == "business_clean" and chosen:
            bad = is_rejected(chosen, hard_banned_tokens=hard_tokens) or penalty_score(chosen, soft_banned_tokens=soft_tokens) > 0
            if bad:
                logger.info("shot %s: business_clean reselect due to banned/soft token clip=%s:%s", shot_index, chosen.provider, chosen.video_id)
                alt_clip, alt_score, alt_breakdown = _reselect_for_business_clean(
                    spec,
                    candidate_pool,
                    already_selected=already_selected,
                    orientation=orientation,
                    hard_tokens=hard_tokens,
                    soft_tokens=soft_tokens,
                )
                if alt_clip:
                    chosen = alt_clip
                    score = alt_score
                    score_breakdown = alt_breakdown

        if not chosen:
            if "safe_library" not in diag["fallback_steps"]:
                diag["fallback_steps"].append("safe_library")
            safe_pool = _ensure_safe_library(orientation, allowed_scenes=allowed_scenes, spec=spec)
            safe_pool = _filter_duplicates(safe_pool, already_selected, diag) if (minimize_repeats and avoid_duplicate_footage) else list(safe_pool)
            best = _select_candidate(
                spec,
                safe_pool,
                already_selected=already_selected,
                orientation=orientation,
                hard_tokens=hard_tokens,
                soft_tokens=soft_tokens,
                diversity_mode=diversity_mode,
            )
            if best:
                chosen = best.candidate
                score = float(best.score)
                score_breakdown = dict(best.breakdown or {})

        if not chosen and raw_pool and allow_emergency_reuse:
            diag["reuse_fallback"] = True
            if "emergency_reuse" not in diag["fallback_steps"]:
                diag["fallback_steps"].append("emergency_reuse")
            warning = f"shot_{shot_index}: unique pool exhausted, reuse fallback enabled"
            diag.setdefault("warnings", []).append(warning)
            logger.warning(warning)
            best = _select_candidate(
                spec,
                raw_pool,
                already_selected={**already_selected, "ids": set(), "selected_results": []},
                orientation=orientation,
                hard_tokens=hard_tokens,
                soft_tokens=soft_tokens,
                diversity_mode=diversity_mode,
            )
            if best:
                chosen = best.candidate
                score = float(best.score)
                score_breakdown = dict(best.breakdown or {})

        if not chosen:
            raise RuntimeError(f"footage_not_found_for_shot_{shot_index}")

        clip_path = chosen.download_url if chosen.provider == "safe_broll" else _download(chosen)
        if minimize_repeats and avoid_duplicate_footage:
            _update_memory(chosen, used_query, spec, already_selected, score_breakdown=score_breakdown)
        end_trim = max(0.8, float(spec.duration_s))
        matches.append(
            MatchedClip(
                shot_index=shot_index,
                phrase_index=spec.phrase_index,
                phrase_text=spec.phrase_text,
                clip_path=str(Path(clip_path).resolve()),
                provider=chosen.provider,
                clip_id=chosen.video_id,
                clip_url=chosen.download_url,
                duration_target=float(spec.duration_s),
                start_trim_s=0.0,
                end_trim_s=end_trim,
                query_used=used_query,
                score=score,
                score_breakdown=score_breakdown,
            )
        )
        diag["unique_selected"] = len({candidate_unique_key(x) for x in already_selected.get("selected_results", [])})
        logger.info(
            "shot %s: query='%s' candidates=%s raw=%s duplicates_filtered=%s rejected=%s best=%s:%s score=%s bucket=%s",
            shot_index,
            used_query,
            len(candidate_pool),
            len(raw_pool),
            duplicate_before_filter,
            rejected_count,
            chosen.provider,
            chosen.video_id,
            score,
            spec.query_bucket,
        )

    if expected_unique > 0 and diag.get("unique_selected", 0) < expected_unique:
        warning = f"unique_clips_below_threshold:{diag.get('unique_selected', 0)}/{expected_unique}"
        diag.setdefault("warnings", []).append(warning)
        logger.warning(warning)
    visual_buckets = [str((m.score_breakdown or {}).get("visual_bucket") or "").strip().lower() for m in matches if str((m.score_breakdown or {}).get("visual_bucket") or "").strip()]
    shot_sizes = [str((m.score_breakdown or {}).get("shot_size") or "").strip().lower() for m in matches if str((m.score_breakdown or {}).get("shot_size") or "").strip()]
    motion_hints = [str((m.score_breakdown or {}).get("motion_hint") or "").strip().lower() for m in matches if str((m.score_breakdown or {}).get("motion_hint") or "").strip()]
    max_visual_run = 1
    current_visual_run = 1
    for idx in range(1, len(visual_buckets)):
        if visual_buckets[idx] == visual_buckets[idx - 1]:
            current_visual_run += 1
            max_visual_run = max(max_visual_run, current_visual_run)
        else:
            current_visual_run = 1
    diag["visual_bucket_counts"] = {k: visual_buckets.count(k) for k in sorted(set(visual_buckets))}
    diag["shot_size_counts"] = {k: shot_sizes.count(k) for k in sorted(set(shot_sizes))}
    diag["motion_hint_counts"] = {k: motion_hints.count(k) for k in sorted(set(motion_hints))}
    diag["weak_diversity"] = bool(
        (orientation == "vertical" and len(set(visual_buckets)) < 2 and len(set(shot_sizes)) < 2)
        or max_visual_run >= 3
    )
    return matches

