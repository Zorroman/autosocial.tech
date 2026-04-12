import re
from dataclasses import dataclass, field, replace

from style_packs import normalize_scene
from video_niches_config import resolve_video_niche_profile


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
SHORT_VISUAL_SEQUENCE = ["people", "hands", "environment", "object", "process", "atmosphere", "people", "environment", "object", "process"]
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
    query_bucket: str = ""
    visual_bucket: str = ""
    timeline_role: str = "body"
    niche_profile_id: str = "generic"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", str(text or "").lower(), flags=re.UNICODE)


def _timeline_role(index: int, total: int) -> str:
    total = max(1, int(total or 1))
    if index == 0:
        return "hook"
    if index >= total - 2:
        return "closing"
    return "body"


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


def _expand_theme_queries(base_queries: list[str], profile: dict | None, phrase: str) -> list[str]:
    expanded = list(base_queries or [])
    phrase_tokens = _tokenize(phrase)
    if profile:
        expanded.extend(profile.get("primary_keywords") or [])
        expanded.extend(profile.get("secondary_keywords") or [])
        expanded.extend(profile.get("related_keywords") or [])
        expanded.extend(profile.get("mood_keywords") or [])
        if phrase_tokens:
            for keyword in list(profile.get("primary_keywords") or [])[:3]:
                expanded.append(f"{phrase_tokens[0]} {keyword}")
    return _dedup_keep_order([str(x or "").strip() for x in expanded if str(x or "").strip()])


def _visual_phrase_queries(profile: dict | None, phrase: str, desired_scene: str, timeline_role: str) -> list[str]:
    if not profile:
        return []
    phrase_clean = _clean_query(phrase)
    subjects = [str(x).strip() for x in (profile.get("visual_subjects") or []) if str(x).strip()][:3]
    actions = [str(x).strip() for x in (profile.get("visual_actions") or []) if str(x).strip()][:3]
    locations = [str(x).strip() for x in (profile.get("visual_locations") or []) if str(x).strip()][:2]
    props = [str(x).strip() for x in (profile.get("visual_props") or []) if str(x).strip()][:2]
    queries: list[str] = []
    for subject in subjects:
        queries.append(f"{subject} {phrase_clean}".strip())
    for action in actions:
        for subject in subjects[:2] or ["person"]:
            queries.append(f"{subject} {action}".strip())
            if phrase_clean:
                queries.append(f"{subject} {action} {phrase_clean}".strip())
    for location in locations:
        queries.append(f"{location} {DEFAULT_SCENE_QUERIES.get(desired_scene, 'real life')}".strip())
        for subject in subjects[:1]:
            queries.append(f"{subject} in {location}".strip())
    for prop in props:
        queries.append(f"{prop} close up".strip())
    if timeline_role == "hook":
        queries.extend([f"{q} close up".strip() for q in queries[:2]])
    if timeline_role == "closing":
        queries.extend([f"{q} final shot".strip() for q in queries[:2]])
    return _dedup_keep_order([q for q in queries if q])


def _profile_query_bucket(profile: dict | None, phrase_index: int, desired_scene: str, timeline_role: str) -> tuple[str, list[str]]:
    visual_buckets = dict((profile or {}).get("visual_buckets") or {})
    sequence = [str(x).strip().lower() for x in ((profile or {}).get("visual_sequence") or []) if str(x).strip()]
    if timeline_role == "hook" and visual_buckets.get("hook"):
        return "hook", list(visual_buckets.get("hook") or [])
    if timeline_role == "closing" and visual_buckets.get("closing"):
        return "closing", list(visual_buckets.get("closing") or [])
    if sequence:
        bucket = sequence[phrase_index % len(sequence)]
        return bucket, list(visual_buckets.get(bucket) or [])
    return str(desired_scene or "generic").strip().lower() or "generic", list(visual_buckets.get(desired_scene) or [])


def _scene_visual_bucket(desired_scene: str, mood: str = "neutral") -> str:
    scene = str(desired_scene or "").strip().lower()
    mood = str(mood or "").strip().lower()
    if scene in {"product", "food"}:
        return "object"
    if scene in {"work"}:
        return "process"
    if scene in {"people"}:
        return "people"
    if scene in {"abstract_real"}:
        return "atmosphere"
    if scene in {"nature", "city", "home", "travel"}:
        return "environment"
    if mood == "dynamic":
        return "process"
    return "environment"


def expand_short_shot_specs(specs: list[ShotSpec], target_seconds: int, min_segments: int = 8) -> list[ShotSpec]:
    if not specs:
        return []
    if int(target_seconds or 0) > 40:
        return list(specs)
    desired_segments = max(len(specs), int(min_segments or 8))
    if len(specs) >= desired_segments:
        return list(specs)
    expanded = [replace(spec) for spec in specs]
    guard = 0
    while len(expanded) < desired_segments and guard < 64:
        guard += 1
        split_idx = max(range(len(expanded)), key=lambda idx: float(expanded[idx].duration_s))
        current = expanded[split_idx]
        if float(current.duration_s) <= 1.2:
            break
        half = max(1.2, round(float(current.duration_s) / 2.0, 2))
        remainder = max(1.2, round(float(current.duration_s) - half, 2))
        bucket_queries = list(current.fallback_queries or current.queries or [])
        left = replace(current, duration_s=half)
        right = replace(
            current,
            duration_s=remainder,
            queries=_dedup_keep_order([*bucket_queries[1:], *bucket_queries[:1]])[:8] or list(current.queries or []),
            fallback_queries=_dedup_keep_order([*bucket_queries[2:], *bucket_queries[:2]])[:10] or list(current.fallback_queries or []),
        )
        expanded[split_idx : split_idx + 1] = [left, right]
    total = len(expanded)
    remapped: list[ShotSpec] = []
    for idx, spec in enumerate(expanded):
        role = _timeline_role(idx, total)
        visual_bucket = SHORT_VISUAL_SEQUENCE[idx % len(SHORT_VISUAL_SEQUENCE)]
        if role == "hook":
            visual_bucket = "process"
        elif role == "closing":
            visual_bucket = "atmosphere"
        remapped.append(replace(spec, timeline_role=role, visual_bucket=visual_bucket))
    return remapped


def normalize_shot_specs(
    phrases: list[str],
    shotlist: list[dict],
    phrase_durations: list[float],
    style_pack: dict | None = None,
    niche_visual_profile: str | None = None,
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
    profile = resolve_video_niche_profile(niche_visual_profile, " ".join(str(x or "") for x in (phrases or [])))
    for idx, phrase in enumerate(phrases):
        raw = per_phrase.get(idx, {})
        scene = _normalized_scene(str(raw.get("scene_type") or "work"), allowed_scenes)
        mood = str(raw.get("mood") or style_mood or "neutral").strip().lower()
        if mood not in MOODS:
            mood = "neutral"
        role = _timeline_role(idx, len(phrases))

        queries_raw = raw.get("queries")
        if isinstance(queries_raw, str):
            queries_raw = [queries_raw]
        if not isinstance(queries_raw, list):
            queries_raw = []
        cleaned = [_clean_query(x) for x in queries_raw if str(x).strip()]
        cleaned = [x for x in cleaned if x]
        if not cleaned:
            cleaned = [_clean_query(phrase), DEFAULT_SCENE_QUERIES.get(scene, "real life")]

        if profile:
            preferred = [str(x).strip() for x in (profile.get("preferred_scenes") or []) if str(x).strip()]
            if preferred and scene not in preferred:
                scene = normalize_scene(preferred[0], allowed_scenes)

        forbid_tokens = set(str(x).strip().lower() for x in ((profile or {}).get("exclusion_keywords") or []) if str(x).strip())
        if forbid_tokens:
            cleaned = [q for q in cleaned if not _query_has_forbid_token(q, forbid_tokens)]
            if not cleaned:
                cleaned = [DEFAULT_SCENE_QUERIES.get(scene, "real life")]

        if query_bias:
            cleaned.extend(query_bias[:2])
        scene_override = scene_overrides.get(scene) if isinstance(scene_overrides, dict) else None
        if isinstance(scene_override, list):
            cleaned.extend([str(x).strip() for x in scene_override[:2] if str(x).strip()])

        bucket, bucket_queries = _profile_query_bucket(profile, idx, scene, role)
        cleaned = [*bucket_queries, *cleaned]
        cleaned = [*_visual_phrase_queries(profile, phrase, scene, role), *cleaned]
        cleaned = _expand_theme_queries(cleaned, profile, phrase)
        if forbid_tokens:
            cleaned = [q for q in cleaned if not _query_has_forbid_token(q, forbid_tokens)]

        cleaned = _dedup_keep_order(cleaned[:8])

        fallback = []
        for q in cleaned:
            fallback.append(q)
            fallback.append(_without_adjectives(q))
            fallback.append(_only_category(q, scene))
        if isinstance(scene_override, list):
            fallback.extend([str(x).strip() for x in scene_override if str(x).strip()])
        fallback.append(DEFAULT_SCENE_QUERIES.get(scene, "real life"))
        if bucket_queries:
            fallback.extend(bucket_queries)
        fallback.extend(_visual_phrase_queries(profile, phrase, scene, role))
        fallback = _expand_theme_queries([x for x in fallback if x], profile, phrase)
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
                *[str(x).strip().lower() for x in (profile.get("visual_subjects") or [])[:2] if str(x).strip()],
                *[str(x).strip().lower() for x in (profile.get("visual_actions") or [])[:1] if str(x).strip()],
            ]
        )
        duration_s = float(phrase_durations[idx] if idx < len(phrase_durations) else 2.0)
        duration_s = max(0.6, duration_s)
        must_exclude = _dedup_keep_order([*ANTI_FANTASY_DEFAULT, *hard_banned])
        if forbid_tokens:
            must_exclude = _dedup_keep_order([*must_exclude, *sorted(forbid_tokens)])
        must_exclude = _dedup_keep_order([*must_exclude, *[str(x).strip().lower() for x in (profile.get("forbidden_visuals") or []) if str(x).strip()]])
        soft_exclude = _dedup_keep_order([*soft_banned, *[str(x).strip().lower() for x in (profile.get("negative_queries") or []) if str(x).strip()]])
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
                query_bucket=bucket,
                visual_bucket=_scene_visual_bucket(scene, mood),
                timeline_role=role,
                niche_profile_id=str((profile or {}).get("id") or "generic"),
            )
        )
    return specs
