"""AI Content Director — the decision brain of the content factory.

It decides WHAT to film next and WHY. It never writes the script, never
renders and never publishes: it produces a DirectorStrategy (pillar -> topic ->
angle -> hook -> outline) which the existing Script Generator consumes.

Decision pipeline (each stage records its reasoning):
  1. pillar selection      — weighted rotation + recency + daily limit + performance
  2. topic ideation        — AI when available, deterministic heuristic otherwise
  3. duplicate protection  — normalized titles, token similarity, cooldown, bans
  4. angle selection       — best framing for the topic given recent angle usage
  5. hook creation         — the literal first sentence of the video
  6. outline               — structural plan (not a script)
  7. handoff               — approved strategy -> VideoProject for the writer

Everything is explainable: every strategy stores decision_json with the
candidate scores and the human-readable reasons behind the choice.
Works with or without analytics; works with or without an AI provider.
"""
import json
import re
from datetime import datetime, timedelta

from app_models import (
    Channel,
    ContentNiche,
    ContentPerformance,
    ContentPillar,
    DirectorStrategy,
    VideoProject,
)
from app_settings import settings

# ----------------------------------------------------------------- helpers

_STOPWORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "只", "the", "a", "an", "of", "to", "is", "why", "what", "how",
    "почему", "это", "для", "или", "если", "чем", "про",
}


def normalize_title(title: str) -> str:
    """Order-independent keyword signature of a title."""
    t = re.sub(r"[^\w\s]", " ", (title or "").lower())
    words = [w for w in t.split() if len(w) > 2 and w not in _STOPWORDS]
    return " ".join(sorted(set(words)))[:300]


def similarity(a: str, b: str) -> float:
    """Jaccard-style token overlap of two titles (0..1)."""
    wa = set(normalize_title(a).split())
    wb = set(normalize_title(b).split())
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    return round(inter / max(1, min(len(wa), len(wb))), 3)


def _split_seeds(raw: str) -> list[str]:
    return [s.strip() for s in re.split(r"[;,\n]", raw or "") if s.strip()]


# ------------------------------------------------------------- analytics

def channel_analytics(db, channel_id: int) -> dict:
    """Aggregated realized performance for a channel. Returns has_data=False
    when nothing is recorded — the Director then decides without analytics."""
    rows = (
        db.query(ContentPerformance)
        .filter(ContentPerformance.channel_id == channel_id)
        .all()
    )
    if not rows:
        return {"has_data": False, "videos": 0, "avg_ctr": None,
                "avg_retention": None, "avg_views": None, "per_pillar": {}}

    def _avg(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    per_pillar: dict[int, dict] = {}
    for r in rows:
        if r.pillar_id is None:
            continue
        b = per_pillar.setdefault(r.pillar_id, {"ctr": [], "retention": [], "views": []})
        b["ctr"].append(r.ctr)
        b["retention"].append(r.retention)
        b["views"].append(r.views)
    per_pillar_avg = {
        pid: {"avg_ctr": _avg(b["ctr"]), "avg_retention": _avg(b["retention"]),
              "avg_views": _avg(b["views"]), "videos": len(b["views"])}
        for pid, b in per_pillar.items()
    }
    return {
        "has_data": True,
        "videos": len(rows),
        "avg_ctr": _avg([r.ctr for r in rows]),
        "avg_retention": _avg([r.retention for r in rows]),
        "avg_views": _avg([r.views for r in rows]),
        "per_pillar": per_pillar_avg,
    }


# ------------------------------------------------- stage 1: pillar choice

def select_pillar(db, channel: Channel, *, now=None, analytics: dict | None = None):
    """Deliberate (not random) pillar choice.

    score = weight
          - recency_penalty (recently produced pillars step back)
          + performance_bonus (pillars that historically perform better)
    Pillars that are inactive or at their daily limit are excluded.
    Returns (pillar, debug) where debug explains every candidate.
    """
    now = now or datetime.utcnow()
    analytics = analytics if analytics is not None else channel_analytics(db, channel.id)
    debug = {"candidates": [], "excluded": [], "analytics_used": analytics["has_data"]}
    if not channel.niche_id:
        return None, {**debug, "error": "channel_has_no_niche"}

    pillars = db.query(ContentPillar).filter_by(niche_id=channel.niche_id, active=True).all()
    if not pillars:
        return None, {**debug, "error": "no_active_pillars"}

    day_start = now - timedelta(days=1)
    today_counts: dict[int, int] = {}
    for (pid,) in (
        db.query(VideoProject.content_pillar_id)
        .filter(VideoProject.channel_id == channel.id,
                VideoProject.created_at >= day_start,
                VideoProject.content_pillar_id.isnot(None)).all()
    ):
        today_counts[pid] = today_counts.get(pid, 0) + 1

    # recency: how many strategies back was this pillar last used
    recent = (
        db.query(DirectorStrategy)
        .filter(DirectorStrategy.channel_id == channel.id)
        .order_by(DirectorStrategy.created_at.desc()).limit(10).all()
    )
    last_positions: dict[int, int] = {}
    for idx, s in enumerate(recent):
        if s.pillar_id is not None and s.pillar_id not in last_positions:
            last_positions[s.pillar_id] = idx  # 0 = most recent

    avg_ctr = analytics.get("avg_ctr")
    best = None
    for p in pillars:
        used_today = today_counts.get(p.id, 0)
        if p.daily_video_limit and used_today >= p.daily_video_limit:
            debug["excluded"].append({"pillar": p.name, "reason": "daily_limit_reached",
                                      "used_today": used_today, "limit": p.daily_video_limit})
            continue
        base = float(max(0, p.weight or 0))
        if base <= 0:
            debug["excluded"].append({"pillar": p.name, "reason": "zero_weight"})
            continue

        reasons = [f"base weight {int(base)}"]
        score = base

        pos = last_positions.get(p.id)
        recency_penalty = 0.0
        if pos is not None:
            # most recent pillar penalized hardest, decaying with distance
            recency_penalty = base * settings.DIRECTOR_PILLAR_RECENCY_PENALTY / (pos + 1)
            score -= recency_penalty
            reasons.append(f"recency -{recency_penalty:.1f} (used {pos + 1} strategies ago)")
        else:
            reasons.append("not used recently (+diversity)")

        perf_bonus = 0.0
        pstats = (analytics.get("per_pillar") or {}).get(p.id)
        if analytics["has_data"] and pstats and pstats.get("avg_ctr") is not None and avg_ctr:
            delta = (pstats["avg_ctr"] - avg_ctr) / max(avg_ctr, 1e-6)
            perf_bonus = base * settings.DIRECTOR_ANALYTICS_WEIGHT * max(-1.0, min(1.0, delta))
            score += perf_bonus
            reasons.append(
                f"historical CTR {pstats['avg_ctr']:.3f} vs channel {avg_ctr:.3f} "
                f"-> {perf_bonus:+.1f}"
            )
        elif not analytics["has_data"]:
            reasons.append("no analytics yet (weights + rotation only)")

        cand = {"pillar_id": p.id, "pillar": p.name, "score": round(score, 2),
                "base_weight": int(base), "recency_penalty": round(recency_penalty, 2),
                "performance_bonus": round(perf_bonus, 2),
                "used_today": used_today, "reasons": reasons}
        debug["candidates"].append(cand)
        if best is None or score > best[0]:
            best = (score, p, cand)

    debug["candidates"].sort(key=lambda c: -c["score"])
    if best is None:
        return None, {**debug, "error": "all_pillars_exhausted"}
    debug["chosen"] = best[2]
    return best[1], debug


# ------------------------------------------------- stage 2: topic ideation

# Case-safe templates: the seed always stays in its original (nominative)
# form before a colon or dash, so no Russian case agreement is required.
_HEURISTIC_TEMPLATES = [
    "{seed}: что это значит",
    "{seed}: три трактовки",
    "{seed}: скрытый смысл",
    "{seed} — совпадение или знак",
    "{seed}: что говорит традиция",
    "{seed}: почему это повторяется",
]


def _heuristic_candidates(pillar: ContentPillar, count: int, offset: int = 0) -> list[dict]:
    """Deterministic ideation from the pillar's own allowed_topics.

    Used when no AI provider is configured (or DIRECTOR_USE_AI=false), so the
    Director always produces real, varied ideas offline. `offset` (derived from
    how much this channel already produced) rotates both the seed and the
    phrasing, so successive runs do not all read the same way.
    """
    seeds = _split_seeds(pillar.allowed_topics) or _split_seeds(pillar.description) or [pillar.name]
    out = []
    for i in range(count):
        seed = seeds[(i + offset) % len(seeds)]
        template = _HEURISTIC_TEMPLATES[(i + offset) % len(_HEURISTIC_TEMPLATES)]
        title = template.format(seed=seed)
        title = title[:1].upper() + title[1:] if title else title
        out.append({"topic": title, "seed": seed, "source": "heuristic"})
    return out


def _ai_candidates(pillar: ContentPillar, niche: ContentNiche, channel: Channel,
                   language: str, recent_titles: list[str], count: int):
    """AI ideation. Returns (candidates, error). Never raises."""
    try:
        from openai_client import OpenAIClientError, generate_json_with_retry, is_openai_enabled
    except Exception as exc:
        return [], f"openai_client_unavailable: {exc}"
    if not is_openai_enabled():
        return [], "openai_not_configured"

    def _validate(payload: dict) -> None:
        ideas = payload.get("ideas")
        if not isinstance(ideas, list) or not ideas:
            raise ValueError("ideas must be a non-empty list")

    system_prompt = (
        "You are a YouTube Shorts producer choosing what to film next for one channel. "
        'Return JSON {"ideas":[{"topic","seed"}]} with short, concrete, curiosity-driven '
        "topics for the given content pillar. Write in the requested language. "
        "Speculative practices must be framed as tradition/belief, never proven fact. "
        "Avoid the recent topics listed. Prefer concrete, actionable topics (how to "
        "attract/choose/recognize a specific thing) over abstract philosophical framing "
        "('what is karma', 'signs from the universe' as a vague general theme) -- on this "
        "channel, concrete topics have measurably driven more subscriber growth."
    )
    user_prompt = json.dumps({
        "niche": niche.name if niche else None,
        "pillar": pillar.name,
        "pillar_topics": pillar.allowed_topics,
        "forbidden_topics": pillar.forbidden_topics,
        "language": language,
        "target_audience": channel.target_audience,
        "recent_topics": recent_titles,
        "count": count,
    }, ensure_ascii=False)
    try:
        res = generate_json_with_retry(
            system_prompt=system_prompt, user_prompt=user_prompt,
            validator=_validate, max_output_tokens=700, temperature=0.9,
        )
    except OpenAIClientError as exc:
        return [], f"ai_failed: {str(exc)[:160]}"
    except Exception as exc:
        return [], f"ai_error: {str(exc)[:160]}"
    ideas = (res.payload or {}).get("ideas") or []
    out = []
    for it in ideas[:count]:
        topic = str((it or {}).get("topic") or "").strip()
        if topic:
            out.append({"topic": topic, "seed": str((it or {}).get("seed") or "").strip(),
                        "source": "ai"})
    return out, None


# --------------------------------------- stage 3: duplicate / ban protection

def topic_history(db, channel_id: int, *, cooldown_days: int | None = None) -> list[DirectorStrategy]:
    cutoff = datetime.utcnow() - timedelta(days=cooldown_days or settings.TOPIC_COOLDOWN_DAYS)
    return (
        db.query(DirectorStrategy)
        .filter(DirectorStrategy.channel_id == channel_id,
                DirectorStrategy.created_at >= cutoff)
        .order_by(DirectorStrategy.created_at.desc()).limit(200).all()
    )


def banned_signatures(db, channel_id: int) -> set:
    """Topics the admin explicitly banned are never proposed again."""
    rows = (
        db.query(DirectorStrategy)
        .filter(DirectorStrategy.channel_id == channel_id,
                DirectorStrategy.status.in_(["banned", "rejected"]))
        .all()
    )
    return {r.normalized_topic for r in rows if r.normalized_topic}


def duplicate_check(db, channel_id: int, topic: str, *, history=None,
                    banned=None) -> dict:
    """Returns {duplicate: bool, score: float, reason, closest}."""
    history = history if history is not None else topic_history(db, channel_id)
    banned = banned if banned is not None else banned_signatures(db, channel_id)
    sig = normalize_title(topic)
    if sig and sig in banned:
        return {"duplicate": True, "score": 1.0, "reason": "explicitly_banned", "closest": topic}
    best_score, closest = 0.0, None
    for s in history:
        sc = similarity(topic, s.selected_topic or "")
        if sc > best_score:
            best_score, closest = sc, s.selected_topic
    # exact normalized match is always a duplicate
    if closest and normalize_title(closest) == sig and sig:
        return {"duplicate": True, "score": 1.0, "reason": "exact_repeat", "closest": closest}
    dup = best_score >= settings.DIRECTOR_DUPLICATE_THRESHOLD
    return {
        "duplicate": dup, "score": best_score, "closest": closest,
        "reason": "too_similar_to_recent" if dup else "unique_enough",
    }


# ------------------------------------------------- stage 4: angle selection

ANGLES = [
    {"name": "Эзотерическая трактовка", "slug": "esoteric", "educational": 0.5, "entertainment": 0.8},
    {"name": "Психологическое объяснение", "slug": "psychological", "educational": 0.9, "entertainment": 0.5},
    {"name": "Миф против фактов", "slug": "myth_vs_facts", "educational": 0.85, "entertainment": 0.7},
    {"name": "Три версии", "slug": "three_versions", "educational": 0.7, "entertainment": 0.75},
    {"name": "Почему это повторяется", "slug": "why_recurring", "educational": 0.6, "entertainment": 0.8},
    {"name": "Самый необычный случай", "slug": "unusual_case", "educational": 0.4, "entertainment": 0.95},
]


def select_angle(db, channel_id: int, topic: str, *, history=None) -> tuple[dict, dict]:
    """Pick the angle least used recently, so consecutive videos differ in
    framing even inside the same pillar."""
    history = history if history is not None else topic_history(db, channel_id)
    recent_angles = [s.selected_angle for s in history[:6] if s.selected_angle]
    scored = []
    for a in ANGLES:
        penalty = 0.0
        if a["name"] in recent_angles:
            penalty = 1.0 / (recent_angles.index(a["name"]) + 1)
        score = round(1.0 - penalty, 3)
        scored.append({"angle": a["name"], "slug": a["slug"], "score": score,
                       "recently_used": a["name"] in recent_angles})
    scored.sort(key=lambda x: -x["score"])
    chosen_slug = scored[0]["slug"]
    chosen = next(a for a in ANGLES if a["slug"] == chosen_slug)
    return chosen, {"candidates": scored, "chosen": chosen["name"],
                    "recent_angles": recent_angles}


# ---------------------------------------------------- stage 5: hook design

# The subject leads the sentence and is followed by punctuation, so the
# templates stay grammatical for any noun phrase (no morphology needed).
_HOOK_TEMPLATES = {
    "esoteric": "{subject}. В эзотерической традиции это считают не случайностью...",
    "psychological": "{subject}. Психологи объясняют это совсем иначе, чем принято думать...",
    "myth_vs_facts": "{subject}. Что здесь миф, а что — правда?",
    "three_versions": "{subject}. Есть как минимум три разных объяснения...",
    "why_recurring": "{subject}. Почему это повторяется снова и снова?",
    "unusual_case": "{subject}. Один случай до сих пор не смогли объяснить...",
}


def build_hook(topic: str, angle: dict, seed: str = "") -> tuple[str, float]:
    """The literal first sentence of the video + a hook-strength estimate."""
    subject = (seed or "").strip()
    if not subject:
        # take the part before ':' / '—' from the topic
        subject = re.split(r"[:\-—]", (topic or ""), maxsplit=1)[0].strip() or (topic or "")
    subject = subject[:1].upper() + subject[1:] if subject else subject
    hook = _HOOK_TEMPLATES.get(angle["slug"], _HOOK_TEMPLATES["why_recurring"]).format(subject=subject)
    # strength heuristics: curiosity gap, personal address, brevity
    strength = 0.5
    if any(w in hook.lower() for w in ("почему", "не случайн", "не объяснил", "миф")):
        strength += 0.2
    if "?" in hook or "..." in hook:
        strength += 0.15
    if len(hook) <= 110:
        strength += 0.1
    return hook, round(min(1.0, strength), 3)


# ------------------------------------------------- stage 6: outline design

def build_outline(topic: str, angle: dict, hook: str) -> dict:
    """Structural plan only — the writer turns this into the actual script."""
    return {
        "structure": [
            {"part": "hook", "goal": "остановить пролистывание", "text_hint": hook},
            {"part": "intrigue", "goal": "обозначить загадку, не раскрывая ответ"},
            {"part": "main_idea", "goal": f"основная мысль по теме «{topic}»"},
            {"part": "two_versions", "goal": f"две трактовки в рамках угла «{angle['name']}»"},
            {"part": "conclusion", "goal": "короткий понятный вывод без гарантий и обещаний"},
            {"part": "cta", "goal": "мягкий призыв: наблюдать за собой / досмотреть / подписаться"},
        ],
        "angle": angle["name"],
        "angle_slug": angle["slug"],
        "topic": topic,
    }


# --------------------------------------------------------- candidate scoring

def score_candidate(cand: dict, *, dup: dict, angle: dict, hook_strength: float,
                    pillar: ContentPillar, analytics: dict) -> dict:
    """Explainable 0..1 sub-scores + integer priority."""
    novelty = round(max(0.0, 1.0 - dup["score"]), 3)
    # more visual keywords on the pillar => easier to film well
    vis_kw = len(_split_seeds(pillar.visual_keywords))
    visual_potential = round(min(1.0, 0.4 + 0.06 * vis_kw), 3)
    competition = round(min(1.0, 0.3 + 0.1 * len((cand.get("topic") or "").split())), 3)
    educational = angle["educational"]
    entertainment = angle["entertainment"]

    est_ctr = 0.04 + 0.05 * hook_strength + 0.02 * novelty
    est_retention = 0.35 + 0.2 * entertainment + 0.1 * visual_potential
    if analytics.get("has_data"):
        pstats = (analytics.get("per_pillar") or {}).get(pillar.id) or {}
        if pstats.get("avg_ctr"):
            est_ctr = (est_ctr + pstats["avg_ctr"]) / 2
        if pstats.get("avg_retention"):
            est_retention = (est_retention + pstats["avg_retention"]) / 2

    priority = int(round(100 * (
        0.35 * novelty + 0.25 * hook_strength + 0.2 * visual_potential
        + 0.1 * entertainment + 0.1 * educational
    )))
    return {
        "novelty_score": novelty,
        "visual_potential": visual_potential,
        "competition_score": competition,
        "educational_value": educational,
        "entertainment_value": entertainment,
        "hook_strength": hook_strength,
        "estimated_ctr": round(min(0.35, est_ctr), 4),
        "estimated_retention": round(min(0.95, est_retention), 4),
        "priority": max(1, min(100, priority)),
    }


# -------------------------------------------------------------- the decision

def decide(db, channel: Channel, *, pillar_id: int | None = None,
           now=None) -> tuple[DirectorStrategy | None, dict]:
    """Full Director run. Creates one DirectorStrategy (status=draft) or returns
    (None, decision) with an explicit reason. Never writes a script."""
    now = now or datetime.utcnow()
    decision = {"stages": {}, "created_at": now.isoformat()}

    niche = db.query(ContentNiche).filter_by(id=channel.niche_id).first() if channel.niche_id else None
    if not niche:
        decision["error"] = "channel_has_no_niche"
        return None, decision
    language = (channel.language or niche.default_language or "ru").strip()
    analytics = channel_analytics(db, channel.id)
    decision["analytics"] = analytics

    # stage 1 — pillar (ranked; if the best pillar is exhausted we try the next)
    history = topic_history(db, channel.id)
    banned = banned_signatures(db, channel.id)
    recent_titles = [s.selected_topic for s in history[:20] if s.selected_topic]
    count = settings.DIRECTOR_CANDIDATES_PER_RUN

    if pillar_id:
        forced = db.query(ContentPillar).filter_by(id=pillar_id, niche_id=niche.id).first()
        if not forced:
            decision["error"] = "pillar_not_in_channel_niche"
            return None, decision
        pillar_queue = [forced]
        decision["stages"]["pillar"] = {"chosen": {"pillar_id": forced.id, "pillar": forced.name},
                                        "forced_by_admin": True, "candidates": []}
    else:
        pillar, pdebug = select_pillar(db, channel, now=now, analytics=analytics)
        decision["stages"]["pillar"] = pdebug
        if not pillar:
            decision["error"] = pdebug.get("error", "no_pillar_available")
            return None, decision
        ranked_ids = [c["pillar_id"] for c in pdebug["candidates"]]
        by_id = {p.id: p for p in db.query(ContentPillar)
                 .filter(ContentPillar.id.in_(ranked_ids)).all()} if ranked_ids else {}
        pillar_queue = [by_id[i] for i in ranked_ids if i in by_id] or [pillar]

    # stages 2-5 — ideation, dedupe, angle, hook, scoring (per pillar, in order)
    angle, adebug = select_angle(db, channel.id, "", history=history)
    decision["stages"]["angle"] = adebug
    attempts, evaluated, pillar, source, ai_error = [], [], None, "heuristic", None
    for candidate_pillar in pillar_queue[:5]:
        cands, perr, psource = [], None, "heuristic"
        if settings.DIRECTOR_USE_AI:
            cands, perr = _ai_candidates(candidate_pillar, niche, channel, language,
                                         recent_titles, count)
            if cands:
                psource = "ai"
        if not cands:
            cands = _heuristic_candidates(candidate_pillar, count, offset=len(history))
        local_eval, rejected = [], []
        for cand in cands:
            dup = duplicate_check(db, channel.id, cand["topic"], history=history, banned=banned)
            if dup["duplicate"]:
                rejected.append({"topic": cand["topic"], "reason": dup["reason"],
                                 "similarity": dup["score"], "closest": dup["closest"]})
                continue
            hook, hstrength = build_hook(cand["topic"], angle, cand.get("seed", ""))
            scores = score_candidate(cand, dup=dup, angle=angle, hook_strength=hstrength,
                                     pillar=candidate_pillar, analytics=analytics)
            local_eval.append({**cand, "hook": hook, "scores": scores, "duplicate_check": dup})
        attempts.append({"pillar": candidate_pillar.name, "generated": len(cands),
                         "rejected": rejected, "accepted": len(local_eval), "source": psource})
        if local_eval:
            evaluated, pillar, source, ai_error = local_eval, candidate_pillar, psource, perr
            break
        # this pillar is exhausted -> fall through to the next-best pillar

    decision["stages"]["ideation"] = {
        "source": source, "ai_error": ai_error,
        "pillar_attempts": attempts,
        "pillar": pillar.name if pillar else None,
        "note": ("heuristic ideation from pillar topics (no AI provider)"
                 if source == "heuristic" else "AI ideation"),
    }
    decision["stages"]["duplicates"] = {
        "checked": sum(a["generated"] for a in attempts),
        "rejected": [r for a in attempts for r in a["rejected"]],
        "accepted": len(evaluated),
        "pillars_tried": [a["pillar"] for a in attempts],
        "threshold": settings.DIRECTOR_DUPLICATE_THRESHOLD,
        "cooldown_days": settings.TOPIC_COOLDOWN_DAYS,
    }
    if not evaluated or pillar is None:
        decision["error"] = "all_candidates_duplicate_or_banned"
        return None, decision

    evaluated.sort(key=lambda c: -c["scores"]["priority"])
    winner = evaluated[0]
    decision["stages"]["selection"] = {
        "chosen": winner["topic"],
        "priority": winner["scores"]["priority"],
        "runners_up": [{"topic": c["topic"], "priority": c["scores"]["priority"]}
                       for c in evaluated[1:4]],
    }

    outline = build_outline(winner["topic"], angle, winner["hook"])
    decision["stages"]["outline"] = {"parts": [p["part"] for p in outline["structure"]]}

    reasons = [
        f"pillar «{pillar.name}» selected by weighted rotation",
        f"novelty {winner['scores']['novelty_score']} (no duplicates within {settings.TOPIC_COOLDOWN_DAYS} days)",
        f"angle «{angle['name']}» least recently used",
        f"hook strength {winner['scores']['hook_strength']}",
        f"visual potential {winner['scores']['visual_potential']}",
        ("historical analytics applied" if analytics["has_data"]
         else "no analytics yet — decided on rotation, novelty and hook"),
    ]
    decision["reasons"] = reasons

    s = winner["scores"]
    strategy = DirectorStrategy(
        channel_id=channel.id, niche_id=niche.id, pillar_id=pillar.id,
        language=language, target_audience=channel.target_audience,
        generation_reason="; ".join(reasons),
        priority=s["priority"],
        estimated_ctr=s["estimated_ctr"], estimated_retention=s["estimated_retention"],
        novelty_score=s["novelty_score"], competition_score=s["competition_score"],
        hook_strength=s["hook_strength"], visual_potential=s["visual_potential"],
        educational_value=s["educational_value"], entertainment_value=s["entertainment_value"],
        selected_topic=winner["topic"][:300],
        normalized_topic=normalize_title(winner["topic"]),
        selected_angle=angle["name"], selected_hook=winner["hook"],
        outline_json=json.dumps(outline, ensure_ascii=False),
        decision_json=json.dumps(decision, ensure_ascii=False),
        status="draft", source=source,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy, decision


# ------------------------------------------------------ stage 7: handoff

def handoff_to_writer(db, strategy: DirectorStrategy) -> VideoProject:
    """Approved strategy -> VideoProject consumed by the existing Script
    Generator. The Director supplies topic/hook/outline, never the script."""
    channel = db.query(Channel).filter_by(id=strategy.channel_id).first()
    niche = db.query(ContentNiche).filter_by(id=strategy.niche_id).first() if strategy.niche_id else None
    pillar = db.query(ContentPillar).filter_by(id=strategy.pillar_id).first() if strategy.pillar_id else None
    outline = json.loads(strategy.outline_json) if strategy.outline_json else {}
    snapshot = {
        "youtube_channel_id": channel.youtube_channel_id if channel else None,
        "channel_name": channel.name if channel else None,
        "niche_id": strategy.niche_id,
        "niche_name": niche.name if niche else None,
        "content_pillar_id": strategy.pillar_id,
        "content_pillar_name": pillar.name if pillar else None,
        "topic": strategy.selected_topic,
        "language": strategy.language,
        "target_audience": strategy.target_audience,
        "tone_of_voice": (channel.tone_of_voice or channel.content_style) if channel else None,
        "visual_style": channel.visual_style if channel else None,
        "director": {
            "strategy_id": strategy.id,
            "angle": strategy.selected_angle,
            "hook": strategy.selected_hook,
            "outline": outline,
            "priority": strategy.priority,
            "generation_reason": strategy.generation_reason,
            "estimated_ctr": strategy.estimated_ctr,
            "estimated_retention": strategy.estimated_retention,
            "source": strategy.source,
        },
        "generation_profile_snapshot": {
            "default_voice": channel.default_voice if channel else None,
            "default_video_duration_seconds": channel.default_video_duration_seconds if channel else None,
            "snapshot_at": datetime.utcnow().isoformat(),
        },
    }
    project = VideoProject(
        channel_id=strategy.channel_id,
        content_pillar_id=strategy.pillar_id,
        content_strategy_id=strategy.id,
        generation_profile_json=json.dumps(snapshot, ensure_ascii=False),
        title=strategy.selected_topic[:300],
        duration_target_seconds=int((channel.default_video_duration_seconds if channel else 45) or 45),
    )
    db.add(project)
    db.flush()
    strategy.video_project_id = project.id
    strategy.status = "used"
    strategy.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project
