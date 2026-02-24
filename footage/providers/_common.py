import hashlib
import json
from pathlib import Path

import requests

from saas_settings import settings


def _json_cache_path() -> Path:
    root = settings.FOOTAGE_CACHE_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root / "cache_index.json"


def _load_cache_index() -> dict:
    path = _json_cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache_index(data: dict) -> None:
    path = _json_cache_path()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def cache_key(provider: str, video_id: str, download_url: str) -> str:
    raw = f"{provider}:{video_id}:{download_url}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def cached_file_path(key: str, ext: str = ".mp4") -> Path:
    return settings.FOOTAGE_CACHE_DIR / f"{key}{ext}"


def get_cached_path(key: str) -> Path | None:
    idx = _load_cache_index()
    rel = str(idx.get(key) or "").strip()
    if not rel:
        return None
    full = (settings.BASE_DIR / rel).resolve()
    if full.exists() and settings.BASE_DIR in full.parents:
        return full
    return None


def remember_cache(key: str, file_path: Path) -> None:
    idx = _load_cache_index()
    idx[key] = str(file_path.resolve().relative_to(settings.BASE_DIR)).replace("\\", "/")
    _save_cache_index(idx)


def download_to_path(url: str, target: Path, retries: int = 3, timeout: int = 120) -> Path:
    last_error = "download_failed"
    for attempt in range(retries):
        try:
            with requests.get(url, timeout=timeout, stream=True) as res:
                if res.status_code != 200:
                    last_error = f"http_{res.status_code}"
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as f:
                    for chunk in res.iter_content(chunk_size=1024 * 512):
                        if chunk:
                            f.write(chunk)
                if target.exists() and target.stat().st_size > 0:
                    return target
        except Exception as exc:
            last_error = str(exc)
        if attempt < retries - 1:
            continue
    raise RuntimeError(f"video_download_failed: {last_error}")
