import random
from dataclasses import dataclass

from openai import OpenAI

from config import Config
from saas_settings import settings

client = OpenAI(api_key=Config.OPENAI_API_KEY)


@dataclass
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int


SYSTEM_PROMPT = "Ты опытный Instagram/Facebook копирайтер. Пиши по делу, структурно и с сильным CTA."


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
        # Dev-friendly fallback: if OpenAI quota/rate issues happen, generate a structured mock
        # so the product remains usable locally.
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
