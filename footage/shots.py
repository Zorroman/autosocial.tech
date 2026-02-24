import re
from dataclasses import dataclass


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


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Zа-яА-Я0-9]+", str(text or "").lower())


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


def normalize_shot_specs(phrases: list[str], shotlist: list[dict], phrase_durations: list[float]) -> list[ShotSpec]:
    per_phrase: dict[int, dict] = {}
    for idx, raw in enumerate(shotlist or []):
        if not isinstance(raw, dict):
            continue
        pidx = int(raw.get("phrase_index") if str(raw.get("phrase_index", "")).isdigit() else idx)
        per_phrase[pidx] = raw

    specs: list[ShotSpec] = []
    for idx, phrase in enumerate(phrases):
        raw = per_phrase.get(idx, {})
        scene = str(raw.get("scene_type") or "work").strip().lower()
        if scene not in DESIRED_SCENES:
            if scene in {"office", "business"}:
                scene = "work"
            elif scene in {"street", "downtown", "skyline"}:
                scene = "city"
            else:
                scene = "abstract_real"
        mood = str(raw.get("mood") or "neutral").strip().lower()
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
        cleaned = _dedup_keep_order(cleaned[:4])

        fallback = []
        for q in cleaned:
            fallback.append(q)
            fallback.append(_without_adjectives(q))
            fallback.append(_only_category(q, scene))
        fallback.append(DEFAULT_SCENE_QUERIES.get(scene, "real life"))
        fallback = _dedup_keep_order([x for x in fallback if x])

        must_include = _dedup_keep_order(
            ["realistic", "real life", DEFAULT_SCENE_QUERIES.get(scene, "real life").split()[0], *_tokenize(phrase)[:2]]
        )
        duration_s = float(phrase_durations[idx] if idx < len(phrase_durations) else 2.0)
        duration_s = max(0.6, duration_s)
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
                must_exclude=list(ANTI_FANTASY_DEFAULT),
            )
        )
    return specs
