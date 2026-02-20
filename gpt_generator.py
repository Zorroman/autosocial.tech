import base64
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

import requests
from openai import OpenAI

from config import Config
from saas_settings import settings

client = OpenAI(api_key=Config.OPENAI_API_KEY)


@dataclass
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int


SYSTEM_PROMPT = "Ты опытный Instagram/Facebook копирайтер. Пиши структурно, конкретно и с сильным CTA."
IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip() or "gpt-image-1"
MEDIA_DIR = Path(__file__).resolve().with_name("generated_media")
MEDIA_DIR.mkdir(exist_ok=True)


def _build_user_prompt(topic: str, category: str | None, tone: str, language: str, long_post_mode: bool) -> str:
    length_hint = "длинный пост с подробным раскрытием" if long_post_mode else "средний пост"
    return (
        f"Сгенерируй {length_hint} для соцсетей на тему '{topic}'. "
        f"Категория: '{category or 'general'}'. Тон: '{tone}'. Язык: '{language}'. "
        "Дай понятный заголовок, 2-3 абзаца и призыв к действию в конце."
    )


def generate_post_with_usage(
    topic: str,
    category: str | None = None,
    tone: str = "friendly",
    language: str = "ru",
    long_post_mode: bool = False,
    max_output_tokens: int = 400,
) -> GenerationResult:
    if settings.USE_MOCK_PROVIDERS or not Config.OPENAI_API_KEY:
        base = f"{topic}: практичный пост\n\n"
        body = (
            base
            + f"Категория: {category or 'general'}. Тон: {tone}. Язык: {language}.\n"
            + "1) Хук в начале.\n2) Полезная мысль.\n3) Призыв к действию."
        )
        input_tokens = random.randint(80, 160)
        output_tokens = min(max_output_tokens, random.randint(220, 360))
        return GenerationResult(text=body, input_tokens=input_tokens, output_tokens=output_tokens)

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(topic, category, tone, language, long_post_mode)},
            ],
            temperature=0.7,
            max_tokens=max_output_tokens,
        )
    except Exception as exc:
        msg = str(exc)
        if "insufficient_quota" in msg or "You exceeded your current quota" in msg or "Error code: 429" in msg:
            base = f"{topic}: практичный пост\n\n"
            body = (
                base
                + f"Категория: {category or 'general'}. Тон: {tone}. Язык: {language}.\n"
                + "1) Хук в начале.\n2) Полезная мысль.\n3) Призыв к действию."
            )
            input_tokens = random.randint(80, 160)
            output_tokens = min(max_output_tokens, random.randint(220, 360))
            return GenerationResult(text=body, input_tokens=input_tokens, output_tokens=output_tokens)
        raise

    usage = response.usage
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    text = (response.choices[0].message.content or "").strip()
    return GenerationResult(text=text, input_tokens=input_tokens, output_tokens=output_tokens)


def generate_post(niche: str, topic: str | None = None) -> str:
    target_topic = topic or niche
    result = generate_post_with_usage(topic=target_topic, category=niche)
    return result.text


def _build_image_prompt(topic: str, category: str | None, tone: str, language: str) -> str:
    return (
        "Create a photorealistic marketing image for social media post. "
        f"Topic: {topic}. Category: {category or 'general'}. Tone: {tone}. Language context: {language}. "
        "The main object must clearly match the topic meaning. "
        "No text, no logos, no watermark, no flat single-color background. Square 1:1."
    )


def build_semantic_fallback_image_url(
    topic: str,
    category: str | None = None,
    tone: str = "friendly",
    language: str = "ru",
) -> str:
    custom_default = (os.getenv("DEFAULT_IG_IMAGE_URL") or "").strip()
    if custom_default:
        return custom_default

    keywords = _semantic_keywords(topic=topic, category=category)
    encoded = quote_plus(",".join(keywords))
    seed = random.randint(10000, 99999)
    remote_url = f"https://loremflickr.com/1080/1080/{encoded}?lock={seed}"
    hosted_url = _mirror_external_image_to_local(remote_url)
    return hosted_url or remote_url


def _mirror_external_image_to_local(url: str) -> str | None:
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return None
        ctype = (resp.headers.get("content-type") or "").lower()
        if "image" not in ctype:
            return None
        ext = ".jpg"
        if "png" in ctype:
            ext = ".png"
        filename = f"ai_{uuid4().hex}{ext}"
        (MEDIA_DIR / filename).write_bytes(resp.content)
        return f"{settings.API_BASE_URL}/api/media/{filename}"
    except Exception:
        return None


def _semantic_keywords(topic: str, category: str | None) -> list[str]:
    category_map = {
        "beauty": ["beauty", "salon", "cosmetology"],
        "auto": ["car", "service", "automotive"],
        "coach": ["coach", "business", "consulting"],
        "ecommerce": ["shop", "ecommerce", "product"],
        "business": ["business", "office", "marketing"],
    }
    tokens = re.findall(r"[a-zA-Z]{4,}", (topic or "").lower())
    picked = [t for t in tokens if t not in {"this", "that", "with", "from", "your"}][:3]
    if picked:
        return picked
    cat = (category or "").strip().lower()
    for key, values in category_map.items():
        if key in cat:
            return values
    return ["business", "marketing", "social"]


def generate_image_url(topic: str, category: str | None = None, tone: str = "friendly", language: str = "ru") -> str | None:
    """
    Generate an image with OpenAI image model and return a public URL
    served by our API (`/api/media/<file>`).
    """
    if settings.USE_MOCK_PROVIDERS or not Config.OPENAI_API_KEY:
        return build_semantic_fallback_image_url(topic=topic, category=category, tone=tone, language=language)

    for _ in range(2):
        try:
            response = client.images.generate(
                model=IMAGE_MODEL,
                prompt=_build_image_prompt(topic=topic, category=category, tone=tone, language=language),
                size="1024x1024",
            )
            data = getattr(response, "data", None) or []
            if not data:
                continue
            item = data[0]
            b64 = getattr(item, "b64_json", None)
            if not b64:
                continue

            image_bytes = base64.b64decode(b64)
            filename = f"ai_{uuid4().hex}.png"
            (MEDIA_DIR / filename).write_bytes(image_bytes)
            return f"{settings.API_BASE_URL}/api/media/{filename}"
        except Exception:
            continue

    return build_semantic_fallback_image_url(topic=topic, category=category, tone=tone, language=language)
