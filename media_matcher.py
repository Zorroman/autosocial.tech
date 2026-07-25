"""Content Factory — semantic media matching.

Problem this solves: scene voiceovers are often abstract and non-English
("символы формируют нашу реальность"). Sent verbatim to Pexels (English-indexed)
they either return nothing or a tiny generic pool that repeats across scenes and
gets exhausted by the cooldown — which is exactly why project 6 left two scenes
without footage. Worse, the old picker had no relevance check at all: it took
Pexels' first result blindly, so "successful" scenes got footage that was only
coincidentally on-theme.

This module builds concrete, English, *filmable* search queries from each scene
(LLM-driven, with a deterministic fallback), runs a multi-stage fallback ladder,
and scores every candidate for relevance. Nothing irrelevant is attached just to
advance the pipeline — low confidence honestly stays `needs_review`.

The heavy I/O (Pexels HTTP, downloads, DB cooldown) stays in the caller; the
functions here are pure and injectable so they can be unit-tested without network
access. `plan_project_queries` takes an `llm` callable; `pick_media` takes a
`search_fn`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------- tokenisation

_WORD_RE = re.compile(r"[a-z0-9]+")
_SLUG_ID_RE = re.compile(r"-\d+/?$")
_EN_STOP = {
    "the", "and", "for", "with", "video", "footage", "pexels", "com", "www",
    "https", "http", "clip", "stock", "free", "a", "an", "of", "on", "in", "to",
    "at", "by", "her", "his", "their", "our", "your", "other", "items", "com",
}


def slug_tokens(page_url: str) -> set[str]:
    """Descriptive English tokens from a Pexels page URL slug.

    'https://www.pexels.com/video/a-crystal-and-other-items-on-a-table-20406176/'
    -> {'crystal', 'table', ...}
    """
    if not page_url:
        return set()
    tail = page_url.rstrip("/").rsplit("/", 1)[-1]
    tail = _SLUG_ID_RE.sub("", tail)
    return {w for w in _WORD_RE.findall(tail.replace("-", " ").lower())
            if len(w) > 2 and w not in _EN_STOP}


def candidate_tokens(cand) -> set[str]:
    """All relevance tokens we can see for a candidate: slug + provider tags."""
    toks = slug_tokens(getattr(cand, "page_url", "") or "")
    for t in (getattr(cand, "tags", None) or []):
        toks |= {w for w in _WORD_RE.findall(str(t).lower()) if len(w) > 2 and w not in _EN_STOP}
    return toks


def keyword_set(words) -> set[str]:
    out: set[str] = set()
    for w in (words or []):
        for tok in _WORD_RE.findall(str(w).lower()):
            if len(tok) > 2 and tok not in _EN_STOP:
                out.add(tok)
    return out


def relevance_score(keywords: set[str], cand) -> int:
    """How many of the scene's relevance keywords appear in the candidate."""
    if not keywords:
        return 0
    return len(keywords & candidate_tokens(cand))


# ------------------------------------------------------------------ query plan

@dataclass
class ScenePlan:
    scene_id: int
    queries: list[str] = field(default_factory=list)   # concrete English, best-first
    simple: str = ""                                    # 1-2 word concrete English
    keywords: list[str] = field(default_factory=list)   # relevance tokens (English)


@dataclass
class ProjectPlan:
    scenes: dict[int, ScenePlan] = field(default_factory=dict)
    atmospheric: list[str] = field(default_factory=list)  # on-theme B-roll fallback
    source: str = "llm"                                    # llm | heuristic


# Built-in atmospheric B-roll pools, used when the LLM is unavailable. Keyed by
# coarse theme detected from the niche string (RU or EN). All English, concrete.
_ATMOS_ESOTERIC = [
    "sacred geometry", "starry night sky", "glowing particles dark",
    "mystical smoke", "full moon clouds", "candle flame dark",
    "ancient symbols carved stone", "crystal ball", "northern lights",
]
_ATMOS_GENERIC = [
    "cinematic abstract background", "light particles dark",
    "slow motion nature", "city timelapse night", "soft bokeh lights",
]

# Minimal RU->EN concept hints for the heuristic (no network) fallback.
_CONCEPT_HINTS = {
    "символ": "symbols", "знак": "signs", "вселенн": "universe stars",
    "реальност": "reality abstract", "культур": "culture heritage",
    "истори": "history ancient", "жизн": "life", "мир": "world map",
    "число": "numbers", "звезд": "stars night sky", "энерг": "energy glow",
    "судьб": "fate mystical", "тайн": "mystery dark", "медитац": "meditation calm",
}


def _detect_atmos(niche: str) -> list[str]:
    n = (niche or "").lower()
    eso_markers = ("эзотер", "esoter", "mystic", "мистик", "таро", "tarot",
                   "астролог", "astro", "дух", "spirit", "магия", "magic")
    return _ATMOS_ESOTERIC if any(m in n for m in eso_markers) else _ATMOS_GENERIC


def heuristic_plan(scenes, niche: str, language: str) -> ProjectPlan:
    """Deterministic, network-free plan. Maps known abstract stems to English
    concept hints and always attaches the niche atmospheric pool so abstract
    scenes still get on-theme footage."""
    atmos = _detect_atmos(niche)
    plan = ProjectPlan(atmospheric=list(atmos), source="heuristic")
    for s in scenes:
        text = (getattr(s, "voiceover_text", "") or "").lower()
        hints: list[str] = []
        for stem, en in _CONCEPT_HINTS.items():
            if stem in text and en not in hints:
                hints.append(en)
        queries = hints[:3] if hints else list(atmos[:2])
        kws = keyword_set(queries) | keyword_set(atmos[:3])
        plan.scenes[getattr(s, "id")] = ScenePlan(
            scene_id=getattr(s, "id"),
            queries=queries or list(atmos[:2]),
            simple=(queries[0].split()[0] if queries else atmos[0]),
            keywords=sorted(kws),
        )
    return plan


def _plan_prompt(scenes, niche: str, language: str) -> tuple[str, str]:
    system = (
        "You are a stock-footage search expert for short vertical videos. "
        "For each scene you turn an abstract or non-English narration into CONCRETE, "
        "FILMABLE, ENGLISH search queries for Pexels (which indexes English). "
        "Never translate abstract ideas literally — describe what the camera would "
        "actually SEE. Example: narration 'signs of the universe' -> 'starry night "
        "sky timelapse', 'glowing constellations', not 'universe signs'. "
        "Return STRICT JSON."
    )
    lines = []
    for s in scenes:
        lines.append(f'- scene {getattr(s, "id")}: "{(getattr(s, "voiceover_text", "") or "").strip()[:240]}"')
    user = (
        f"Niche/theme: {niche or 'general'}. Narration language: {language or 'ru'}.\n"
        f"Scenes:\n" + "\n".join(lines) + "\n\n"
        "Return JSON of this exact shape:\n"
        '{\n'
        '  "scenes": [\n'
        '    {"id": <scene id>, "queries": ["concrete english b-roll query", "alt query", "broader query"],\n'
        '     "simple": "one or two concrete english words", "keywords": ["noun","noun"]},\n'
        '    ...\n'
        '  ],\n'
        '  "atmospheric": ["on-theme english b-roll", "...", "..."]\n'
        "}\n"
        "Rules: 2-3 queries per scene, best/most specific first, each 2-5 concrete "
        "English words, all visually filmable. keywords = the concrete visible nouns "
        "(English) a good clip would show. atmospheric = 4-6 on-theme establishing "
        "shots for the niche. No abstract nouns, no non-English words anywhere."
    )
    return system, user


def _validate_plan(payload: dict) -> None:
    if not isinstance(payload.get("scenes"), list) or not payload["scenes"]:
        raise ValueError("scenes[] required")
    for item in payload["scenes"]:
        if "id" not in item or not isinstance(item.get("queries"), list) or not item["queries"]:
            raise ValueError("each scene needs id and non-empty queries[]")


def plan_project_queries(scenes, niche: str, language: str, *, llm=None) -> ProjectPlan:
    """Build an English, concrete query plan for every scene. Uses the LLM when
    available, falling back to the deterministic heuristic on any failure so the
    pipeline never hard-depends on the model."""
    if llm is None:
        from openai_client import generate_json_with_retry, is_openai_enabled
        if not is_openai_enabled():
            return heuristic_plan(scenes, niche, language)
        llm = generate_json_with_retry
    try:
        system, user = _plan_prompt(scenes, niche, language)
        res = llm(system_prompt=system, user_prompt=user,
                  validator=_validate_plan, max_output_tokens=1200, temperature=0.4)
        payload = res.payload
    except Exception:
        return heuristic_plan(scenes, niche, language)

    atmos = [str(x).strip() for x in (payload.get("atmospheric") or []) if str(x).strip()]
    if not atmos:
        atmos = _detect_atmos(niche)
    plan = ProjectPlan(atmospheric=atmos, source="llm")
    by_id = {getattr(s, "id"): s for s in scenes}
    for item in payload.get("scenes", []):
        try:
            sid = int(item.get("id"))
        except Exception:
            continue
        if sid not in by_id:
            continue
        queries = [str(q).strip() for q in (item.get("queries") or []) if str(q).strip()]
        if not queries:
            continue
        plan.scenes[sid] = ScenePlan(
            scene_id=sid,
            queries=queries[:3],
            simple=str(item.get("simple") or queries[0].split()[0]).strip(),
            keywords=[str(k).strip() for k in (item.get("keywords") or []) if str(k).strip()],
        )
    # any scene the model skipped falls back to the heuristic for that scene
    if len(plan.scenes) < len(scenes):
        hp = heuristic_plan([s for s in scenes if getattr(s, "id") not in plan.scenes], niche, language)
        plan.scenes.update(hp.scenes)
    return plan


# ------------------------------------------------------------------ the ladder

@dataclass
class LadderStep:
    stage: str          # concrete | simple | atmospheric
    query: str
    keywords: set[str]
    confidence: str     # matched | atmospheric
    min_score: int      # relevance needed to accept a candidate at this stage


def scene_ladder(sp: ScenePlan, atmospheric: list[str]) -> list[LadderStep]:
    """Ordered fallback ladder for one scene:
       concrete query #1..#3 -> simple -> atmospheric B-roll.
    Concrete/simple stages require a real relevance hit (>=1 keyword); the
    atmospheric stage is on-theme by construction so it accepts best-available."""
    kws = keyword_set(sp.keywords) or keyword_set(sp.queries)
    steps: list[LadderStep] = []
    for q in sp.queries:
        steps.append(LadderStep("concrete", q, kws | keyword_set([q]), "matched", 1))
    if sp.simple:
        steps.append(LadderStep("simple", sp.simple, kws | keyword_set([sp.simple]), "matched", 1))
    for a in atmospheric:
        steps.append(LadderStep("atmospheric", a, keyword_set([a]), "atmospheric", 0))
    return steps


@dataclass
class MediaPick:
    candidate: object | None
    stage: str
    confidence: str          # matched | atmospheric | needs_review
    diagnostics: dict


def pick_media(sp: ScenePlan, atmospheric: list[str], *, search_fn,
               exclude_ids: set[str], min_matched_score: int = 1) -> MediaPick:
    """Walk the ladder, scoring candidates, and return the best acceptable pick.

    search_fn(query, exclude_ids) -> list[candidate] (already vertical-first,
    cooldown-excluded by the caller). Adjacent/within-project repeats are avoided
    via exclude_ids. Returns confidence='needs_review' with full diagnostics when
    nothing acceptable is found — the caller must then leave the scene unfilled."""
    tried = []
    best_atmos: tuple[int, object, str] | None = None
    for step in scene_ladder(sp, atmospheric):
        try:
            cands = search_fn(step.query, exclude_ids) or []
        except Exception as exc:
            tried.append({"stage": step.stage, "query": step.query, "error": str(exc)[:160]})
            continue
        scored = []
        for c in cands:
            if str(getattr(c, "video_id", "")) in exclude_ids:
                continue
            scored.append((relevance_score(step.keywords, c), c))
        scored.sort(key=lambda t: t[0], reverse=True)
        tried.append({
            "stage": step.stage, "query": step.query,
            "candidates": [{"id": str(getattr(c, "video_id", "")), "score": sc,
                            "slug": (getattr(c, "page_url", "") or "").rstrip("/").rsplit("/", 1)[-1][:60]}
                           for sc, c in scored[:5]],
        })
        if not scored:
            continue
        top_score, top = scored[0]
        if step.confidence == "matched" and top_score >= max(step.min_score, min_matched_score):
            return MediaPick(top, step.stage, "matched",
                             {"chosen_query": step.query, "chosen_score": top_score,
                              "source": "concrete", "stages_tried": tried})
        if step.confidence == "atmospheric":
            # remember the best atmospheric option but keep trying earlier-quality
            if best_atmos is None or top_score > best_atmos[0]:
                best_atmos = (top_score, top, step.query)
    if best_atmos is not None:
        return MediaPick(best_atmos[1], "atmospheric", "atmospheric",
                         {"chosen_query": best_atmos[2], "chosen_score": best_atmos[0],
                          "source": "atmospheric_fallback", "stages_tried": tried})
    return MediaPick(None, "none", "needs_review",
                     {"reason": "no acceptable candidate across all stages",
                      "stages_tried": tried})
