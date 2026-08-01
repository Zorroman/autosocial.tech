import random
from dataclasses import dataclass

from openai import OpenAI

from config import Config
from app_settings import settings

client = OpenAI(api_key=Config.OPENAI_API_KEY)


@dataclass
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int


SYSTEM_PROMPT = "Ты опытный Instagram/Facebook копирайтер. Пиши структурно, конкретно и с сильным CTA."


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
        hooks = [
            f"{topic}: что важно учесть перед запуском",
            f"{topic}: короткий разбор без воды",
            f"{topic}: 3 рабочих шага на сегодня",
            f"{topic}: как получить результат быстрее",
        ]
        values = [
            "Покажите клиенту конкретную выгоду в первой строке.",
            "Добавьте один понятный кейс, чтобы снять возражения.",
            "Закончите пост четким действием: написать, оставить заявку, перейти по ссылке.",
            "Избегайте общих фраз: дайте цифру, срок или пример.",
        ]
        ctas = [
            "Напишите в директ — подберем формат под ваш бизнес.",
            "Сохраните пост и протестируйте этот сценарий сегодня.",
            "Нужен шаблон под вашу нишу? Ответьте в комментариях.",
        ]
        random.shuffle(values)
        body = (
            f"{random.choice(hooks)}\n\n"
            f"Категория: {category or 'general'} • Тон: {tone} • Язык: {language}\n"
            f"1) {values[0]}\n"
            f"2) {values[1]}\n"
            f"3) {values[2]}\n\n"
            f"{random.choice(ctas)}\n"
            "#маркетинг #smm #контент"
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
            hooks = [
                f"{topic}: краткий план действий",
                f"{topic}: 3 шага для роста",
                f"{topic}: как избежать типичных ошибок",
            ]
            body = (
                f"{random.choice(hooks)}\n\n"
                f"Категория: {category or 'general'} • Тон: {tone} • Язык: {language}\n"
                "1) Дайте конкретику в заголовке.\n"
                "2) Покажите пользу на примере.\n"
                "3) Завершите пост четким CTA.\n\n"
                "Напишите в директ, чтобы получить адаптированный шаблон."
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


def generate_structured_text_with_usage(
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int = 700,
    temperature: float = 0.6,
) -> GenerationResult:
    if settings.USE_MOCK_PROVIDERS or not Config.OPENAI_API_KEY:
        text = (
            "{\n"
            '  "title": "YouTube: практический разбор темы",\n'
            '  "hook": "Смотрите до конца: в конце дам готовый шаблон.",\n'
            '  "outline": ["Проблема", "Решение", "Пример", "Действие"],\n'
            '  "cta": "Подписка + комментарий с запросом шаблона"\n'
            "}"
        )
        return GenerationResult(text=text, input_tokens=120, output_tokens=min(max_output_tokens, 220))

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_output_tokens,
    )
    usage = response.usage
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    text = (response.choices[0].message.content or "").strip()
    return GenerationResult(text=text, input_tokens=input_tokens, output_tokens=output_tokens)


def generate_image_url(*args, **kwargs):
    raise RuntimeError("AI image generation is disabled. Use Pexels/Pixabay media pipeline.")
