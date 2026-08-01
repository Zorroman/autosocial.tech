"""Content Factory — final spoken call-to-action (CTA) generator.

Produces a short, natural, on-topic "subscribe" line for the END of each Short.
The CTA is generated (LLM) with strict validation and de-duplication so videos
never share the same closing line, then handed to the pipeline as a separate
final scene (voiced by the same TTS voice, subtitled, rendered).

Design goals:
  * reuse the shared OpenAI JSON client (retry + validation) — no new client;
  * pure/injectable core so it unit-tests without network;
  * never raise to the caller — on any failure return a safe fallback CTA.

Repeat protection is text-normalised (lowercase, no punctuation, collapsed
whitespace, trimmed tail) plus a token-similarity check, over a history window,
and caps how many times one CTA *type* runs in a row.
"""
from __future__ import annotations

import re
import unicodedata

# CTA categories. subscribe_benefit is the primary/most-frequent one.
CTA_TYPES = ("subscribe_benefit", "next_video", "daily_content", "community", "comment_and_subscribe")
PRIMARY_TYPE = "subscribe_benefit"

MIN_WORDS_DEFAULT = 8
MAX_WORDS_DEFAULT = 16

# Safe fallbacks (used only when generation can't produce a unique valid line).
# Multiple per language so the fallback itself still varies. Never the sole path.
_FALLBACKS = {
    "ru": [
        ("Подпишись, чтобы не пропустить новые истории и открытия по этой теме.", "subscribe_benefit"),
        ("Подпишись — впереди ещё больше коротких и полезных разборов.", "subscribe_benefit"),
        ("Подпишись, чтобы продолжать изучать эту тему вместе с нами.", "daily_content"),
        ("Подпишись и загляни в следующий ролик — там будет интереснее.", "next_video"),
        ("Подпишись и присоединяйся к тем, кто ищет ответы вместе с нами.", "community"),
    ],
    "en": [
        ("Subscribe so you don't miss the next stories and discoveries on this topic.", "subscribe_benefit"),
        ("Subscribe — more short and useful breakdowns are on the way.", "subscribe_benefit"),
        ("Subscribe to keep exploring this topic together with us.", "daily_content"),
        ("Subscribe and check the next video — it gets even better.", "next_video"),
        ("Subscribe and join everyone looking for answers with us.", "community"),
    ],
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
# tails we ignore when comparing "almost the same" endings
_TAIL_WORDS = {"ru": {"с", "нами", "вместе", "здесь", "сегодня", "дальше"},
               "en": {"us", "here", "today", "together", "with"}}
# any of these signals a subscribe call
_SUBSCRIBE_MARKERS = ("подпиш", "подпис", "subscrib")
# multiple simultaneous actions we must NOT ask for at once
_EXTRA_ACTION_MARKERS = ("лайк", "коммент", "уведомл", "поделись", "поделит", "репост",
                         "like", "comment", "share", "notif", "bell")


CTA_RESERVE_SECONDS = 4.0  # duration budget reserved for the CTA scene

_DEFAULT_SETTINGS = {
    "cta_enabled": True,
    "cta_voice_enabled": True,
    "cta_visual_enabled": True,
    "cta_min_words": MIN_WORDS_DEFAULT,
    "cta_max_words": MAX_WORDS_DEFAULT,
    "cta_history_window": 20,
    "cta_max_same_type_streak": 3,
    "cta_fallback_text": "",
}


def default_settings() -> dict:
    return dict(_DEFAULT_SETTINGS)


def read_cta_settings(channel) -> dict:
    """Merge the channel's stored CTA config over the defaults. Uses the existing
    channel.generation_settings_json mechanism — no parallel config store."""
    import json as _json
    out = dict(_DEFAULT_SETTINGS)
    raw = getattr(channel, "generation_settings_json", None)
    try:
        cfg = (_json.loads(raw) if raw else {}) or {}
        cta = cfg.get("cta") if isinstance(cfg.get("cta"), dict) else {}
        for k in out:
            if k in cta and cta[k] is not None:
                out[k] = cta[k]
    except Exception:
        pass
    return out


def normalize(text: str) -> str:
    s = unicodedata.normalize("NFKC", str(text or "")).lower().strip()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def _tokens(text: str, lang: str) -> set[str]:
    toks = normalize(text).split()
    tail = _TAIL_WORDS.get(lang, set())
    return {t for t in toks if t not in tail}


def similarity(a: str, b: str, lang: str = "ru") -> float:
    """Jaccard token overlap of two CTAs (0..1), ignoring trivial tail words."""
    ta, tb = _tokens(a, lang), _tokens(b, lang)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def is_repeat(candidate: str, recent: list[str], lang: str = "ru", threshold: float = 0.8) -> bool:
    """True if candidate equals (normalised) or is near-identical to any recent CTA."""
    cn = normalize(candidate)
    for prev in recent or []:
        if not prev:
            continue
        if normalize(prev) == cn:
            return True
        if similarity(candidate, prev, lang) >= threshold:
            return True
    return False


def type_streak_blocked(next_type: str, recent_types: list[str], max_streak: int = 3) -> bool:
    """True if using next_type would exceed max_streak identical types in a row."""
    streak = 0
    for t in recent_types or []:  # recent_types is newest-first
        if t == next_type:
            streak += 1
        else:
            break
    return streak >= max_streak


def _word_count(text: str) -> int:
    return len([w for w in normalize(text).split() if w])


def validate_cta(text: str, lang: str, min_words: int, max_words: int) -> str | None:
    """Return an error string if invalid, else None."""
    t = str(text or "").strip()
    if not t:
        return "empty"
    wc = _word_count(t)
    if wc < min_words:
        return f"too_short ({wc}w<{min_words})"
    if wc > max_words:
        return f"too_long ({wc}w>{max_words})"
    low = t.lower()
    if not any(m in low for m in _SUBSCRIBE_MARKERS):
        return "no_subscribe_call"
    # single primary action: reject if it also demands like/comment/share/bell
    if any(m in low for m in _EXTRA_ACTION_MARKERS):
        return "multiple_actions"
    # language sanity: ru must contain Cyrillic; non-ru must be mostly ASCII
    has_cyr = bool(re.search(r"[а-яё]", low))
    if lang == "ru" and not has_cyr:
        return "wrong_language"
    if lang != "ru" and has_cyr:
        return "wrong_language"
    return None


def pick_fallback(lang: str, recent: list[str], recent_types: list[str],
                 max_streak: int = 3) -> tuple[str, str]:
    """A safe, still-varied fallback CTA that respects repeat + streak rules."""
    pool = _FALLBACKS.get(lang) or _FALLBACKS["en"]
    for text, ctype in pool:
        if not is_repeat(text, recent, lang) and not type_streak_blocked(ctype, recent_types, max_streak):
            return text, ctype
    # everything collided → least-bad: first that isn't an exact recent repeat
    for text, ctype in pool:
        if normalize(text) not in {normalize(r) for r in (recent or [])}:
            return text, ctype
    return pool[0]


def _prompt(ctx: dict, want_type: str) -> tuple[str, str]:
    lang = ctx.get("language") or "ru"
    system = (
        "You write ONE short, natural spoken call-to-action for the very end of a "
        "short vertical video. It must invite the viewer to SUBSCRIBE to the channel "
        "and briefly say what they gain by subscribing. Exactly one action (subscribe) "
        "— never ask to like, comment, share or hit the bell at the same time. "
        f"Write in the video's language ({lang}). No clickbait, no false promises. "
        "Return STRICT JSON."
    )
    recent = ctx.get("recent_ctas") or []
    user = (
        f"Channel/theme: {ctx.get('niche') or ctx.get('project_title') or 'general'}\n"
        f"Language: {lang}\n"
        f"Video topic: {ctx.get('topic') or ctx.get('project_title') or ''}\n"
        f"Last line of the script: {ctx.get('last_line') or ''}\n"
        f"Channel promise (optional): {ctx.get('channel_promise') or ''}\n"
        f"Desired CTA type: {want_type} "
        f"({'subscribe + concrete benefit' if want_type=='subscribe_benefit' else want_type})\n"
        f"Length: {ctx.get('min_words', MIN_WORDS_DEFAULT)}–{ctx.get('max_words', MAX_WORDS_DEFAULT)} words, "
        "so it speaks in about 3–5 seconds.\n"
        "Must NOT repeat or paraphrase any of these recent CTAs:\n"
        + "\n".join(f"- {c}" for c in recent[:20]) + "\n\n"
        "Return JSON: {\"cta\": \"...\", \"type\": \"" + want_type + "\"}\n"
        "Rules: continue naturally from the video's topic; one subscribe action only; "
        "explain the benefit of subscribing; no like/comment/share/bell; no clickbait."
    )
    return system, user


def _choose_type(recent_types: list[str], max_streak: int) -> str:
    """subscribe_benefit is primary; avoid exceeding the type streak."""
    if not type_streak_blocked(PRIMARY_TYPE, recent_types, max_streak):
        return PRIMARY_TYPE
    # streak on primary → rotate to another allowed type
    for t in ("next_video", "daily_content", "community", "comment_and_subscribe"):
        if not type_streak_blocked(t, recent_types, max_streak):
            return t
    return PRIMARY_TYPE


def generate_cta(ctx: dict, *, llm=None) -> dict:
    """Generate a validated, non-repeating CTA.

    ctx keys: language, niche, project_title, topic, last_line, channel_promise,
    recent_ctas (newest-first), recent_types (newest-first), min_words, max_words,
    max_same_type_streak. Returns {text, type, source, language, fallback_used}.
    source ∈ generated | fallback. Never raises.
    """
    lang = ctx.get("language") or "ru"
    min_words = int(ctx.get("min_words") or MIN_WORDS_DEFAULT)
    max_words = int(ctx.get("max_words") or MAX_WORDS_DEFAULT)
    max_streak = int(ctx.get("max_same_type_streak") or 3)
    recent = ctx.get("recent_ctas") or []
    recent_types = ctx.get("recent_types") or []
    want_type = _choose_type(recent_types, max_streak)

    if llm is None:
        try:
            from openai_client import generate_json_with_retry, is_openai_enabled
            if is_openai_enabled():
                llm = generate_json_with_retry
        except Exception:
            llm = None

    if llm is not None:
        def _validator(payload: dict) -> None:
            if not isinstance(payload.get("cta"), str) or not payload["cta"].strip():
                raise ValueError("cta required")

        for _ in range(2):  # a couple of regen attempts for repeat/validity
            try:
                system, user = _prompt({**ctx, "min_words": min_words, "max_words": max_words}, want_type)
                res = llm(system_prompt=system, user_prompt=user,
                          validator=_validator, max_output_tokens=200, temperature=0.8)
                text = str(res.payload.get("cta") or "").strip()
                ctype = str(res.payload.get("type") or want_type).strip()
                if ctype not in CTA_TYPES:
                    ctype = want_type
                if validate_cta(text, lang, min_words, max_words):
                    continue
                if is_repeat(text, recent, lang):
                    continue
                if type_streak_blocked(ctype, recent_types, max_streak):
                    ctype = want_type
                return {"text": text, "type": ctype, "source": "generated",
                        "language": lang, "fallback_used": False}
            except Exception:
                continue

    text, ctype = pick_fallback(lang, recent, recent_types, max_streak)
    return {"text": text, "type": ctype, "source": "fallback",
            "language": lang, "fallback_used": True}
