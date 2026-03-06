import re
from dataclasses import dataclass, field

from style_packs import normalize_scene


DESIRED_SCENES = {"people", "work", "city", "nature", "product", "abstract_real", "home", "food", "travel"}
MOODS = {"calm", "dynamic", "neutral"}
NOISE_WORDS = {
    "very",
    "super",
    "really",
    "cool",
    "nice",
    "best",
    "amazing",
    "epic",
    "cinematic",
    "highly",
    "beautiful",
    "awesome",
}
COMMON_ADJECTIVES = {"big", "small", "large", "modern", "new", "old", "fast", "slow", "great"}
DEFAULT_SCENE_QUERIES = {
    "work": "office work",
    "city": "city street",
    "nature": "nature landscape",
    "people": "people talking",
    "home": "home interior",
    "food": "food cooking",
    "travel": "travel walking",
    "product": "hands holding product",
    "abstract_real": "light abstract real",
}
THEME_SCENE_PROFILES = [
    {
        "id": "esoteric_nature",
        "keywords": {
            "эзотерика",
            "эзотерический",
            "медитация",
            "медитативный",
            "духовный",
            "осознанность",
            "энергия",
            "чакра",
            "таро",
            "астрология",
            "мистика",
            "интуиция",
            "самопознание",
            "гармония",
            "вибрации",
            "ретрит",
            "луна",
        },
        "preferred_scenes": ["nature", "abstract_real", "travel", "home"],
        "query_overrides": [
            "misty forest",
            "mountain landscape",
            "sea waves",
            "foggy nature",
            "meditation in nature",
        ],
        "forbid_tokens": {
            "office",
            "laptop",
            "meeting",
            "startup",
            "business",
            "corporate",
            "typing",
            "coworking",
        },
    },
]
ANTI_FANTASY_DEFAULT = [
    "fantasy",
    "dragon",
    "alien",
    "ufo",
    "anime",
    "cartoon",
    "3d",
    "render",
    "cgi",
    "unreal",
    "ai generated",
    "midjourney",
    "stable diffusion",
    "illustration",
    "sci-fi",
    "space battle",
    "monster",
    "magic spell",
    "metaverse",
]


@dataclass
class ShotSpec:
    phrase_index: int
    phrase_text: str
    duration_s: float
    desired_scene: str
    mood: str
    queries: list[str]
    fallback_queries: list[str]
    must_include: list[str]
    must_exclude: list[str]
    soft_exclude: list[str] = field(default_factory=list)
    style_pack_id: str = "default_pro"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", str(text or "").lower(), flags=re.UNICODE)


def _detect_theme_profile(text: str) -> dict | None:
    tokens = set(_tokenize(text))
    for profile in THEME_SCENE_PROFILES:
        keys = set(profile.get("keywords") or [])
        if tokens & keys:
            return profile
    return None


def _query_has_forbid_token(query: str, forbid_tokens: set[str]) -> bool:
    if not forbid_tokens:
        return False
    q = str(query or "").strip().lower()
    if not q:
        return False
    return any(tok in q for tok in forbid_tokens)


def _clean_query(q: str) -> str:
    parts = [x for x in _tokenize(q) if x not in NOISE_WORDS]
    return " ".join(parts).strip()


def _without_adjectives(q: str) -> str:
    parts = [x for x in _tokenize(q) if x not in COMMON_ADJECTIVES]
    return " ".join(parts).strip()


def _only_category(q: str, desired_scene: str) -> str:
    parts = _tokenize(q)
    if not parts:
        return DEFAULT_SCENE_QUERIES.get(desired_scene, "real life")
    return parts[-1]


def _dedup_keep_order(items: list[str]) -> list[str]:
    out = []
    for item in items:
        cur = str(item or "").strip()
        if cur and cur not in out:
            out.append(cur)
    return out


def _normalized_scene(raw_scene: str, allowed_scenes: list[str]) -> str:
    scene = str(raw_scene or "").strip().lower()
    if scene not in DESIRED_SCENES:
        if scene in {"office", "business"}:
            scene = "work"
        elif scene in {"street", "downtown", "skyline"}:
            scene = "city"
        elif scene in {"forest", "mountains", "river"}:
            scene = "nature"
        else:
            scene = "abstract_real"
    return normalize_scene(scene, allowed_scenes)


def normalize_shot_specs(
    phrases: list[str],
    shotlist: list[dict],
    phrase_durations: list[float],
    style_pack: dict | None = None,
) -> list[ShotSpec]:
    style_pack = style_pack or {}
    allowed_scenes = list(style_pack.get("allowed_scenes") or [])
    query_bias = [str(x).strip() for x in (style_pack.get("query_bias") or []) if str(x).strip()]
    scene_overrides = style_pack.get("scene_query_overrides") if isinstance(style_pack.get("scene_query_overrides"), dict) else {}
    hard_banned = [str(x).strip().lower() for x in (style_pack.get("banned_tokens") or []) if str(x).strip()]
    soft_banned = [str(x).strip().lower() for x in (style_pack.get("soft_banned_tokens") or []) if str(x).strip()]
    style_mood = str(style_pack.get("mood") or "neutral").strip().lower()
    style_id = str(style_pack.get("id") or "default_pro").strip().lower() or "default_pro"

    per_phrase: dict[int, dict] = {}
    for idx, raw in enumerate(shotlist or []):
        if not isinstance(raw, dict):
            continue
        pidx = int(raw.get("phrase_index") if str(raw.get("phrase_index", "")).isdigit() else idx)
        per_phrase[pidx] = raw

    specs: list[ShotSpec] = []
    global_profile = _detect_theme_profile(" ".join(str(x or "") for x in (phrases or [])))
    for idx, phrase in enumerate(phrases):
        raw = per_phrase.get(idx, {})
        scene = _normalized_scene(str(raw.get("scene_type") or "work"), allowed_scenes)
        mood = str(raw.get("mood") or style_mood or "neutral").strip().lower()
        if mood not in MOODS:
            mood = "neutral"

        queries_raw = raw.get("queries")
        if isinstance(queries_raw, str):
            queries_raw = [queries_raw]
        if not isinstance(queries_raw, list):
            queries_raw = []
        cleaned = [_clean_query(x) for x in queries_raw if str(x).strip()]
        cleaned = [x for x in cleaned if x]
        if not cleaned:
            cleaned = [_clean_query(phrase), DEFAULT_SCENE_QUERIES.get(scene, "real life")]

        phrase_context = f"{phrase} {' '.join(cleaned)}"
        profile = _detect_theme_profile(phrase_context) or global_profile
        if profile:
            preferred = [str(x).strip() for x in (profile.get("preferred_scenes") or []) if str(x).strip()]
            if preferred and scene not in preferred:
                scene = normalize_scene(preferred[0], allowed_scenes)

        forbid_tokens = set(str(x).strip().lower() for x in ((profile or {}).get("forbid_tokens") or []) if str(x).strip())
        if forbid_tokens:
            cleaned = [q for q in cleaned if not _query_has_forbid_token(q, forbid_tokens)]
            if not cleaned:
                cleaned = [DEFAULT_SCENE_QUERIES.get(scene, "real life")]

        if query_bias:
            cleaned.extend(query_bias[:2])
        scene_override = scene_overrides.get(scene) if isinstance(scene_overrides, dict) else None
        if isinstance(scene_override, list):
            cleaned.extend([str(x).strip() for x in scene_override[:2] if str(x).strip()])

        if profile:
            cleaned = [
                *[q for q in (profile.get("query_overrides") or []) if str(q).strip()],
                *cleaned,
            ]
            if forbid_tokens:
                cleaned = [q for q in cleaned if not _query_has_forbid_token(q, forbid_tokens)]

        cleaned = _dedup_keep_order(cleaned[:6])

        fallback = []
        for q in cleaned:
            fallback.append(q)
            fallback.append(_without_adjectives(q))
            fallback.append(_only_category(q, scene))
        if isinstance(scene_override, list):
            fallback.extend([str(x).strip() for x in scene_override if str(x).strip()])
        fallback.append(DEFAULT_SCENE_QUERIES.get(scene, "real life"))
        fallback = _dedup_keep_order([x for x in fallback if x])
        if forbid_tokens:
            fallback = [q for q in fallback if not _query_has_forbid_token(q, forbid_tokens)]
            if not fallback:
                fallback = [DEFAULT_SCENE_QUERIES.get(scene, "real life")]

        must_include = _dedup_keep_order(
            [
                "realistic",
                "real life",
                *(query_bias[:2]),
                DEFAULT_SCENE_QUERIES.get(scene, "real life").split()[0],
                *_tokenize(phrase)[:2],
            ]
        )
        duration_s = float(phrase_durations[idx] if idx < len(phrase_durations) else 2.0)
        duration_s = max(0.6, duration_s)
        must_exclude = _dedup_keep_order([*ANTI_FANTASY_DEFAULT, *hard_banned])
        if forbid_tokens:
            must_exclude = _dedup_keep_order([*must_exclude, *sorted(forbid_tokens)])
        soft_exclude = _dedup_keep_order(soft_banned)
        specs.append(
            ShotSpec(
                phrase_index=idx,
                phrase_text=str(phrase or "").strip(),
                duration_s=duration_s,
                desired_scene=scene,
                mood=mood,
                queries=cleaned,
                fallback_queries=fallback,
                must_include=must_include,
                must_exclude=must_exclude,
                soft_exclude=soft_exclude,
                style_pack_id=style_id,
            )
        )
    return specs

