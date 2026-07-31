"""Local footage library with repeat protection for mass Shorts production.

Responsibilities:
- register downloaded stock clips as FootageAsset (dedupe by provider id AND
  SHA-256 of the file — the same clip can come back under different URLs);
- pick candidates for a scene segment with scoring, cooldown rules and a
  reservation mechanism so parallel render jobs never pick the same asset;
- record FootageUsage after a successful render, release reservations on
  failure; expired reservations free themselves automatically.

Cooldown rules (env-configurable, see app_settings):
1. never twice inside one project;
2. same channel: FOOTAGE_SAME_CHANNEL_COOLDOWN_DAYS (default 30);
3. other channels: FOOTAGE_GLOBAL_COOLDOWN_DAYS (default 7);
4. when unique candidates run out: widen query -> synonyms -> broader topic ->
   local library of other clusters -> only then allow reuse (recorded with
   footage_reuse_reason / footage_reuse_age_days / footage_candidate_count).
"""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from app_models import FootageAsset, FootageUsage
from app_settings import settings

# Rule-based query expansion; no paid AI calls in the footage path.
_QUERY_SYNONYMS = {
    "candle": ["candlelight", "flame closeup", "burning candle dark"],
    "moon": ["full moon", "moonlight night", "lunar sky"],
    "night": ["dark night", "midnight", "night sky stars"],
    "mystic": ["misty forest", "foggy mountains", "candle flame closeup"],
    "fog": ["mist forest", "foggy morning", "haze mountains"],
    "sleep": ["person sleeping bedroom", "person awake night", "bedroom dark"],
    "ritual": ["ceremony candles", "person meditating nature", "hands old book"],
    "symbol": ["ancient carved symbols stone", "runes closeup", "old temple wall"],
    "tarot": ["tarot cards hands", "fortune telling table", "old cards closeup"],
    "crystal": ["crystal closeup", "gemstones", "quartz stone"],
}
# Real-scene fallbacks only — no abstract/CGI (the user wants nature/people, not
# "Windows-screensaver" motion graphics).
_BROAD_FALLBACKS = ["misty forest morning", "calm ocean waves", "starry night sky",
                    "person walking in nature"]


def query_variants(base_query: str, extra_terms: list[str] | None = None) -> list[str]:
    """Deterministic-ish expansion: base -> widened -> synonyms -> broad."""
    base = (base_query or "").strip()
    out: list[str] = []
    if base:
        out.append(base)
        words = [w for w in re.findall(r"[a-zA-Z]{3,}", base.lower())]
        if len(words) > 1:
            out.append(" ".join(words[:2]))          # widened (fewer words)
            out.append(words[0])
        for w in words:
            for syn in _QUERY_SYNONYMS.get(w, [])[:2]:
                out.append(syn)
    for t in (extra_terms or []):
        if t and t not in out:
            out.append(t)
    out.extend(_BROAD_FALLBACKS)
    seen, uniq = set(), []
    for q in out:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            uniq.append(q)
    return uniq


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_media(path: Path) -> dict:
    try:
        proc = subprocess.run(
            [settings.FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        info = json.loads(proc.stdout or "{}")
        v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        return {
            "duration": float(info.get("format", {}).get("duration") or 0.0),
            "width": int(v.get("width") or 0),
            "height": int(v.get("height") or 0),
        }
    except Exception:
        return {"duration": None, "width": None, "height": None}


def register_asset(db, *, provider: str, provider_asset_id: str, local_path: Path,
                   download_url: str = "", original_url: str = "",
                   search_query: str = "", author: str = "",
                   license_note: str = "") -> FootageAsset:
    """Idempotent registration; dedupes by (provider, id) and by file hash."""
    existing = (
        db.query(FootageAsset)
        .filter_by(provider=provider, provider_asset_id=str(provider_asset_id))
        .first()
    )
    if existing:
        if not existing.local_path or not Path(existing.local_path).exists():
            existing.local_path = str(local_path)
        return existing
    file_hash = sha256_file(local_path)
    by_hash = db.query(FootageAsset).filter_by(file_hash=file_hash).first()
    if by_hash:
        # Same file under a different provider id/URL: one asset, not two.
        return by_hash
    meta = probe_media(local_path)
    w, h = meta.get("width") or 0, meta.get("height") or 0
    asset = FootageAsset(
        provider=provider,
        provider_asset_id=str(provider_asset_id),
        original_url=original_url[:600] or None,
        download_url=download_url[:600] or None,
        local_path=str(local_path),
        file_hash=file_hash,
        duration=meta.get("duration"),
        width=w or None,
        height=h or None,
        orientation="vertical" if h > w else ("horizontal" if w else None),
        search_query=(search_query or "")[:300] or None,
        author=(author or "")[:200] or None,
        license_note=(license_note or "")[:200] or None,
    )
    db.add(asset)
    db.flush()
    return asset


# ------------------------------------------------------------- availability

def _release_expired_reservations(db) -> None:
    cutoff = datetime.utcnow() - timedelta(seconds=settings.FOOTAGE_RESERVATION_TTL_SECONDS)
    db.query(FootageAsset).filter(
        FootageAsset.reserved_by_job_id.isnot(None),
        FootageAsset.reserved_at < cutoff,
    ).update({"reserved_by_job_id": None, "reserved_at": None}, synchronize_session=False)


def _last_usage_map(db, asset_ids: list[int]) -> dict[int, list[FootageUsage]]:
    if not asset_ids:
        return {}
    rows = (
        db.query(FootageUsage)
        .filter(FootageUsage.footage_asset_id.in_(asset_ids))
        .order_by(FootageUsage.used_at.desc())
        .all()
    )
    out: dict[int, list[FootageUsage]] = {}
    for r in rows:
        out.setdefault(r.footage_asset_id, []).append(r)
    return out


def score_candidates(db, candidates: list[FootageAsset], *, channel_id: int,
                     project_id: int, job_id: int | None,
                     min_duration: float) -> list[tuple[float, FootageAsset, dict]]:
    """Returns (score, asset, debug) sorted best-first. Assets blocked by hard
    rules (used in this project / reserved by another job) get score None and
    are excluded."""
    now = datetime.utcnow()
    same_cd = timedelta(days=settings.FOOTAGE_SAME_CHANNEL_COOLDOWN_DAYS)
    global_cd = timedelta(days=settings.FOOTAGE_GLOBAL_COOLDOWN_DAYS)
    usages = _last_usage_map(db, [a.id for a in candidates])
    scored = []
    for a in candidates:
        debug = {"asset_id": a.id, "provider_asset_id": a.provider_asset_id}
        if a.reserved_by_job_id and a.reserved_by_job_id != job_id:
            debug["blocked"] = "reserved_by_other_job"
            continue
        a_usages = usages.get(a.id, [])
        if any(u.video_project_id == project_id for u in a_usages):
            debug["blocked"] = "used_in_this_project"
            continue
        score = 0.0
        if (a.orientation or "") == "vertical":
            score += 30
            debug["vertical"] = True
        if a.duration and a.duration >= min_duration:
            score += 15
        if (a.height or 0) >= 1080:
            score += 10
        same_ch = [u for u in a_usages if u.channel_id == channel_id]
        other_ch = [u for u in a_usages if u.channel_id != channel_id]
        cooldown_penalty = 0.0
        if same_ch and (now - same_ch[0].used_at) < same_cd:
            cooldown_penalty += 1000  # hard cooldown -> effectively excluded unless fallback
            debug["same_channel_cooldown"] = True
            debug["reuse_age_days"] = (now - same_ch[0].used_at).days
        if other_ch and (now - other_ch[0].used_at) < global_cd:
            cooldown_penalty += 500
            debug["global_cooldown"] = True
            debug.setdefault("reuse_age_days", (now - other_ch[0].used_at).days)
        score -= cooldown_penalty
        score -= min(20.0, float(a.total_use_count or 0) * 2.0)
        debug["use_count"] = a.total_use_count
        debug["score"] = round(score, 1)
        scored.append((score, a, debug))
    scored.sort(key=lambda x: -x[0])
    return scored


def reserve_asset(db, asset: FootageAsset, job_id: int) -> bool:
    """Atomic-enough reservation: UPDATE ... WHERE reserved_by_job_id IS NULL."""
    updated = (
        db.query(FootageAsset)
        .filter(FootageAsset.id == asset.id,
                (FootageAsset.reserved_by_job_id.is_(None)) | (FootageAsset.reserved_by_job_id == job_id))
        .update({"reserved_by_job_id": job_id, "reserved_at": datetime.utcnow()},
                synchronize_session=False)
    )
    db.commit()
    return bool(updated)


def release_job_reservations(db, job_id: int) -> None:
    db.query(FootageAsset).filter(FootageAsset.reserved_by_job_id == job_id).update(
        {"reserved_by_job_id": None, "reserved_at": None}, synchronize_session=False
    )
    db.commit()


def commit_usage(db, *, asset: FootageAsset, project_id: int, channel_id: int,
                 scene_id: int | None, start_time: float, duration: float,
                 search_query: str = "", reuse_reason: str | None = None) -> None:
    db.add(FootageUsage(
        footage_asset_id=asset.id,
        video_project_id=project_id,
        channel_id=channel_id,
        scene_id=scene_id,
        start_time=start_time,
        duration=duration,
        search_query=(search_query or "")[:300] or None,
        reuse_reason=(reuse_reason or None),
    ))
    asset.total_use_count = (asset.total_use_count or 0) + 1
    asset.last_used_at = datetime.utcnow()
    asset.reserved_by_job_id = None
    asset.reserved_at = None


def pick_local_candidates(db, *, query: str, channel_id: int, project_id: int,
                          job_id: int | None, min_duration: float,
                          limit: int = 30) -> list[tuple[float, FootageAsset, dict]]:
    """Library-first search: match assets whose search_query shares words with
    the query (cheap relevance), newest first, then score."""
    _release_expired_reservations(db)
    words = [w for w in re.findall(r"[a-zA-Zа-яА-ЯёЁ]{3,}", (query or "").lower())][:4]
    q = db.query(FootageAsset).filter(FootageAsset.local_path.isnot(None))
    rows = q.order_by(FootageAsset.created_at.desc()).limit(500).all()
    matched = []
    for a in rows:
        if not a.local_path or not Path(a.local_path).exists():
            continue
        hay = f"{a.search_query or ''}".lower()
        relevance = sum(1 for w in words if w in hay)
        if words and relevance == 0:
            continue
        matched.append((relevance, a))
    matched.sort(key=lambda x: -x[0])
    candidates = [a for _, a in matched[:limit]]
    scored = score_candidates(db, candidates, channel_id=channel_id,
                              project_id=project_id, job_id=job_id,
                              min_duration=min_duration)
    # add relevance to debug
    rel = {a.id: r for r, a in matched}
    for _, a, dbg in scored:
        dbg["local_relevance"] = rel.get(a.id, 0)
    return scored


def segment_plan(total_duration: float) -> list[float]:
    """Split a duration into equal visual segments of ~FOOTAGE_SEGMENT_SECONDS.

    Guarantees: sum(segments) == total (±0.01 via last-segment absorb), no
    segment shorter than a 0.8 s hard floor, and segments stay inside
    [min, max] whenever the total allows an equal split there; otherwise the
    closest-to-target equal split is chosen (never a tiny trailing segment)."""
    target = settings.FOOTAGE_SEGMENT_SECONDS
    lo, hi = settings.FOOTAGE_SEGMENT_MIN_SECONDS, settings.FOOTAGE_SEGMENT_MAX_SECONDS
    total = max(0.8, float(total_duration))
    if total <= hi:
        return [round(total, 2)]
    # candidate segment counts around total/target; prefer one that lands in
    # [lo, hi], otherwise the one closest to target (still equal-sized).
    import math
    base = total / target
    n_options = sorted({max(1, math.floor(base)), max(1, round(base)), math.ceil(base)})
    def _fitness(n):
        seg = total / n
        in_bounds = lo <= seg <= hi
        return (0 if in_bounds else 1, abs(seg - target))
    n = min(n_options, key=_fitness)
    seg = total / n
    segments = [round(seg, 2)] * n
    segments[-1] = round(total - sum(segments[:-1]), 2)
    if segments[-1] < 0.8 and n > 1:  # absorb a degenerate tail into neighbour
        tail = segments.pop()
        segments[-1] = round(segments[-1] + tail, 2)
    return segments


# --------------------------------------------- exhausted-search acquisition

def select_and_reserve(db, scored, job_id: int, used_asset_ids: set,
                       used_hashes: set):
    """Walk the scored list best-first; the first successful reservation wins.
    A failed reservation (parallel job grabbed it) moves on to the NEXT
    candidate - never proceeds with an unreserved asset."""
    for sc, a, dbg in scored:
        if a.id in used_asset_ids or (a.file_hash or "") in used_hashes:
            continue
        if reserve_asset(db, a, job_id):
            return sc, a, dbg
    return None, None, None


def acquire_segment_asset(db, *, query: str, channel_id: int, project_id: int,
                          job_id: int, min_duration: float,
                          used_asset_ids: set, used_hashes: set,
                          allow_network: bool = True,
                          visual_intent: dict | None = None) -> tuple[FootageAsset | None, dict]:
    """Full fallback chain before any reuse is allowed:
    1) local library across all query variants (original -> synonyms -> broad);
    2) Pexels across a bounded budget of queries x pages, downloading fresh
       unique clips (provider id + SHA-256 checked at registration);
    3) only after the budget is exhausted: cooldown-reuse fallback;
    4) last resort: reuse inside the search stats (reuse_was_unavoidable).
    Returns (asset_or_None, stats). The asset is already reserved."""
    stats = {
        "search_queries_attempted": 0,
        "pages_attempted": 0,
        "candidates_examined": 0,
        "candidates_rejected_cooldown": 0,
        "candidates_rejected_duplicate": 0,
        "candidates_rejected_visual": 0,
        "visual_checks": 0,
        "visual_degraded": False,
        "reuse_was_unavoidable": False,
        "source": None,
    }

    def _visual_ok(asset) -> bool:
        """Visual AI gate (cache-first). Rejected candidates are skipped and
        never become FootageUsage. Bounded by VISUAL_AI_MAX_CHECKS_PER_SEGMENT."""
        if not visual_intent or not settings.VISUAL_VALIDATION_ENABLED:
            return True
        if stats["visual_checks"] >= settings.VISUAL_AI_MAX_CHECKS_PER_SEGMENT:
            stats["visual_degraded"] = True
            return settings.VISUAL_VALIDATION_FAIL_OPEN
        from visual_validation import validate_asset
        stats["visual_checks"] += 1
        res = validate_asset(db, asset, visual_intent)
        if res.degraded:
            stats["visual_degraded"] = True
        if not res.accepted:
            stats["candidates_rejected_visual"] += 1
            return False
        return True
    variants = query_variants(query)[: max(2, settings.PEXELS_MAX_SEARCH_QUERIES_PER_SEGMENT)]
    cooldown_pool: list = []

    # --- stage 1: local library over every variant ---
    for v in variants:
        stats["search_queries_attempted"] += 1
        scored = pick_local_candidates(
            db, query=v, channel_id=channel_id, project_id=project_id,
            job_id=job_id, min_duration=min_duration,
        )
        stats["candidates_examined"] += len(scored)
        fresh, cooled = [], []
        for sc, a, dbg in scored:
            if a.id in used_asset_ids or (a.file_hash or "") in used_hashes:
                stats["candidates_rejected_duplicate"] += 1
                continue
            (fresh if sc > -400 else cooled).append((sc, a, dbg))
        stats["candidates_rejected_cooldown"] += len(cooled)
        cooldown_pool.extend(cooled)
        fresh = [(sc, a, dbg) for sc, a, dbg in fresh if _visual_ok(a)]
        sc, chosen, dbg = select_and_reserve(db, fresh, job_id, used_asset_ids, used_hashes)
        if chosen:
            stats["source"] = f"local:{v}"
            return chosen, stats

    # --- stage 2: Pexels network with bounded budget ---
    if allow_network:
        try:
            from footage.providers.pexels import download_video, search_videos
        except Exception:
            search_videos = None
        if search_videos:
            for v in variants:
                for page in range(1, settings.PEXELS_MAX_PAGES_PER_QUERY + 1):
                    stats["pages_attempted"] += 1
                    try:
                        results = search_videos(
                            query=v, orientation="vertical", min_duration=3,
                            max_duration=60,
                            limit=settings.PEXELS_CANDIDATES_PER_SEGMENT, page=page,
                        ) or search_videos(
                            query=v, orientation="horizontal", min_duration=3,
                            max_duration=60,
                            limit=settings.PEXELS_CANDIDATES_PER_SEGMENT, page=page,
                        )
                    except Exception:
                        continue
                    for r in results[: settings.PEXELS_CANDIDATES_PER_SEGMENT]:
                        stats["candidates_examined"] += 1
                        try:
                            saved = Path(download_video(
                                r, settings.FOOTAGE_CACHE_DIR / "stock" / f"pexels_{r.video_id}.mp4"))
                            if not saved.exists():
                                continue
                            asset = register_asset(
                                db, provider=r.provider,
                                provider_asset_id=str(r.video_id),
                                local_path=saved, download_url=r.download_url or "",
                                original_url=r.page_url or "", search_query=v,
                                author=r.author or "",
                                license_note="Pexels License (free to use)",
                            )
                            db.commit()
                        except Exception:
                            continue
                        if asset.id in used_asset_ids or (asset.file_hash or "") in used_hashes:
                            stats["candidates_rejected_duplicate"] += 1
                            continue
                        scored = score_candidates(
                            db, [asset], channel_id=channel_id,
                            project_id=project_id, job_id=job_id,
                            min_duration=min_duration,
                        )
                        if not scored:
                            stats["candidates_rejected_duplicate"] += 1
                            continue
                        sc, a, dbg = scored[0]
                        if sc <= -400:
                            stats["candidates_rejected_cooldown"] += 1
                            cooldown_pool.append((sc, a, dbg))
                            continue
                        if not _visual_ok(a):
                            continue
                        if reserve_asset(db, a, job_id):
                            stats["source"] = f"pexels:{v}:p{page}"
                            return a, stats

    # --- stage 3: search budget exhausted -> cooldown reuse fallback ---
    stats["reuse_was_unavoidable"] = True
    if settings.FOOTAGE_ALLOW_REUSE_FALLBACK and cooldown_pool:
        cooldown_pool.sort(key=lambda x: -x[0])
        sc, chosen, dbg = select_and_reserve(db, cooldown_pool, job_id, used_asset_ids, used_hashes)
        if chosen:
            stats["source"] = "cooldown_reuse"
            return chosen, stats
    return None, stats
