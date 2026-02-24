import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from footage.types import VideoResult
from saas_settings import settings


def _index_path() -> Path:
    root = settings.FOOTAGE_CACHE_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root / "index.json"


def _load_index() -> dict:
    path = _index_path()
    if not path.exists():
        return {"version": 1, "items": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "items": []}
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload
    return {"version": 1, "items": []}


def _save_index(data: dict) -> None:
    _index_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def url_hash(url: str) -> str:
    return hashlib.sha1(str(url or "").encode("utf-8")).hexdigest()


def index_lookup(provider: str, video_id: str, download_url: str) -> dict | None:
    idx = _load_index()
    key = url_hash(download_url)
    for item in idx.get("items", []):
        if str(item.get("provider")) != str(provider):
            continue
        if str(item.get("id")) != str(video_id):
            continue
        if str(item.get("url_hash")) != key:
            continue
        rel = str(item.get("local_path") or "").strip()
        if not rel:
            continue
        full = (settings.BASE_DIR / rel).resolve()
        if full.exists() and (settings.BASE_DIR == full or settings.BASE_DIR in full.parents):
            return item
    return None


def remember_index(result: VideoResult, local_path: Path) -> None:
    rel = str(local_path.resolve().relative_to(settings.BASE_DIR)).replace("\\", "/")
    item = {
        "provider": result.provider,
        "id": result.video_id,
        "url": result.download_url,
        "url_hash": url_hash(result.download_url),
        "local_path": rel,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "duration": int(result.duration or 0),
        "width": int(result.width or 0),
        "height": int(result.height or 0),
        "tags_signature": " ".join(sorted([str(x).strip().lower() for x in (result.tags or []) if str(x).strip()]))[:500],
    }
    idx = _load_index()
    filtered = []
    for cur in idx.get("items", []):
        if (
            str(cur.get("provider")) == result.provider
            and str(cur.get("id")) == str(result.video_id)
            and str(cur.get("url_hash")) == item["url_hash"]
        ):
            continue
        filtered.append(cur)
    filtered.append(item)
    idx["items"] = filtered[-20000:]
    _save_index(idx)


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


def stable_cache_file(provider: str, video_id: str, download_url: str, ext: str = ".mp4") -> Path:
    stem = f"{provider}_{video_id}_{url_hash(download_url)[:12]}"
    return settings.FOOTAGE_CACHE_DIR / f"{stem}{ext}"
