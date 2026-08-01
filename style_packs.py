import copy
import json
from pathlib import Path

from app_settings import settings


DEFAULT_STYLE_PACK_ID = "default_pro"
DEFAULT_ALLOWED_SCENES = ["people", "work", "city", "nature", "home", "product", "abstract_real"]
SCENE_ALIASES = {
    "office": "work",
    "business": "work",
    "street": "city",
    "downtown": "city",
    "skyline": "city",
    "travel": "city",
    "food": "home",
}
DEFAULT_PACK = {
    "id": DEFAULT_STYLE_PACK_ID,
    "name": "Default Pro",
    "description": "Fallback style pack",
    "allowed_scenes": list(DEFAULT_ALLOWED_SCENES),
    "banned_tokens": [],
    "soft_banned_tokens": [],
    "motion_level": "medium",
    "mood": "neutral",
    "shot_types": ["wide", "medium", "closeup", "hands", "broll"],
    "query_bias": ["real life", "realistic", "natural light"],
    "scene_query_overrides": {},
    "visual_profile": {"palette": "neutral", "light": "natural"},
}

_CACHE = {"path": None, "mtime": None, "data": None}


def _config_path() -> Path:
    return (settings.BASE_DIR / "config" / "style_packs.json").resolve()


def _uniq(items: list[str]) -> list[str]:
    out = []
    for item in items:
        value = str(item or "").strip().lower()
        if value and value not in out:
            out.append(value)
    return out


def _normalize_pack(raw: dict, global_banned: list[str]) -> dict:
    pack = copy.deepcopy(DEFAULT_PACK)
    if isinstance(raw, dict):
        for key in (
            "id",
            "name",
            "description",
            "allowed_scenes",
            "banned_tokens",
            "soft_banned_tokens",
            "motion_level",
            "mood",
            "shot_types",
            "query_bias",
            "scene_query_overrides",
            "visual_profile",
        ):
            if key in raw:
                pack[key] = raw[key]
    pack["id"] = str(pack.get("id") or DEFAULT_STYLE_PACK_ID).strip().lower()
    if not pack["id"]:
        pack["id"] = DEFAULT_STYLE_PACK_ID
    allowed = [str(x or "").strip().lower() for x in (pack.get("allowed_scenes") or []) if str(x or "").strip()]
    pack["allowed_scenes"] = _uniq(allowed) or list(DEFAULT_ALLOWED_SCENES)
    banned = _uniq([*(global_banned or []), *((pack.get("banned_tokens") or []))])
    soft = _uniq(pack.get("soft_banned_tokens") or [])
    pack["banned_tokens"] = banned
    pack["soft_banned_tokens"] = [x for x in soft if x not in banned]
    pack["query_bias"] = _uniq(pack.get("query_bias") or [])
    shot_types = [str(x or "").strip().lower() for x in (pack.get("shot_types") or []) if str(x or "").strip()]
    pack["shot_types"] = _uniq(shot_types)
    scene_overrides = {}
    raw_overrides = pack.get("scene_query_overrides") or {}
    if isinstance(raw_overrides, dict):
        for scene, queries in raw_overrides.items():
            key = str(scene or "").strip().lower()
            if not key:
                continue
            if isinstance(queries, str):
                queries = [queries]
            if not isinstance(queries, list):
                continue
            clean = [str(q or "").strip() for q in queries if str(q or "").strip()]
            if clean:
                scene_overrides[key] = clean[:8]
    pack["scene_query_overrides"] = scene_overrides
    pack["motion_level"] = str(pack.get("motion_level") or "medium").strip().lower()
    if pack["motion_level"] not in {"low", "medium", "high"}:
        pack["motion_level"] = "medium"
    pack["mood"] = str(pack.get("mood") or "neutral").strip().lower()
    if pack["mood"] not in {"calm", "neutral", "dynamic"}:
        pack["mood"] = "neutral"
    if not isinstance(pack.get("visual_profile"), dict):
        pack["visual_profile"] = {"palette": "neutral", "light": "natural"}
    return pack


def _load() -> dict:
    path = _config_path()
    mtime = path.stat().st_mtime if path.exists() else None
    cache_path = str(path)
    if _CACHE["data"] is not None and _CACHE["mtime"] == mtime and _CACHE["path"] == cache_path:
        return _CACHE["data"]
    config = {"global_banned_tokens": [], "packs": [copy.deepcopy(DEFAULT_PACK)]}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                config = raw
        except Exception:
            config = {"global_banned_tokens": [], "packs": [copy.deepcopy(DEFAULT_PACK)]}
    global_banned = _uniq(config.get("global_banned_tokens") or [])
    packs = []
    for raw_pack in config.get("packs") or []:
        if isinstance(raw_pack, dict):
            packs.append(_normalize_pack(raw_pack, global_banned))
    if not packs:
        packs = [_normalize_pack(copy.deepcopy(DEFAULT_PACK), global_banned)]
    by_id = {p["id"]: p for p in packs}
    if DEFAULT_STYLE_PACK_ID not in by_id:
        by_id[DEFAULT_STYLE_PACK_ID] = _normalize_pack(copy.deepcopy(DEFAULT_PACK), global_banned)
    payload = {"global_banned_tokens": global_banned, "packs": list(by_id.values())}
    _CACHE["path"] = cache_path
    _CACHE["mtime"] = mtime
    _CACHE["data"] = payload
    return payload


def list_style_packs() -> list[dict]:
    return [copy.deepcopy(p) for p in _load()["packs"]]


def get_style_pack(style_pack_id: str | None) -> dict:
    req = str(style_pack_id or "").strip().lower()
    packs = _load()["packs"]
    by_id = {p["id"]: p for p in packs}
    selected = by_id.get(req) if req else None
    if not selected:
        selected = by_id.get(DEFAULT_STYLE_PACK_ID) or packs[0]
    return copy.deepcopy(selected)


def normalize_scene(scene: str, allowed_scenes: list[str]) -> str:
    allowed = [str(x or "").strip().lower() for x in (allowed_scenes or []) if str(x or "").strip()]
    allowed = _uniq(allowed) or list(DEFAULT_ALLOWED_SCENES)
    current = str(scene or "").strip().lower()
    mapped = SCENE_ALIASES.get(current, current)
    if mapped in allowed:
        return mapped
    for candidate in ("work", "people", "city", "nature", "home", "product", "abstract_real"):
        if candidate in allowed:
            return candidate
    return allowed[0]


def snapshot_style_pack(style_pack: dict) -> dict:
    return copy.deepcopy(get_style_pack((style_pack or {}).get("id")))
