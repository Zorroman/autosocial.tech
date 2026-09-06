"""Shorts hook diversity -- fixes only the opening 1-2 phrases of a Shorts
script. Nothing else in the pipeline changes: not the scheduler, media
selection, TTS, subtitles, music, CTA, render, YouTube upload, or the
long-form generator.

Root cause of the reported bug: video_script_generator._fallback() used one
hardcoded opening line ("Сегодня коротко и понятно разбираем тему..."). Every
time OpenAI generation failed (rate limit, timeout, invalid JSON) a Short
landed on that same static fallback script, so a run of consecutive
generation failures produced a run of visually-identical openers. Not an
audio-trimming bug -- a templated-script bug that only shows up under
repeated LLM failure, which is why it looked like "the last few in a row."
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# ------------------------------------------------------------- forbidden openers

# Anchored: these must not be how a hook STARTS. Matched against normalized
# (lowercased, punctuation-stripped) text.
FORBIDDEN_HOOK_PREFIXES: tuple[str, ...] = (
    "сегодня коротко и понятно",
    "сегодня мы разберем",
    "сегодня мы разберём",
    "давайте разберемся",
    "давайте разберёмся",
    "в этом видео",
    "вы когда нибудь задумывались",
    "мало кто знает",
    "а вы знали",
    "сейчас расскажу",
    "сегодня поговорим",
    "разберем тему",
    "разберём тему",
)

# Must not appear ANYWHERE in the hook, not just as an opener.
FORBIDDEN_HOOK_SUBSTRINGS: tuple[str, ...] = (
    "в этом видео",
)

HOOK_TYPES: tuple[str, ...] = (
    "provocative_statement",
    "strong_question",
    "unexpected_fact",
    "warning",
    "result_promise",
    "emotional_situation",
    "mystical_intrigue",
    "contrast_paradox",
)

HOOK_TYPE_DESCRIPTIONS: dict[str, str] = {
    "provocative_statement": "провокационное утверждение",
    "strong_question": "сильный вопрос",
    "unexpected_fact": "неожиданный факт",
    "warning": "опасность или предупреждение",
    "result_promise": "обещание результата",
    "emotional_situation": "эмоциональная ситуация",
    "mystical_intrigue": "мистическая интрига",
    "contrast_paradox": "контраст или парадокс",
}


def normalize_hook(text: str) -> str:
    s = str(text or "").lower().strip()
    s = re.sub(r"[«»\"'.,!?:;()\-–—]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_templated_hook(text: str) -> bool:
    norm = normalize_hook(text)
    if not norm:
        return True
    if any(norm.startswith(prefix) for prefix in FORBIDDEN_HOOK_PREFIXES):
        return True
    return any(bad in norm for bad in FORBIDDEN_HOOK_SUBSTRINGS)


# --------------------------------------------------------------- similarity
# No LLM call: normalize, then blend two cheap signals and take the max --
# SequenceMatcher catches near-identical/reordered text, word-trigram Jaccard
# catches the same words in a different order (which SequenceMatcher can
# under-score).

def _word_ngrams(text: str, n: int = 3) -> set[str]:
    words = text.split()
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def hook_similarity(a: str, b: str) -> float:
    na, nb = normalize_hook(a), normalize_hook(b)
    if not na or not nb:
        return 0.0
    seq_ratio = SequenceMatcher(None, na, nb).ratio()
    grams_a, grams_b = _word_ngrams(na), _word_ngrams(nb)
    jaccard = (len(grams_a & grams_b) / len(grams_a | grams_b)) if (grams_a and grams_b) else 0.0
    return max(seq_ratio, jaccard)


def most_similar_score(hook: str, recent_hooks: list[str]) -> float:
    if not recent_hooks:
        return 0.0
    return max((hook_similarity(hook, h) for h in recent_hooks if h), default=0.0)


# ------------------------------------------------------------------ rotation

def next_hook_type(recent_types: list[str]) -> str:
    """Pick a type not used by either of the last two hooks WE chose (entries
    that are None/unclassified -- the model's own unmodified first attempt --
    don't count against any type, since we never controlled that choice)."""
    known = [t for t in (recent_types or []) if t in HOOK_TYPES]
    last_two = known[-2:]
    banned = {last_two[0]} if (len(last_two) == 2 and last_two[0] == last_two[1]) else set(last_two)
    candidates = [t for t in HOOK_TYPES if t not in banned] or list(HOOK_TYPES)
    recent_window = known[-len(HOOK_TYPES):]
    for t in candidates:
        if t not in recent_window:
            return t
    return candidates[0]


# --------------------------------------------------------- deterministic fallback

def deterministic_hook(topic: str, hook_type: str) -> str:
    """Non-templated, non-LLM opener. Used as: (a) the base for the
    already-existing total-fallback path (OpenAI unavailable), and (b) the
    last resort after MAX_HOOK_ATTEMPTS LLM regenerations still produced a
    templated/too-similar/wrong-length hook."""
    topic = str(topic or "тема").strip().rstrip(".")
    by_type = {
        "provocative_statement": f"{topic} — не то, чем кажется на первый взгляд.",
        "strong_question": f"Почему {topic} задевает сильнее, чем кажется на первый взгляд?",
        "unexpected_fact": f"Мало кто замечает, как {topic} влияет на решения.",
        "warning": f"Если упустить {topic}, последствия проявятся не сразу.",
        "result_promise": f"Разобравшись в {topic}, вы увидите ситуацию иначе.",
        "emotional_situation": f"Есть момент, когда {topic} меняет всё сразу.",
        "mystical_intrigue": f"{topic} — знак, который не стоит списывать на совпадение.",
        "contrast_paradox": f"Чем меньше думаешь про {topic}, тем сильнее оно влияет.",
    }
    return by_type.get(hook_type, by_type["unexpected_fact"])


def fallback_hook_type_for_topic(topic: str) -> str:
    """Deterministic (not random, not history-dependent) type pick for the
    zero-history base fallback path, so even total OpenAI outage doesn't
    collapse every topic onto the same opener."""
    idx = sum(ord(c) for c in str(topic or "")) % len(HOOK_TYPES)
    return HOOK_TYPES[idx]
