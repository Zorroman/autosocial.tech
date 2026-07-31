from __future__ import annotations

import re
from hashlib import sha1
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from config import Config
from saas_settings import settings

PEXELS_PHOTO_API_URL = "https://api.pexels.com/v1/search"
MEDIA_DIR = Path(__file__).resolve().parents[3] / "generated_media"
MEDIA_DIR.mkdir(exist_ok=True)

_GENERIC_TEXTURE_TERMS = {
    "tile", "tiles", "ceramic", "marble", "texture", "pattern", "background", "surface", "mosaic", "wallpaper",
}

_MATERIAL_TOPIC_TERMS = {
    "tile", "tiles", "material", "materials", "floor", "flooring", "wall", "walls", "paint", "ceramic", "marble",
}

_ESOTERICA_REQUIRED_TERMS = {
    "ritual", "moon", "energy", "meditation", "tarot", "symbol", "symbols", "candles", "candle", "mystic",
    "mystical", "zodiac", "spiritual", "practice", "intuition", "universe", "sacred", "incense",
}

_ESOTERICA_WRONG_CONTEXT_TERMS = {
    "renovation", "interior", "wall", "room", "floor", "tool", "texture", "material", "materials",
    "kitchen", "bathroom", "construction", "tile", "tiles", "surface", "pattern", "wallpaper", "workspace",
}

_COSMETOLOGY_SKIN_TERMS = {
    "skin", "facial", "face", "skincare", "esthetician", "aesthetic", "cosmetology", "treatment", "clinic",
}

_COSMETOLOGY_NAIL_TERMS = {
    "nail", "nails", "manicure", "pedicure", "hand", "hands",
}

_RENOVATION_PROCESS_TERMS = {
    "worker", "measure", "measuring", "blueprint", "tools", "tool", "renovation", "construction",
    "interior", "room", "repair", "worksite", "contractor", "home improvement",
}


_PSYCHOLOGY_SUPPORT_TERMS = {
    "therapy", "therapist", "counseling", "counselling", "conversation", "support", "journal", "journaling",
    "reflection", "listening", "session", "comfort", "calm", "emotions", "mental health", "psychology",
}

_PSYCHOLOGY_ABSTRACT_TERMS = {
    "landscape", "sunset", "forest", "mountain", "lake", "sea", "ocean", "window", "silhouette", "sky",
}

_RENOVATION_PLANNING_TERMS = {
    "estimate", "budget", "blueprint", "plan", "planning", "measuring", "contractor", "discussion", "worksite",
    "unfinished room", "renovation process", "repair planning", "construction estimate", "project management",
}

_ESOTERICA_MOON_TOPIC_TERMS = {
    "луна", "лун", "полнолун", "новолун", "moon", "full moon", "zodiac", "зодиак", "астролог",
}

_ESOTERICA_ENERGY_TOPIC_TERMS = {
    "энерг", "защит", "негатив", "очищ", "ритуал", "свеч", "аура", "crystal", "energy", "cleansing", "ritual",
}

_ESOTERICA_SIGNS_TOPIC_TERMS = {
    "знак", "знаки", "вселен", "интуиц", "символ", "повтор", "синхрон", "universe", "intuition", "symbols", "signs",
}

_RENOVATION_MATERIAL_TOPIC_TERMS_RU = {
    "материал", "отделк", "плитк", "пол", "полы", "стен", "краск", "обои", "ламинат", "керам", "финиш",
}

_RENOVATION_PLANNING_TOPIC_TERMS_RU = {
    "смет", "бюджет", "подрядчик", "план", "этап", "срок", "договор", "расчет", "расчёт",
    "доплат", "перерасход", "контроль", "приемк", "приёмк", "закуп", "очеред", "работ",
}

_WEAK_TOPIC_WORDS = {
    "как", "что", "почему", "ошибка", "ошибки", "ошибок", "шаг", "шаги", "план", "контент", "контентплан",
    "контент-план", "день", "дней", "неделя", "неделю", "месяц", "пост", "поста", "постов", "тема",
    "темы", "тем", "бизнес", "клиент", "клиенты", "аудитория", "результат", "результаты", "публикация",
    "публикации", "публиковать", "generate", "post", "social", "media",
}

NICHE_MEDIA_KEYWORDS: dict[str, dict[str, Any]] = {
    "fitness": {
        "visual": ["gym workout", "morning exercise", "yoga stretching", "healthy lifestyle", "personal trainer"],
        "fallback": ["fitness gym portrait", "exercise coaching", "healthy workout"],
        "negative": ["office", "meeting", "laptop", "city skyline", "conference", "animal"],
    },
    "real_estate": {
        "visual": ["modern apartment interior", "real estate agent", "house keys home", "property consultation", "apartment renovation"],
        "fallback": ["apartment interior", "real estate consultation", "home keys"],
        "negative": ["gym", "restaurant", "tattoo", "animal", "car workshop"],
    },
    "restaurant": {
        "visual": ["restaurant food plating", "chef cooking", "cozy dining table", "coffee shop interior", "restaurant kitchen"],
        "fallback": ["restaurant dish close up", "chef plating food", "cozy table restaurant"],
        "negative": ["office", "meeting", "construction", "car repair"],
    },
    "beauty_salon": {
        "visual": ["beauty treatment", "manicure close up", "skincare spa", "makeup artist", "beauty salon interior"],
        "fallback": ["beauty salon treatment", "skincare spa portrait", "manicure salon"],
        "negative": ["construction", "restaurant", "car workshop", "animal"],
    },
    "finance": {
        "visual": ["business planning", "calculator desk", "entrepreneur laptop", "money strategy", "financial consultation"],
        "fallback": ["financial planning desk", "business calculator", "money consultation"],
        "negative": ["gym", "restaurant", "tattoo", "barbershop"],
    },
    "psychology": {
        "visual": ["therapy session", "supportive conversation", "journaling notebook", "counseling office", "emotional support"],
        "fallback": ["therapy office", "journaling reflection", "emotional support conversation"],
        "negative": ["construction", "cars", "restaurant kitchen", "tattoo machine"],
    },
    "esoterica": {
        "visual": ["tarot candles altar", "moon ritual candles", "spiritual hands crystals", "mystical meditation", "esoteric symbols"],
        "fallback": ["meditation candles", "moon spiritual ritual", "altar candles crystals"],
        "negative": ["animal", "street traffic", "train", "office", "car", "restaurant"],
        "required_any": ["candle", "candles", "moon", "crystal", "spiritual", "meditation", "ritual", "incense", "tarot", "energy"],
    },
    "tattoo": {
        "visual": ["tattoo artist studio", "tattoo sketch drawing", "black ink tattoo arm", "tattoo machine close up", "tattoo consultation"],
        "fallback": ["tattoo artist close up", "tattoo studio", "tattoo sketch"],
        "negative": ["office", "restaurant", "construction", "animal"],
    },
    "smm_marketing": {
        "visual": ["content planning desk", "social media strategy", "marketing team workspace", "analytics dashboard", "content creation workspace"],
        "fallback": ["content strategy desk", "marketing planning", "social media workspace"],
        "negative": ["animal", "forest", "train", "construction debris"],
    },
    "dentist": {
        "visual": ["dentist consultation", "dental clinic", "teeth care close up", "dentist tools", "patient smile clinic"],
        "fallback": ["dental clinic consultation", "dentist tools", "healthy smile clinic"],
        "negative": ["restaurant", "construction", "car workshop", "tattoo"],
    },
    "autoservice": {
        "visual": ["car diagnostics workshop", "mechanic inspecting engine", "auto service bay", "vehicle maintenance", "car repair tools"],
        "fallback": ["mechanic engine diagnostics", "auto service workshop", "car maintenance bay"],
        "negative": ["forest", "train", "office meeting", "animal", "restaurant"],
    },
    "barbershop": {
        "visual": ["barber haircut close up", "beard trim barbershop", "barber chair studio", "mens grooming", "clippers haircut"],
        "fallback": ["barber haircut", "beard trim", "barbershop portrait"],
        "negative": ["animal", "forest", "train", "office", "construction"],
    },
    "cosmetology": {
        "visual": ["skincare treatment room", "cosmetologist consultation", "beauty facial close up", "aesthetic clinic", "cosmetology procedure"],
        "fallback": ["cosmetology consultation", "beauty treatment clinic", "facial skincare room"],
        "negative": ["animal", "train", "car workshop", "construction"],
    },
    "detailing": {
        "visual": ["car detailing studio", "car polishing close up", "vehicle interior cleaning", "detailing coating", "microfiber detailing"],
        "fallback": ["car detailing close up", "vehicle polishing", "detailing studio"],
        "negative": ["forest", "animal", "office", "restaurant"],
    },
    "renovation": {
        "visual": ["renovation planning blueprint", "worker measuring room", "contractor discussion worksite", "unfinished room renovation", "home improvement tools in use"],
        "fallback": ["apartment renovation planning", "worker measuring wall", "interior renovation worksite"],
        "negative": ["animal", "restaurant", "tattoo", "gym"],
        "required_any": ["renovation", "repair", "interior", "worker", "tool", "construction", "apartment", "home", "paint", "measure"],
    },
    "consulting": {
        "visual": ["business consultation meeting", "strategy discussion desk", "advisor with client", "planning session", "professional consultation"],
        "fallback": ["business consulting meeting", "strategy planning desk", "consultation office"],
        "negative": ["restaurant kitchen", "tattoo studio", "car workshop"],
    },
    "online_courses": {
        "visual": ["online learning workspace", "course recording setup", "laptop education", "teacher online class", "digital study desk"],
        "fallback": ["online course workspace", "digital learning desk", "teacher laptop class"],
        "negative": ["construction", "car workshop", "restaurant"],
    },
}

NICHE_ALIASES = {
    "fitness": "fitness",
    "фитнес": "fitness",
    "real_estate": "real_estate",
    "недвижимость": "real_estate",
    "ремонт квартир": "renovation",
    "apartment_renovation": "renovation",
    "renovation": "renovation",
    "restaurant": "restaurant",
    "ресторан": "restaurant",
    "beauty_salon": "beauty_salon",
    "beauty-salon": "beauty_salon",
    "beauty": "beauty_salon",
    "beauty salon": "beauty_salon",
    "косметология": "cosmetology",
    "cosmetology": "cosmetology",
    "finance": "finance",
    "финансы": "finance",
    "psychology": "psychology",
    "психология": "psychology",
    "esoterica": "esoterica",
    "esoterics": "esoterica",
    "эзотерика": "esoterica",
    "tattoo": "tattoo",
    "тату": "tattoo",
    "smm_marketing": "smm_marketing",
    "smm": "smm_marketing",
    "маркетинг": "smm_marketing",
    "smm и маркетинг": "smm_marketing",
    "dentist": "dentist",
    "стоматология": "dentist",
    "autoservice": "autoservice",
    "автосервис": "autoservice",
    "barbershop": "barbershop",
    "барбершоп": "barbershop",
    "detailing": "detailing",
    "детейлинг": "detailing",
    "consulting": "consulting",
    "консалтинг": "consulting",
    "online_courses": "online_courses",
    "online-courses": "online_courses",
    "онлайн-курсы": "online_courses",
}


class PexelsError(RuntimeError):
    pass


class PexelsConfigError(PexelsError):
    pass


class PexelsRateLimitError(PexelsError):
    pass


class PexelsRequestError(PexelsError):
    pass


class PexelsEmptyResultError(PexelsError):
    pass


@dataclass
class PexelsMediaResult:
    provider: str
    type: str
    external_id: str
    preview_url: str
    full_url: str
    width: int
    height: int
    photographer: str
    orientation: str
    query_used: str
    score: float
    local_url: str
    local_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "type": self.type,
            "external_id": self.external_id,
            "preview_url": self.preview_url,
            "full_url": self.full_url,
            "width": self.width,
            "height": self.height,
            "photographer": self.photographer,
            "orientation": self.orientation,
            "query_used": self.query_used,
            "score": round(self.score, 4),
            "local_url": self.local_url,
            "local_path": self.local_path,
        }


def normalize_niche_slug(value: str | None) -> str:
    raw = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if not raw:
        return "smm_marketing"
    if raw in NICHE_ALIASES:
        return NICHE_ALIASES[raw]
    raw_slug = raw.replace("-", "_")
    if raw_slug in NICHE_ALIASES:
        return NICHE_ALIASES[raw_slug]
    for key, target in NICHE_ALIASES.items():
        if key in raw:
            return target
    return raw_slug


def _tokenize(value: str) -> list[str]:
    tokens = re.findall(r"[A-Za-zА-Яа-яЁёÄÖÜäöüß0-9]+", str(value or "").lower())
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if len(token) < 3 or token in _WEAK_TOPIC_WORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _topic_focus_terms(topic: str, post_text: str | None = None, limit: int = 4) -> list[str]:
    primary = _tokenize(topic)
    secondary = _tokenize(post_text or "")
    merged: list[str] = []
    seen: set[str] = set()
    for token in [*primary, *secondary]:
        if token in seen:
            continue
        seen.add(token)
        merged.append(token)
        if len(merged) >= limit:
            break
    return merged


def _normalized_text(*parts: str | None) -> str:
    return " ".join(str(part or "").strip().lower() for part in parts if str(part or "").strip())


def _contains_any_term(text: str, terms: set[str] | list[str] | tuple[str, ...]) -> bool:
    return any(str(term or "").strip().lower() in text for term in terms if str(term or "").strip())


def _derive_topic_constraints(niche_slug: str, topic: str, post_text: str | None = None) -> dict[str, Any]:
    text = _normalized_text(topic, post_text)
    query_terms: list[str] = []
    positive_terms: list[str] = []
    avoid_terms: list[str] = []
    required_positive_any: list[str] = []
    required_positive_count = 0

    if niche_slug == "esoterica":
        positive_terms.extend(sorted(_ESOTERICA_REQUIRED_TERMS))
        avoid_terms.extend(sorted(_ESOTERICA_WRONG_CONTEXT_TERMS))
        required_positive_any.extend(["ritual", "moon", "meditation", "candles", "candle", "tarot", "spiritual", "mystical", "altar", "crystal", "incense"])
        required_positive_count = 1
        if _contains_any_term(text, _ESOTERICA_ENERGY_TOPIC_TERMS):
            query_terms.extend([
                "energy cleansing ritual candles crystals incense",
                "spiritual protection ritual candles altar",
                "sacred smoke candles crystals ritual",
            ])
        elif _contains_any_term(text, _ESOTERICA_MOON_TOPIC_TERMS):
            query_terms.extend([
                "full moon ritual candles tarot altar",
                "moon phase spiritual ritual candles",
                "zodiac mystical candles meditation",
            ])
        elif _contains_any_term(text, _ESOTERICA_SIGNS_TOPIC_TERMS):
            query_terms.extend([
                "tarot cards candles mystical symbols",
                "intuition spiritual symbols candles",
                "universe signs mystical ritual altar",
            ])
        else:
            query_terms.extend([
                "tarot candles crystals altar",
                "spiritual meditation candles crystals",
                "mystical ritual altar incense",
            ])

    elif niche_slug == "psychology":
        positive_terms.extend(sorted(_PSYCHOLOGY_SUPPORT_TERMS))
        avoid_terms.extend(sorted(_PSYCHOLOGY_ABSTRACT_TERMS))
        required_positive_any.extend(["therapy", "conversation", "journaling", "support", "reflection", "counseling"])
        required_positive_count = 1
        if _contains_any_term(text, {"????", "anxiety", "panic", "??????", "stress"}):
            query_terms.extend([
                "therapy session calm conversation",
                "emotional support counseling",
                "mental health journaling support",
            ])
        elif _contains_any_term(text, {"??????", "boundary", "???", "guilt", "????"}):
            query_terms.extend([
                "supportive conversation therapy",
                "journaling self reflection",
                "therapist client calm office",
            ])
        else:
            query_terms.extend([
                "therapy session reflection",
                "journaling emotional support",
                "calm conversation counseling",
            ])

    elif niche_slug == "cosmetology":
        nail_topic = _contains_any_term(text, {"????", "?????", "?????", "nail", "manicure", "pedicure"})
        if nail_topic:
            positive_terms.extend(sorted(_COSMETOLOGY_NAIL_TERMS))
            query_terms.extend([
                "manicure salon close up",
                "nail treatment beauty salon",
                "nail care procedure",
            ])
        else:
            positive_terms.extend(sorted(_COSMETOLOGY_SKIN_TERMS))
            avoid_terms.extend(sorted(_COSMETOLOGY_NAIL_TERMS))
            if _contains_any_term(text, {"????????", "??????", "???????", "skin", "hydrat", "sensitive"}):
                query_terms.extend([
                    "sensitive skin facial treatment",
                    "skincare face consultation",
                    "aesthetic clinic skin care",
                ])
            else:
                query_terms.extend([
                    "skincare facial treatment",
                    "esthetician face consultation",
                    "aesthetic clinic face",
                ])

    elif niche_slug == "renovation":
        material_topic = _contains_any_term(text, _RENOVATION_MATERIAL_TOPIC_TERMS_RU | _MATERIAL_TOPIC_TERMS)
        planning_topic = _contains_any_term(text, _RENOVATION_PLANNING_TOPIC_TERMS_RU | {"estimate", "budget", "contractor", "plan", "planning", "timeline"})
        if material_topic and not planning_topic:
            positive_terms.extend(sorted(_MATERIAL_TOPIC_TERMS))
            query_terms.extend([
                "tile installation renovation worker",
                "home renovation materials installation",
                "apartment finishing work in progress",
            ])
        elif planning_topic:
            positive_terms.extend(sorted(_RENOVATION_PROCESS_TERMS | _RENOVATION_PLANNING_TERMS))
            avoid_terms.extend(sorted(_GENERIC_TEXTURE_TERMS | _MATERIAL_TOPIC_TERMS))
            query_terms.extend([
                "contractor reviewing blueprint renovation",
                "home renovation estimate blueprint planning",
                "worker measuring unfinished apartment room",
                "renovation planning contractor discussion",
            ])
        else:
            positive_terms.extend(sorted(_RENOVATION_PROCESS_TERMS | {"worker", "measuring", "unfinished room"}))
            avoid_terms.extend(sorted(_GENERIC_TEXTURE_TERMS))
            query_terms.extend([
                "worker renovating unfinished apartment room",
                "contractor measuring room renovation",
                "home renovation tools in use",
            ])

    return {
        "query_terms": query_terms[:4],
        "positive_terms": positive_terms,
        "avoid_terms": avoid_terms,
        "required_positive_any": required_positive_any,
        "required_positive_count": required_positive_count,
    }



def _platform_orientation(platform: str | None) -> str:
    key = str(platform or "").strip().lower()
    if key == "instagram":
        return "portrait"
    if key in {"facebook", "blog"}:
        return "landscape"
    return "portrait"


def build_media_query(niche: str | None, topic: str, post_text: str | None = None, platform: str | None = None) -> dict[str, Any]:
    niche_slug = normalize_niche_slug(niche)
    pack = NICHE_MEDIA_KEYWORDS.get(niche_slug, NICHE_MEDIA_KEYWORDS["smm_marketing"])
    topic_terms = _topic_focus_terms(topic, post_text, limit=4)
    visual_terms = list(pack["visual"])
    orientation = _platform_orientation(platform)
    topic_constraints = _derive_topic_constraints(niche_slug, topic, post_text)

    primary_parts = [*(topic_constraints["query_terms"][:1] or []), *visual_terms[:1], *topic_terms[:1]]
    primary_query = " ".join(part for part in primary_parts if part).strip()
    fallback_queries = []
    for parts in (
        topic_constraints["query_terms"],
        [*topic_terms[:1], *visual_terms[:3]],
        [*visual_terms[:2], *topic_terms[:1]],
        pack["fallback"],
        visual_terms,
    ):
        query = " ".join(part for part in parts if part).strip()
        if query and query not in fallback_queries and query != primary_query:
            fallback_queries.append(query)

    return {
        "niche_slug": niche_slug,
        "orientation": orientation,
        "topic_terms": topic_terms,
        "niche_terms": visual_terms,
        "negative_terms": list(pack["negative"]),
        "positive_terms": list(topic_constraints["positive_terms"]),
        "avoid_terms": list(topic_constraints["avoid_terms"]),
        "required_positive_any": list(topic_constraints["required_positive_any"]),
        "required_positive_count": int(topic_constraints["required_positive_count"] or 0),
        "primary_query": primary_query or " ".join(visual_terms[:2]),
        "fallback_queries": fallback_queries[:6],
        "selection_seed": f"{niche_slug}|{topic}|{platform or ''}",
    }


def _api_headers() -> dict[str, str]:
    api_key = (Config.PEXELS_API_KEY or "").strip()
    if not api_key:
        raise PexelsConfigError("PEXELS_API_KEY is missing")
    return {"Authorization": api_key}


def _candidate_orientation(width: int, height: int) -> str:
    if width == height:
        return "square"
    return "portrait" if height > width else "landscape"


def _search_photos(query: str, orientation: str, per_page: int = 10) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"query": query, "per_page": max(5, min(20, int(per_page or 10))), "page": 1}
    if orientation in {"portrait", "landscape"}:
        params["orientation"] = orientation
    try:
        response = requests.get(PEXELS_PHOTO_API_URL, headers=_api_headers(), params=params, timeout=20)
    except requests.Timeout as exc:
        raise PexelsRequestError("Pexels request timed out") from exc
    except requests.RequestException as exc:
        raise PexelsRequestError("Pexels request failed") from exc
    if response.status_code == 401:
        raise PexelsConfigError("PEXELS_API_KEY rejected by Pexels")
    if response.status_code == 429:
        raise PexelsRateLimitError("Pexels rate limit reached")
    if response.status_code >= 500:
        raise PexelsRequestError(f"Pexels server error: {response.status_code}")
    if response.status_code != 200:
        raise PexelsRequestError(f"Pexels search failed: {response.status_code}")
    payload = response.json() if response.content else {}
    photos = payload.get("photos") if isinstance(payload, dict) else []
    return [item for item in photos if isinstance(item, dict)]


def _candidate_blob(photo: dict[str, Any]) -> str:
    parts = [
        str(photo.get("alt") or ""),
        str(photo.get("url") or ""),
        str((photo.get("photographer") or "")),
    ]
    src = photo.get("src")
    if isinstance(src, dict):
        parts.extend(str(v or "") for v in src.values())
    return " ".join(parts).lower()


def _signature_tokens(value: str) -> set[str]:
    tokens = _tokenize(value)
    return {token for token in tokens if not token.isdigit()}


def _photo_signature(photo: dict[str, Any]) -> set[str]:
    parts = [str(photo.get("alt") or ""), str(photo.get("url") or "")]
    full_url = _photo_download_url(photo)
    if full_url:
        parsed = urlparse(full_url)
        parts.append(parsed.path.replace("-", " ").replace("_", " "))
    return _signature_tokens(" ".join(parts))


def _signature_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / float(len(union))


def _same_photo_family(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_photographer = str(left.get("photographer") or "").strip().lower()
    right_photographer = str(right.get("photographer") or "").strip().lower()
    if not left_photographer or left_photographer != right_photographer:
        return False
    return _signature_overlap(_photo_signature(left), _photo_signature(right)) >= 0.35


def _select_candidate(
    candidates: list[tuple[float, dict[str, Any]]],
    *,
    query_meta: dict[str, Any],
    query: str,
) -> tuple[float, dict[str, Any]]:
    ranked = sorted(candidates, key=lambda item: (-item[0], str(item[1].get("id") or "")))
    if len(ranked) == 1:
        return ranked[0]

    # Keep one representative per same-shoot family before final deterministic selection.
    family_shortlist: list[tuple[float, dict[str, Any]]] = []
    for candidate in ranked:
        if any(_same_photo_family(candidate[1], kept[1]) for kept in family_shortlist):
            continue
        family_shortlist.append(candidate)
        if len(family_shortlist) >= 5:
            break
    if not family_shortlist:
        family_shortlist = ranked[:5]

    best_score = family_shortlist[0][0]
    top_family_is_dominant = any(_same_photo_family(ranked[0][1], item[1]) for item in ranked[1:3])
    if top_family_is_dominant and len(family_shortlist) > 1 and (best_score - family_shortlist[1][0]) <= 4.0:
        return family_shortlist[1]

    competitive = [item for item in family_shortlist if (best_score - item[0]) <= 4.0]
    if len(competitive) == 1:
        return competitive[0]

    seed = f"{query_meta.get('niche_slug') or ''}|{query_meta.get('selection_seed') or ''}|{query}"
    choice_index = int(sha1(seed.encode("utf-8")).hexdigest()[:8], 16) % len(competitive)
    return competitive[choice_index]


def _score_candidate(photo: dict[str, Any], query_meta: dict[str, Any], orientation: str) -> float:
    blob = _candidate_blob(photo)
    blob_tokens = _signature_tokens(blob)
    width = int(photo.get("width") or 0)
    height = int(photo.get("height") or 0)
    candidate_orientation = _candidate_orientation(width, height)
    score = 0.0

    topic_terms = query_meta["topic_terms"]
    niche_terms = query_meta["niche_terms"]
    negative_terms = query_meta["negative_terms"]
    positive_terms = [str(item or "").strip().lower() for item in (query_meta.get("positive_terms") or []) if str(item or "").strip()]
    avoid_terms = [str(item or "").strip().lower() for item in (query_meta.get("avoid_terms") or []) if str(item or "").strip()]
    required_positive_any = [str(item or "").strip().lower() for item in (query_meta.get("required_positive_any") or []) if str(item or "").strip()]
    required_positive_count = max(0, int(query_meta.get("required_positive_count") or 0))
    niche_slug = str(query_meta.get("niche_slug") or "").strip().lower()
    pack = NICHE_MEDIA_KEYWORDS.get(niche_slug, {})
    required_any = [str(item or "").strip().lower() for item in (pack.get("required_any") or []) if str(item or "").strip()]
    positive_hits = 0

    for token in topic_terms:
        if token in blob:
            score += 14.0
    for token in niche_terms:
        token_low = token.lower()
        if token_low in blob:
            score += 6.0
    for token in positive_terms:
        if token in blob:
            score += 8.0
            positive_hits += 1
    for token in negative_terms:
        if token in blob:
            score -= 20.0
    for token in avoid_terms:
        if token in blob:
            score -= 14.0

    if required_any and not any(token in blob for token in required_any):
        score -= 18.0
    if required_positive_any and not any(token in blob for token in required_positive_any):
        score -= 26.0
    if required_positive_count and positive_hits < required_positive_count:
        score -= 18.0 * float(required_positive_count - positive_hits)

    if niche_slug in {"esoterica", "renovation"}:
        if any(token in blob_tokens for token in _GENERIC_TEXTURE_TERMS):
            topic_token_set = {str(token or "").strip().lower() for token in topic_terms}
            if not (topic_token_set & _MATERIAL_TOPIC_TERMS):
                score -= 24.0
    if niche_slug == "esoterica":
        esoterica_positive_hits = sum(1 for token in _ESOTERICA_REQUIRED_TERMS if token in blob)
        if any(token in blob for token in _ESOTERICA_WRONG_CONTEXT_TERMS):
            score -= 42.0
        if esoterica_positive_hits < 2:
            score -= 14.0 * float(2 - esoterica_positive_hits)
    if niche_slug == "renovation":
        planning_intent = _contains_any_term(str(query_meta.get("selection_seed") or ""), _RENOVATION_PLANNING_TOPIC_TERMS_RU | {"estimate", "budget", "contractor", "plan", "planning", "timeline"})
        if planning_intent and any(token in blob_tokens for token in _GENERIC_TEXTURE_TERMS | _MATERIAL_TOPIC_TERMS):
            score -= 20.0
    if niche_slug == "psychology" and any(token in blob for token in _PSYCHOLOGY_ABSTRACT_TERMS):
        score -= 18.0

    if orientation == "portrait":
        if candidate_orientation == "portrait":
            score += 12.0
        elif candidate_orientation == "square":
            score += 5.0
        else:
            score -= 8.0
    elif orientation == "landscape":
        if candidate_orientation == "landscape":
            score += 12.0
        elif candidate_orientation == "square":
            score += 4.0
        else:
            score -= 8.0

    if width >= 1600 or height >= 1600:
        score += 2.5
    if not str(photo.get("alt") or "").strip():
        score -= 3.0
    return score


def _photo_download_url(photo: dict[str, Any]) -> str:
    src = photo.get("src") if isinstance(photo.get("src"), dict) else {}
    return str(src.get("large2x") or src.get("large") or src.get("original") or src.get("medium") or "").strip()


def _photo_preview_url(photo: dict[str, Any]) -> str:
    src = photo.get("src") if isinstance(photo.get("src"), dict) else {}
    return str(src.get("medium") or src.get("large") or src.get("landscape") or src.get("portrait") or _photo_download_url(photo)).strip()


def _extract_pexels_id_from_media_url(media_url: str | None) -> str:
    raw = str(media_url or "").strip()
    if not raw:
        return ""
    match = re.search(r"pexels_(\d+)", raw)
    if match:
        return match.group(1)
    path = urlparse(raw).path
    match = re.search(r"/photos/(\d+)/", path)
    if match:
        return match.group(1)
    return ""


def _load_recent_project_refs(db, project_id: int | None) -> tuple[set[str], set[str]]:
    if not db or not project_id:
        return set(), set()
    try:
        from saas_models import Post
    except Exception:
        return set(), set()
    rows = (
        db.query(Post.media_url)
        .filter(Post.project_id == int(project_id), Post.media_url.isnot(None))
        .order_by(Post.id.desc())
        .limit(80)
        .all()
    )
    ids: set[str] = set()
    urls: set[str] = set()
    for row in rows:
        value = str(row[0] or "").strip()
        if not value:
            continue
        urls.add(value)
        ext_id = _extract_pexels_id_from_media_url(value)
        if ext_id:
            ids.add(ext_id)
    return ids, urls


def _persist_photo(photo: dict[str, Any]) -> tuple[str, str]:
    photo_id = str(photo.get("id") or "").strip()
    if not photo_id:
        raise PexelsRequestError("Pexels response missing photo id")
    download_url = _photo_download_url(photo)
    if not download_url:
        raise PexelsRequestError("Pexels response missing photo url")
    target = MEDIA_DIR / f"pexels_{photo_id}.jpg"
    if not target.exists():
        try:
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()
        except requests.Timeout as exc:
            raise PexelsRequestError("Pexels image download timed out") from exc
        except requests.RequestException as exc:
            raise PexelsRequestError("Pexels image download failed") from exc
        target.write_bytes(response.content)
    return str(target), f"{settings.API_BASE_URL}/api/media/{target.name}"


def fetch_post_image(
    *,
    niche: str | None,
    topic: str,
    platform: str,
    post_text: str | None = None,
    db=None,
    project_id: int | None = None,
    used_external_ids: set[str] | None = None,
    used_urls: set[str] | None = None,
) -> PexelsMediaResult:
    query_meta = build_media_query(niche=niche, topic=topic, post_text=post_text, platform=platform)
    orientation = query_meta["orientation"]
    recent_ids, recent_urls = _load_recent_project_refs(db, project_id)
    blocked_ids = set(recent_ids) | set(used_external_ids or set())
    blocked_urls = set(recent_urls) | set(used_urls or set())

    last_error: Exception | None = None
    queries = [query_meta["primary_query"], *query_meta["fallback_queries"]]
    for query in queries:
        try:
            photos = _search_photos(query, orientation, per_page=10)
        except (PexelsConfigError, PexelsRateLimitError, PexelsRequestError) as exc:
            last_error = exc
            if isinstance(exc, (PexelsConfigError, PexelsRateLimitError)):
                raise
            continue
        candidates: list[tuple[float, dict[str, Any]]] = []
        for photo in photos:
            ext_id = str(photo.get("id") or "").strip()
            full_url = _photo_download_url(photo)
            if not ext_id or not full_url:
                continue
            if ext_id in blocked_ids or full_url in blocked_urls:
                continue
            score = _score_candidate(photo, query_meta, orientation)
            if score <= 0:
                continue
            candidates.append((score, photo))
        if not candidates:
            continue
        best_score, best_photo = _select_candidate(candidates, query_meta=query_meta, query=query)
        local_path, local_url = _persist_photo(best_photo)
        return PexelsMediaResult(
            provider="pexels",
            type="photo",
            external_id=str(best_photo.get("id") or ""),
            preview_url=_photo_preview_url(best_photo),
            full_url=_photo_download_url(best_photo),
            width=int(best_photo.get("width") or 0),
            height=int(best_photo.get("height") or 0),
            photographer=str(best_photo.get("photographer") or "").strip(),
            orientation=_candidate_orientation(int(best_photo.get("width") or 0), int(best_photo.get("height") or 0)),
            query_used=query,
            score=best_score,
            local_url=local_url,
            local_path=local_path,
        )

    if last_error:
        raise last_error
    raise PexelsEmptyResultError("No Pexels image matched the topic and niche")
