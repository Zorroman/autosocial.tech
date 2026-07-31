import json
import re
from typing import Any

from saas_settings import settings


_KEYWORDS_PATH = settings.BASE_DIR / "data" / "niche_media_keywords.json"
_EMBEDDED_KEYWORDS: dict[str, Any] = {
    "barbershop": {
        "positive": ["barbershop", "barber", "haircut", "beard trim", "shaving", "men grooming", "barber chair", "clippers", "fade haircut"],
        "negative": ["office", "meeting", "crowd", "shopping mall", "airport", "laptop", "finance", "marketing", "abstract", "city skyline"],
        "fallback_queries": ["barber haircut close up", "beard trimming barbershop", "men haircut barber chair"],
    }
}


def _load_keywords() -> dict[str, Any]:
    if not _KEYWORDS_PATH.exists():
        return dict(_EMBEDDED_KEYWORDS)
    try:
        data = json.loads(_KEYWORDS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(_EMBEDDED_KEYWORDS)
        merged = dict(_EMBEDDED_KEYWORDS)
        merged.update(data)
        return merged
    except Exception:
        return dict(_EMBEDDED_KEYWORDS)


_KEYWORDS = _load_keywords()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _normalize_language(language: str) -> str:
    key = _normalize_text(language)
    if key in {"русский", "ru", "russian"}:
        return "ru"
    if key in {"deutsch", "de", "german"}:
        return "de"
    return "en"


def _normalize_goal(goal: str) -> str:
    key = _normalize_text(goal)
    if key in {"лиды", "lead", "leads", "sales", "продажи"}:
        return "lead"
    if key in {"доверие", "trust"}:
        return "trust"
    return "awareness"


def _infer_niche_slug(niche_slug: str, niche_title: str, manual_topic: str) -> str:
    slug = _normalize_text(niche_slug)
    if slug and slug in _KEYWORDS:
        return slug

    hay = " ".join([_normalize_text(niche_title), _normalize_text(manual_topic), slug])
    mapping = {
        "barbershop": ["barber", "barbershop", "барбер", "барбершоп"],
        "beauty-salon": ["beauty", "салон", "красот"],
        "auto-service": ["auto service", "автосервис", "ремонт авто", "car service"],
        "tire-service": ["tire", "шиномонтаж", "шины"],
        "tattoo-studio": ["tattoo", "тату"],
        "fitness-trainer": ["fitness", "тренер", "тренировка"],
        "restaurant": ["restaurant", "ресторан"],
        "cafe": ["cafe", "кафе", "coffee"],
        "child-education": ["child", "дет", "education", "школ", "обучен"],
        "car-wash": ["car wash", "мойка", "детейлинг"],
    }
    for candidate, needles in mapping.items():
        if any(x in hay for x in needles):
            return candidate
    return "barbershop"


def _extract_offer_keywords(offer_text: str, language: str) -> list[str]:
    lang = _normalize_language(language)
    tokens = re.findall(r"[A-Za-zА-Яа-яÄÖÜäöüß0-9]+", str(offer_text or ""))
    out: list[str] = []
    for token in tokens:
        key = token.lower()
        if len(key) < 4:
            continue
        out.append(key)
        if len(out) >= 2:
            break
    if out:
        return out
    if lang == "ru":
        return ["услуга"]
    if lang == "de":
        return ["service"]
    return ["service"]


def _orientation(content_type: str, requested_orientation: str) -> str:
    req = _normalize_text(requested_orientation)
    if req in {"vertical", "horizontal", "any"}:
        return req
    ctype = _normalize_text(content_type)
    if ctype in {"video", "video_post", "shorts", "reels"}:
        return "vertical"
    return "any"


def buildMediaQuery(payload: dict[str, Any]) -> dict[str, Any]:
    niche_slug = _infer_niche_slug(
        str(payload.get("nicheSlug") or payload.get("niche_slug") or ""),
        str(payload.get("nicheTitle") or payload.get("niche_title") or ""),
        str(payload.get("manualTopic") or payload.get("manual_topic") or ""),
    )
    pack = _KEYWORDS.get(niche_slug) or {}
    positive = [str(x).strip() for x in (pack.get("positive") or []) if str(x).strip()]
    fallback = [str(x).strip() for x in (pack.get("fallback_queries") or []) if str(x).strip()]
    negative = [str(x).strip().lower() for x in (pack.get("negative") or []) if str(x).strip()]
    language = _normalize_language(str(payload.get("language") or "ru"))
    goal = _normalize_goal(str(payload.get("goal") or "awareness"))
    offer_keywords = _extract_offer_keywords(str(payload.get("offerText") or payload.get("offer_text") or ""), language)

    query_parts = []
    if positive:
        query_parts.extend(positive[:3])
    query_parts.extend(offer_keywords[:1])
    if goal == "lead":
        query_parts.append("booking")
    elif goal == "trust":
        query_parts.append("real client")
    query = " ".join(dict.fromkeys([x for x in query_parts if x])).strip()

    if not fallback:
        fallback = positive[:3] if positive else ["local service", "close up", "professional service"]
    while len(fallback) < 3:
        fallback.append(fallback[-1] if fallback else "local service")

    return {
        "query": query or "local service",
        "fallbackQueries": fallback[:3],
        "negativeKeywords": negative,
        "orientation": _orientation(str(payload.get("contentType") or payload.get("content_type") or ""), str(payload.get("orientation") or "")),
        "positiveKeywords": positive,
        "nicheSlug": niche_slug,
    }


def build_media_query(payload: dict[str, Any]) -> dict[str, Any]:
    return buildMediaQuery(payload)


def _media_text_blob(item: dict[str, Any]) -> str:
    tags = item.get("tags")
    if isinstance(tags, list):
        tags_text = " ".join(str(x) for x in tags if str(x).strip())
    else:
        tags_text = str(tags or "")
    return " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("alt") or ""),
            str(item.get("description") or ""),
            str(item.get("url") or ""),
            tags_text,
        ]
    ).lower()


def filter_media_results(items: list[dict[str, Any]], positive_keywords: list[str], negative_keywords: list[str], min_positive: int = 2) -> list[dict[str, Any]]:
    positive = [str(x).strip().lower() for x in (positive_keywords or []) if str(x).strip()]
    negative = [str(x).strip().lower() for x in (negative_keywords or []) if str(x).strip()]
    kept: list[tuple[int, dict[str, Any]]] = []
    for item in items or []:
        blob = _media_text_blob(item)
        if any(n in blob for n in negative):
            continue
        score = sum(1 for p in positive if p and p in blob)
        if score < min_positive:
            continue
        kept.append((score, item))
    kept.sort(key=lambda x: (-x[0], str((x[1] or {}).get("id") or ""), str((x[1] or {}).get("url") or "")))
    return [row[1] for row in kept]
