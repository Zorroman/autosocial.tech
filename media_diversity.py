"""Media Diversity Engine — media *selection* only, nothing else in the
pipeline changes: not the scheduler, not render, not AI script/TTS, not
publishing.

Three pieces, each addressing one concrete production problem:

1. search_both_providers() -- Pexels and Pixabay are searched together and
   merged into one candidate pool, instead of "search Pexels, only fall back
   to Pixabay if Pexels raised/returned nothing" (which is why Pixabay was
   effectively dead in practice: Pexels almost never fails outright, it just
   sometimes returns mediocre results that a human wouldn't have picked).
2. infer_category() -- a coarse visual theme per clip (forest, monk,
   meditation, ...), so repeated real-world themes (not just repeated exact
   clips) can be penalized.
3. category_penalty() / graduated_recency_penalty() -- scoring deltas that
   plug into the *existing* scoring in footage_library.score_candidates(),
   rather than a second, competing ranking system.

No new provider APIs, no new services, no new third-party dependencies --
footage/providers/pexels.py and footage/providers/pixabay.py already exist
and already share the same search_videos(...) signature.
"""
from __future__ import annotations

from footage.types import VideoResult

# ------------------------------------------------------------- categories

# Order matters: candidates are tested top-to-bottom and the first match
# wins. Concrete subjects (forest, monk, temple, ...) are checked before
# atmospheric modifiers (fog, night, energy) so e.g. "misty forest morning"
# categorizes as "forest", not "fog" -- the modifier, not the subject.
CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "waterfall": {"waterfall", "cascade", "rapids"},
    "temple": {"temple", "shrine", "pagoda", "cathedral", "church"},
    "ruins": {"ruins", "ancient ruins", "old stone", "ruin", "archaeology"},
    "monk": {"monk", "monks", "monastery", "buddhist monk"},
    "meditation": {"meditation", "meditating", "mindfulness", "zen"},
    "woman": {"woman", "girl", "female"},
    "couple": {"couple", "two people", "relationship"},
    "forest": {"forest", "woods", "woodland", "trees"},
    "mountains": {"mountain", "mountains", "peak", "hills"},
    "sea": {"sea", "ocean", "waves", "beach", "coast"},
    "books": {"book", "books", "library", "pages", "reading"},
    "cosmos": {"cosmos", "galaxy", "universe", "nebula", "space"},
    "stars": {"stars", "starry", "star", "constellation"},
    "moon": {"moon", "lunar", "moonlight"},
    "candles": {"candle", "candles", "candlelight"},
    "fire": {"fire", "flame", "bonfire", "campfire", "burning"},
    "symbols": {"symbol", "symbols", "rune", "runes", "sigil"},
    "walking": {"walking", "walk", "path", "trail"},
    "night": {"night", "midnight", "nighttime", "dark sky"},
    "fog": {"fog", "mist", "misty", "haze", "foggy"},
    "energy": {"energy", "aura", "glow", "light rays"},
}


def infer_category(*texts: str) -> str | None:
    """First matching category across the given free-text fields (title,
    tags, search_query, ...), or None if nothing matches -- treated as
    neutral (no bonus/penalty), never as a false repeat."""
    hay = " ".join(str(t or "") for t in texts).lower()
    if not hay.strip():
        return None
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in hay for kw in keywords):
            return category
    return None


# --------------------------------------------------------- provider merge

def search_both_providers(query: str, *, orientation: str, min_duration: int,
                          max_duration: int, limit: int, page: int = 1) -> list[VideoResult]:
    """Search Pexels and Pixabay for the same query and merge the results
    into one pool, instead of only reaching Pixabay when Pexels raises.
    Each provider call is independently fault-tolerant: either one failing
    (missing API key, network error, rate limit) still returns whatever the
    other provider found -- never an exception, matching the existing
    providers' own already-graceful "no key -> []" behavior."""
    results: list[VideoResult] = []

    try:
        from footage.providers.pexels import search_videos as pexels_search
        results.extend(pexels_search(
            query=query, orientation=orientation, min_duration=min_duration,
            max_duration=max_duration, limit=limit, page=page,
        ) or [])
    except Exception:
        pass

    try:
        from footage.providers.pixabay import search_videos as pixabay_search
        results.extend(pixabay_search(
            query=query, orientation=orientation, min_duration=min_duration,
            max_duration=max_duration, limit=limit, page=page,
        ) or [])
    except Exception:
        pass

    seen: set[str] = set()
    merged: list[VideoResult] = []
    for r in results:
        key = r.unique_key()
        if key in seen:
            continue
        seen.add(key)
        merged.append(r)
    return merged


# ------------------------------------------------------------- scoring

def category_penalty(category: str | None, recent_categories: list[str]) -> float:
    """Scoring delta for how much a candidate's category repeats the
    channel's most recently used categories. recent_categories is ordered
    oldest-first (so [-1] is the most recent). Positive = bonus (fresh
    theme), negative = penalty (recently overused theme)."""
    if not category:
        return 0.0
    if not recent_categories:
        return 20.0
    occurrences = sum(1 for c in recent_categories if c == category)
    if occurrences == 0:
        return 20.0
    penalty = -30.0 * min(occurrences, 3)
    if recent_categories[-1] == category:
        penalty -= 50.0
    return penalty


def graduated_recency_penalty(days_since_used: float | None) -> float:
    """Scoring delta based on how long ago a specific clip was last used,
    layered on top of (not replacing) the existing hard same-channel/global
    cooldown exclusion in footage_library.score_candidates. Mirrors the
    illustrative point table: never used is the best case, and the penalty
    grows sharply as the last use gets more recent."""
    if days_since_used is None:
        return 100.0
    if days_since_used > 365:
        return 50.0
    if days_since_used > 180:
        return 30.0
    if days_since_used > 30:
        return -50.0
    if days_since_used > 7:
        return -150.0
    if days_since_used > 1:
        return -500.0
    return -10_000.0  # used today or yesterday: effectively banned, but still
    # a finite score so it stays composable with the other scoring terms
    # (a literal -inf would poison any sum/bound check downstream).


def long_term_cooldown_ok(days_since_used: float | None, uses_since: int,
                          *, min_days: int, min_uses: int) -> bool:
    """The hard long-term rule: a clip becomes reusable only once BOTH the
    day threshold and the usage-count threshold have cleared -- whichever
    is later, not whichever is first. days_since_used=None means never
    used, which is always fine."""
    if days_since_used is None:
        return True
    return days_since_used >= min_days and uses_since >= min_uses
