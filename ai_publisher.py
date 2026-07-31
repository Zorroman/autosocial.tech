"""AI Publisher — prepares everything a rendered video needs to go to YouTube.

Produces a metadata package with MULTIPLE title/description alternatives (plus a
selected index), tags, hashtags, a pinned comment, privacy, and a thumbnail
built from the best frame of the rendered video with an auto-generated overlay
hook. Nothing is uploaded here — this only prepares the package.

Future learning: generate_publish_package() accepts an optional
`analytics_context` (CTR / retention / watch time / impressions from past
videos). It is unused today but recorded in generation_meta so the station can
later be trained to prefer metadata that historically performed better.
"""
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from saas_settings import settings

AI_PUBLISHER_VERSION = "1"


def _clean_list(v, n):
    out = []
    for x in (v or []):
        s = str(x).strip()
        if s and s not in out:
            out.append(s)
        if len(out) >= n:
            break
    return out


def _fallback_package(topic: str, privacy: str) -> dict:
    t = (topic or "Видео").strip()
    return {
        "title_options": [t[:95], f"{t}: главное за 60 секунд"[:95], f"{t} — что это значит?"[:95]],
        "description_options": [f"{t}\n\nСмотрите до конца. #shorts", f"Коротко и по делу: {t}."],
        "tags": [w.lower() for w in t.split()[:8]],
        "hashtags": ["#shorts"],
        "pinned_comment": "А что думаете вы? Пишите в комментариях 👇",
        "overlay_text": " ".join(t.split()[:3])[:24],
        "selected_title": 0,
        "selected_description": 0,
        "privacy": privacy,
        "schedule": None,
        "thumbnail": None,
        "generation_meta": {"model": "fallback", "version": AI_PUBLISHER_VERSION,
                            "generated_at": datetime.utcnow().isoformat(), "analytics_used": False},
    }


def generate_publish_package(*, topic: str, script_text: str = "", language: str = "ru",
                             style: str = "", niche: str = "", offer: str | None = None,
                             privacy: str = "public", title_count: int = 4,
                             description_count: int = 2, analytics_context=None) -> dict:
    """Generate the YouTube metadata package (alternatives + selection)."""
    topic = (topic or "").strip()
    from openai_client import OpenAIClientError, generate_json_with_retry, is_openai_enabled
    if not topic or not is_openai_enabled():
        return _fallback_package(topic, privacy)

    def _validator(payload: dict) -> None:
        if not isinstance(payload.get("title_options"), list) or not payload["title_options"]:
            raise ValueError("title_options required")
        if not isinstance(payload.get("description_options"), list) or not payload["description_options"]:
            raise ValueError("description_options required")

    system_prompt = (
        "Ты — редактор YouTube-канала. По теме и сценарию ролика подготовь метаданные для публикации. "
        "Верни СТРОГО JSON с ключами: title_options (массив из "
        f"{title_count} разных цепляющих заголовков до 95 символов, максимум 1 эмодзи), "
        f"description_options (массив из {description_count} описаний по 2–4 предложения, "
        "в конце уместные хэштеги), tags (8–12 ключевых слов в нижнем регистре), "
        "hashtags (3–5 строк с #), pinned_comment (1 вовлекающая строка-вопрос), "
        "overlay_text (короткий хук 2–4 слова для обложки, БЕЗ эмодзи). "
        f"Язык — {language}. Без пояснений, только JSON."
    )
    user_prompt = (
        f"niche: {niche}\nstyle: {style}\ntopic: {topic}\n"
        f"script:\n{(script_text or '')[:1600]}\n"
    )
    try:
        result = generate_json_with_retry(
            system_prompt=system_prompt, user_prompt=user_prompt,
            validator=_validator, max_output_tokens=900, temperature=0.7,
        )
        p = result.payload
    except (OpenAIClientError, Exception):  # noqa: BLE001 — degrade to fallback
        return _fallback_package(topic, privacy)

    titles = _clean_list(p.get("title_options"), title_count) or [topic[:95]]
    descs = _clean_list(p.get("description_options"), description_count) or [topic]
    return {
        "title_options": [t[:95] for t in titles],
        "description_options": descs,
        "tags": _clean_list(p.get("tags"), 12),
        "hashtags": _clean_list(p.get("hashtags"), 5) or ["#shorts"],
        "pinned_comment": str(p.get("pinned_comment") or "").strip(),
        "overlay_text": str(p.get("overlay_text") or (" ".join(topic.split()[:3]))).strip()[:24],
        "selected_title": 0,
        "selected_description": 0,
        "privacy": privacy,
        "schedule": None,
        "thumbnail": None,
        "generation_meta": {
            "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            "version": AI_PUBLISHER_VERSION,
            "generated_at": datetime.utcnow().isoformat(),
            "analytics_used": bool(analytics_context),
        },
    }


def build_thumbnail(video_path: str, project_id: int) -> dict | None:
    """Extract the most representative frame of the rendered video as the base
    thumbnail. Overlay text is stored in the package and composited later /
    in the UI (editable, no font dependency here). Returns a thumbnail dict."""
    src = Path(video_path)
    if not src.exists():
        return None
    out_dir = (settings.OUTPUT_DIR / "thumbnails")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"project_{project_id}.jpg"
    try:
        proc = subprocess.run(
            [settings.FFMPEG_BIN, "-y", "-i", str(src),
             "-vf", "thumbnail,scale=1280:-2", "-frames:v", "1", str(out)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0 or not out.exists() or out.stat().st_size < 1000:
            return None
    except Exception:
        return None
    try:
        rel = out.resolve().relative_to(settings.BASE_DIR)
        url = f"/api/media/{rel}"
    except Exception:
        url = None
    return {"path": str(out), "url": url, "source": "auto"}
