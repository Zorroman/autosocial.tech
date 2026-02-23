import json
import re
from dataclasses import dataclass
from typing import Any

from openai_client import OpenAIClientError, generate_json_with_retry, is_openai_enabled


SUPPORTED_LANGUAGES = {"ru", "ua", "de", "en"}
SUPPORTED_TONES = {"neutral", "friendly", "expert", "sales"}
SUPPORTED_GOALS = {"awareness", "engagement", "lead", "sales"}
SUPPORTED_PLATFORMS = {"facebook", "instagram", "youtube"}


STRATEGY_SCHEMA = {
    "type": "object",
    "required": [
        "audience",
        "angle",
        "context",
        "usp",
        "structure",
        "key_points",
        "hook_ideas",
        "objections_answers",
        "cta_variants",
        "hashtag_sets",
        "visual_ideas",
    ],
}


DRAFT_SCHEMA = {
    "type": "object",
    "required": [
        "platform",
        "variant_index",
        "post_text",
        "title",
        "description",
        "hashtags",
        "cta",
        "asset_ideas",
        "pinned_comment_text",
    ],
}


@dataclass
class ContentGenerationResult:
    strategy: dict
    drafts: list[dict]
    token_input: int
    token_output: int
    status: str = "ok"  # ok | partial
    warnings: list[str] | None = None
    debug_code: str = ""


def _ensure_list_of_strings(value: Any, field: str, min_len: int = 1) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    items = [str(x).strip() for x in value if str(x).strip()]
    if len(items) < min_len:
        raise ValueError(f"{field} must contain at least {min_len} items")
    return items


def _pad_list(items: list[Any], min_len: int, factory) -> list[Any]:
    while len(items) < min_len:
        items.append(factory(len(items)))
    return items


def _normalize_strategy_payload(payload: dict) -> None:
    # Normalize optional structural noise from model and pad minimal required items
    payload["key_points"] = _pad_list(
        [str(x).strip() for x in (payload.get("key_points") or []) if str(x).strip()],
        3,
        lambda i: f"Ключевой тезис {i + 1}",
    )
    payload["hook_ideas"] = _pad_list(
        [str(x).strip() for x in (payload.get("hook_ideas") or []) if str(x).strip()],
        5,
        lambda i: f"Хук {i + 1}: практический инсайт по теме",
    )
    payload["cta_variants"] = _pad_list(
        [str(x).strip() for x in (payload.get("cta_variants") or []) if str(x).strip()],
        3,
        lambda i: f"CTA {i + 1}: Напишите в директ, подберем решение под вашу задачу.",
    )
    payload["visual_ideas"] = _pad_list(
        [str(x).strip() for x in (payload.get("visual_ideas") or []) if str(x).strip()],
        5,
        lambda i: f"Визуал {i + 1}: реалистичный бизнес-сюжет без текста на изображении.",
    )

    raw_objections = payload.get("objections_answers") or []
    normalized_objections: list[dict[str, str]] = []
    if isinstance(raw_objections, list):
        for row in raw_objections:
            if not isinstance(row, dict):
                continue
            objection = str(row.get("objection") or row.get("question") or "").strip()
            answer = str(row.get("answer") or row.get("response") or "").strip()
            if objection and answer:
                normalized_objections.append({"objection": objection, "answer": answer})
    normalized_objections = _pad_list(
        normalized_objections,
        3,
        lambda i: {
            "objection": f"Возражение {i + 1}: это сложно внедрить",
            "answer": "Разбиваем внедрение на 2-3 коротких шага и запускаем без перегруза команды.",
        },
    )
    payload["objections_answers"] = normalized_objections

    hashtag_sets_raw = payload.get("hashtag_sets") or []
    hashtag_sets_norm: list[list[str]] = []
    if isinstance(hashtag_sets_raw, list):
        for tag_set in hashtag_sets_raw:
            if isinstance(tag_set, list):
                cleaned = [str(x).strip() for x in tag_set if str(x).strip()]
                if cleaned:
                    hashtag_sets_norm.append(cleaned)
    hashtag_sets_norm = _pad_list(
        hashtag_sets_norm,
        2,
        lambda _: ["#контент", "#маркетинг", "#бизнес"],
    )
    payload["hashtag_sets"] = [s if len(s) >= 3 else _pad_list(s, 3, lambda __: "#контент") for s in hashtag_sets_norm]


def validate_strategy_payload(payload: dict) -> None:
    _normalize_strategy_payload(payload)
    for key in STRATEGY_SCHEMA["required"]:
        if key not in payload:
            raise ValueError(f"strategy missing field: {key}")
    for key in ["audience", "angle", "context", "usp", "structure"]:
        if not str(payload.get(key) or "").strip():
            raise ValueError(f"strategy field {key} is empty")
    _ensure_list_of_strings(payload.get("key_points"), "key_points", min_len=3)
    _ensure_list_of_strings(payload.get("hook_ideas"), "hook_ideas", min_len=5)
    _ensure_list_of_strings(payload.get("cta_variants"), "cta_variants", min_len=3)

    objections = payload.get("objections_answers")
    if not isinstance(objections, list) or len(objections) < 3:
        raise ValueError("objections_answers must contain at least 3 items")
    for row in objections:
        if not isinstance(row, dict):
            raise ValueError("objections_answers item must be object")
        if not str(row.get("objection") or "").strip():
            raise ValueError("objection is empty")
        if not str(row.get("answer") or "").strip():
            raise ValueError("answer is empty")

    hashtag_sets = payload.get("hashtag_sets")
    if not isinstance(hashtag_sets, list) or len(hashtag_sets) < 2:
        raise ValueError("hashtag_sets must contain at least 2 sets")
    for tag_set in hashtag_sets:
        _ensure_list_of_strings(tag_set, "hashtag_set", min_len=3)

    _ensure_list_of_strings(payload.get("visual_ideas"), "visual_ideas", min_len=5)


def validate_draft_payload(payload: dict) -> None:
    for key in DRAFT_SCHEMA["required"]:
        if key not in payload:
            raise ValueError(f"draft missing field: {key}")
    platform = str(payload.get("platform") or "").strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError("draft platform is invalid")
    variant_index = int(payload.get("variant_index") or 0)
    if variant_index <= 0:
        raise ValueError("variant_index must be positive")
    if not str(payload.get("post_text") or "").strip():
        raise ValueError("post_text is empty")
    _ensure_list_of_strings(payload.get("hashtags"), "hashtags", min_len=1)
    _ensure_list_of_strings(payload.get("asset_ideas"), "asset_ideas", min_len=3)
    if platform == "youtube":
        if not str(payload.get("title") or "").strip():
            raise ValueError("youtube title is required")
        if not str(payload.get("description") or "").strip():
            raise ValueError("youtube description is required")
        if not str(payload.get("pinned_comment_text") or "").strip():
            raise ValueError("youtube pinned_comment_text is required")


def _strategy_system_prompt() -> str:
    return (
        "You are a head-of-social content strategist. "
        "Build practical strategy from user idea with clear positioning and structure. "
        "Never invent specific product facts if offer is empty. "
        "Visual ideas must be image concepts without text on image. "
        "Return JSON only."
    )


def _strategy_user_prompt(*, topic: str, offer: str | None, language: str, tone: str, goal: str, platforms: list[str]) -> str:
    schema_hint = {
        "audience": "string",
        "angle": "string",
        "context": "string",
        "usp": "string",
        "structure": "string",
        "key_points": ["string", "string", "string"],
        "hook_ideas": ["string", "string", "string", "string", "string"],
        "objections_answers": [{"objection": "string", "answer": "string"}],
        "cta_variants": ["string", "string", "string"],
        "hashtag_sets": [["#tag1", "#tag2", "#tag3"], ["#tagA", "#tagB", "#tagC"]],
        "visual_ideas": ["string", "string", "string", "string", "string"],
    }
    return (
        f"Input\n"
        f"- topic: {topic}\n"
        f"- offer: {offer or ''}\n"
        f"- language: {language}\n"
        f"- tone: {tone}\n"
        f"- goal: {goal}\n"
        f"- platforms: {', '.join(platforms)}\n\n"
        "Task\n"
        "- Expand topic with context, angle and structure.\n"
        "- Return strict JSON with this schema:\n"
        f"{json.dumps(schema_hint, ensure_ascii=False)}"
    )


def _draft_system_prompt() -> str:
    return (
        "You are a senior copywriter. "
        "Write practical, readable social content. "
        "No fake product facts. If offer is empty keep messaging universal. "
        "Return JSON only."
    )


def _draft_constraints(platform: str) -> str:
    if platform == "facebook":
        return "Facebook: 800-1500 chars, max 1-2 emojis per paragraph, clear CTA."
    if platform == "instagram":
        return "Instagram: 900-1800 chars, strong first-line hook, short paragraphs, 8-15 hashtags."
    return (
        "YouTube: title <=70 chars, description 1000-2500 chars, tags 10-20, "
        "exactly 3 hashtags, include pinned_comment_text."
    )


def _draft_user_prompt(
    *,
    strategy: dict,
    topic: str,
    offer: str | None,
    language: str,
    tone: str,
    goal: str,
    platform: str,
    variant_index: int,
) -> str:
    schema_hint = {
        "platform": platform,
        "variant_index": variant_index,
        "post_text": "string",
        "title": "string or null",
        "description": "string or null",
        "hashtags": ["#tag1", "#tag2"],
        "cta": "string",
        "asset_ideas": ["string", "string", "string"],
        "pinned_comment_text": "string or null",
    }
    return (
        f"Input\n"
        f"- topic: {topic}\n"
        f"- offer: {offer or ''}\n"
        f"- language: {language}\n"
        f"- tone: {tone}\n"
        f"- goal: {goal}\n"
        f"- platform: {platform}\n"
        f"- variant_index: {variant_index}\n"
        f"- constraints: {_draft_constraints(platform)}\n\n"
        f"Strategy JSON:\n{json.dumps(strategy, ensure_ascii=False)}\n\n"
        "Return strict JSON with this schema:\n"
        f"{json.dumps(schema_hint, ensure_ascii=False)}"
    )


def _mock_strategy(topic: str, offer: str | None, goal: str) -> dict:
    offer_part = f" Offer context: {offer}." if offer else ""
    return {
        "audience": "Small business owners and marketing specialists",
        "angle": f"Practical breakdown of '{topic}' with concrete actions",
        "context": f"Audience needs a simple way to apply '{topic}' for {goal}.{offer_part}",
        "usp": "Clear structure that can be implemented immediately",
        "structure": "Hook -> problem -> 3-5 actions -> mini case -> CTA",
        "key_points": [
            f"Why '{topic}' impacts {goal}",
            "Common mistakes and how to avoid them",
            "Quick actions for immediate momentum",
            "How to convert insights into CTA",
        ],
        "hook_ideas": [
            f"Most teams miss this in '{topic}'",
            f"3 mistakes in '{topic}' that cost you growth",
            f"How to improve '{topic}' in one week",
            f"Checklist to validate your '{topic}' approach",
            f"What to fix first in '{topic}'",
        ],
        "objections_answers": [
            {"objection": "Too complex for my team", "answer": "Use step-by-step rollout over 3 days."},
            {"objection": "No time for content", "answer": "Reuse one idea across several formats."},
            {"objection": "Our niche is different", "answer": "Framework is universal, examples are flexible."},
        ],
        "cta_variants": [
            "Reply with PLAN and get a quick checklist.",
            "Save this post and test step one today.",
            "Send a DM to get a tailored action map.",
        ],
        "hashtag_sets": [
            ["#marketing", "#content", "#business", "#growth", "#smm"],
            ["#digital", "#strategy", "#leadgen", "#socialmedia", "#branding"],
        ],
        "visual_ideas": [
            "Desk setup with notebook and laptop, no text in frame",
            "Team meeting around whiteboard, no readable text",
            "Smartphone and analytics dashboard blurred, no text",
            "Minimal business flat lay with neutral props",
            "Before/after workspace composition showing process",
        ],
    }


def _mock_draft(*, platform: str, variant_index: int, topic: str, strategy: dict) -> dict:
    hashtags = strategy.get("hashtag_sets", [["#content", "#marketing"]])[variant_index % 2]
    if platform == "youtube":
        return {
            "platform": "youtube",
            "variant_index": variant_index,
            "post_text": f"Deep breakdown of {topic} with practical steps and examples.",
            "title": f"{topic}: practical guide",
            "description": (
                f"In this video we break down {topic} with concrete actions, mistakes to avoid and a practical plan.\n\n"
                "Timestamps:\n"
                "00:00 Intro\n"
                "01:30 Core problem\n"
                "03:45 Action framework\n"
                "06:20 Mini-case\n"
                "08:10 CTA"
            ),
            "hashtags": hashtags[:3],
            "cta": strategy.get("cta_variants", ["Subscribe for next steps"])[0],
            "asset_ideas": strategy.get("visual_ideas", [])[:3],
            "pinned_comment_text": "Which action will you test first? Write step number in comments.",
        }
    return {
        "platform": platform,
        "variant_index": variant_index,
        "post_text": (
            f"Hook: {strategy.get('hook_ideas', [topic])[0]}\n\n"
            f"Topic '{topic}' works best with structure: {strategy.get('structure', '')}.\n"
            "Below are practical steps you can apply today.\n\n"
            f"CTA: {strategy.get('cta_variants', ['Save this post'])[0]}"
        ),
        "title": None,
        "description": None,
        "hashtags": hashtags,
        "cta": strategy.get("cta_variants", ["Save this post"])[0],
        "asset_ideas": strategy.get("visual_ideas", [])[:3],
        "pinned_comment_text": None,
    }


def _goal_label(goal: str) -> str:
    mapping = {
        "sales": "продажа",
        "lead": "лид",
        "engagement": "вовлечение",
        "awareness": "узнаваемость",
    }
    return mapping.get(str(goal or "").strip().lower(), "вовлечение")


def _fallback_strategy(topic: str, offer: str | None, goal: str) -> dict:
    strategy = _mock_strategy(topic=topic, offer=offer, goal=goal)
    strategy["angle"] = f"Практический разбор темы «{topic}» под цель: {_goal_label(goal)}"
    strategy["context"] = (
        f"Аудитории нужен понятный сценарий действий по теме «{topic}»."
        + (f" Оффер: {offer}." if offer else "")
    )
    _normalize_strategy_payload(strategy)
    return strategy


def _extract_hashtags_from_text(text: str, *, limit: int = 12) -> list[str]:
    found = re.findall(r"#([\wа-яА-Я0-9_]+)", text or "", flags=re.U)
    tags: list[str] = []
    for token in found:
        val = f"#{str(token).lower()}"
        if val not in tags:
            tags.append(val)
        if len(tags) >= limit:
            break
    if not tags:
        tags = ["#контент", "#маркетинг", "#бизнес"]
    return tags


def _extract_cta_from_text(text: str) -> str:
    lines = [str(x).strip() for x in str(text or "").splitlines() if str(x).strip()]
    for line in reversed(lines):
        low = line.lower()
        if any(k in low for k in ["напишите", "оставьте", "перейдите", "запишитесь", "купите", "подпишитесь"]):
            return line
    return "Напишите в директ, чтобы получить детали."


def _ensure_platform_draft_shape(draft: dict, *, platform: str, variant_index: int) -> dict:
    out = dict(draft or {})
    out["platform"] = platform
    out["variant_index"] = int(variant_index or 1)
    out["post_text"] = str(out.get("post_text") or "").strip()
    out["cta"] = str(out.get("cta") or "").strip()
    out["hashtags"] = [str(x).strip() for x in (out.get("hashtags") or []) if str(x).strip()]
    out["asset_ideas"] = [str(x).strip() for x in (out.get("asset_ideas") or []) if str(x).strip()]
    if not out["post_text"]:
        out["post_text"] = f"{platform.title()}: {variant_index}. {out.get('title') or 'Практический пост по теме.'}"
    if not out["cta"]:
        out["cta"] = _extract_cta_from_text(out["post_text"])
    if not out["hashtags"]:
        out["hashtags"] = _extract_hashtags_from_text(out["post_text"])
    if len(out["asset_ideas"]) < 3:
        while len(out["asset_ideas"]) < 3:
            out["asset_ideas"].append("Реалистичный кадр по теме без текста на изображении.")
    if platform == "youtube":
        out["title"] = str(out.get("title") or "").strip() or "Практический разбор темы"
        out["description"] = str(out.get("description") or "").strip() or out["post_text"]
        out["pinned_comment_text"] = str(out.get("pinned_comment_text") or "").strip() or "Какой шаг вы внедрите первым?"
        out["hashtags"] = out["hashtags"][:3]
    else:
        out["title"] = out.get("title") or None
        out["description"] = out.get("description") or None
        out["pinned_comment_text"] = None
    return out


def _generate_simplified_draft(
    *,
    topic: str,
    offer: str | None,
    language: str,
    tone: str,
    goal: str,
    platform: str,
    variant_index: int,
) -> tuple[dict, int, int]:
    schema_hint = {
        "post_text": "string",
        "cta": "string",
        "hashtags": ["#tag1", "#tag2", "#tag3"],
        "title": "string_or_empty",
        "description": "string_or_empty",
    }

    def _validator(payload: dict) -> None:
        if not isinstance(payload, dict):
            raise ValueError("payload must be object")
        if not str(payload.get("post_text") or "").strip():
            raise ValueError("post_text is required")
        tags = payload.get("hashtags")
        if not isinstance(tags, list):
            raise ValueError("hashtags must be list")

    system = (
        "You are a social media copywriter. Return compact JSON only. "
        "No extra keys."
    )
    user = (
        f"topic: {topic}\n"
        f"offer: {offer or ''}\n"
        f"language: {language}\n"
        f"tone: {tone}\n"
        f"goal: {goal}\n"
        f"platform: {platform}\n"
        f"variant: {variant_index}\n"
        f"schema: {json.dumps(schema_hint, ensure_ascii=False)}"
    )
    res = generate_json_with_retry(
        system_prompt=system,
        user_prompt=user,
        validator=_validator,
        max_output_tokens=900 if platform != "youtube" else 1400,
        temperature=0.55,
    )
    payload = _ensure_platform_draft_shape(
        {
            "platform": platform,
            "variant_index": variant_index,
            "post_text": payload_get(res.payload, "post_text"),
            "title": payload_get(res.payload, "title"),
            "description": payload_get(res.payload, "description"),
            "hashtags": res.payload.get("hashtags") or [],
            "cta": payload_get(res.payload, "cta"),
            "asset_ideas": [
                "Крупный план продукта/услуги без текста",
                "Сцена использования в реальной среде",
                "До/после или процесс в 3 шагах",
            ],
            "pinned_comment_text": "Напишите ваш вопрос в комментариях.",
        },
        platform=platform,
        variant_index=variant_index,
    )
    return payload, res.input_tokens, res.output_tokens


def payload_get(payload: dict, key: str) -> str:
    return str((payload or {}).get(key) or "").strip()


def _generate_free_text_fallback_draft(
    *,
    platform: str,
    variant_index: int,
    topic: str,
    offer: str | None,
    goal: str,
) -> dict:
    goal_part = {
        "sales": "Сфокусируйтесь на выгоде и конкретном действии клиента.",
        "lead": "Предложите понятный следующий шаг для заявки.",
        "awareness": "Добавьте ценность и запоминаемый инсайт.",
        "engagement": "Добавьте вопрос в конце для обсуждения.",
    }.get(goal, "Добавьте практический вывод и CTA.")
    text = (
        f"Тема: {topic}\n\n"
        f"{goal_part}\n"
        f"{('Оффер: ' + offer) if offer else ''}\n\n"
        "1) Проблема аудитории.\n"
        "2) Решение и понятный план.\n"
        "3) CTA: Напишите в директ, чтобы получить детали."
    ).strip()
    return _ensure_platform_draft_shape(
        {
            "platform": platform,
            "variant_index": variant_index,
            "post_text": text,
            "title": f"{topic}: практический разбор" if platform == "youtube" else None,
            "description": text if platform == "youtube" else None,
            "hashtags": _extract_hashtags_from_text(text),
            "cta": "Напишите в директ, чтобы получить детали.",
            "asset_ideas": [
                "Реалистичная сцена по теме без текста",
                "Процесс/workflow в рабочем окружении",
                "Крупный план ключевого элемента оффера",
            ],
            "pinned_comment_text": "Какой шаг вы попробуете первым?" if platform == "youtube" else None,
        },
        platform=platform,
        variant_index=variant_index,
    )


def generate_quick_suggestions(
    *,
    topic: str,
    offer: str | None,
    goal: str,
    tone: str,
    language: str,
) -> dict:
    if not str(topic or "").strip():
        raise ValueError("topic is required")
    if not is_openai_enabled():
        base = str(topic).strip()
        return {
            "status": "ok",
            "hook": f"{base}: что важно проверить до старта?",
            "angles": [
                f"3 частые ошибки в теме «{base}»",
                f"Чек-лист внедрения «{base}» за 1 день",
                f"Кейс: как применили «{base}» и получили результат",
            ],
            "cta_variants": [
                "Напишите в директ — отправим чек-лист.",
                "Оставьте «ПЛАН» в комментариях — пришлём шаги.",
                "Сохраните пост и внедрите первый шаг сегодня.",
            ],
            "warnings": [],
            "debug_code": "mock",
        }

    schema = {
        "hook": "string",
        "angles": ["string", "string", "string"],
        "cta_variants": ["string", "string", "string"],
    }

    def _validator(payload: dict) -> None:
        if not str(payload.get("hook") or "").strip():
            raise ValueError("hook is required")
        _ensure_list_of_strings(payload.get("angles"), "angles", min_len=3)
        _ensure_list_of_strings(payload.get("cta_variants"), "cta_variants", min_len=3)

    try:
        res = generate_json_with_retry(
            system_prompt="Return short practical suggestions in JSON only.",
            user_prompt=(
                f"topic: {topic}\n"
                f"offer: {offer or ''}\n"
                f"goal: {goal}\n"
                f"tone: {tone}\n"
                f"language: {language}\n"
                f"schema: {json.dumps(schema, ensure_ascii=False)}"
            ),
            validator=_validator,
            max_output_tokens=600,
            temperature=0.5,
        )
        payload = res.payload
        return {
            "status": "ok",
            "hook": str(payload.get("hook") or "").strip(),
            "angles": _ensure_list_of_strings(payload.get("angles"), "angles", min_len=3)[:3],
            "cta_variants": _ensure_list_of_strings(payload.get("cta_variants"), "cta_variants", min_len=3)[:3],
            "warnings": [],
            "debug_code": "",
        }
    except Exception:
        return {
            "status": "partial",
            "hook": f"{topic}: что проверить перед запуском?",
            "angles": [
                f"Пошаговый разбор «{topic}»",
                f"Типичные ошибки в «{topic}»",
                f"Практический кейс по «{topic}»",
            ],
            "cta_variants": [
                "Напишите в директ, подберем решение под задачу.",
                "Оставьте комментарий и получите шаблон.",
                "Сохраните пост и внедрите первый шаг сегодня.",
            ],
            "warnings": ["AI suggestions fallback"],
            "debug_code": "suggest_fallback",
        }


def rewrite_caption_safe(
    *,
    caption: str,
    instruction: str,
    goal: str,
    tone: str,
    language: str,
) -> dict:
    src = str(caption or "").strip()
    if not src:
        raise ValueError("caption is required")

    if not is_openai_enabled():
        return {
            "status": "ok",
            "caption": _local_rewrite(src, instruction),
            "cta": _extract_cta_from_text(src),
            "hashtags": _extract_hashtags_from_text(src),
            "warnings": [],
            "debug_code": "mock",
        }

    schema = {"caption": "string", "cta": "string", "hashtags": ["#tag1", "#tag2"]}

    def _validator(payload: dict) -> None:
        if not str(payload.get("caption") or "").strip():
            raise ValueError("caption is required")
        if not isinstance(payload.get("hashtags"), list):
            raise ValueError("hashtags must be list")

    try:
        res = generate_json_with_retry(
            system_prompt="Rewrite caption with requested style. Return JSON only.",
            user_prompt=(
                f"caption: {src}\n"
                f"instruction: {instruction}\n"
                f"goal: {goal}\n"
                f"tone: {tone}\n"
                f"language: {language}\n"
                f"schema: {json.dumps(schema, ensure_ascii=False)}"
            ),
            validator=_validator,
            max_output_tokens=900,
            temperature=0.55,
        )
        payload = res.payload
        new_caption = str(payload.get("caption") or "").strip()
        tags = [str(x).strip() for x in (payload.get("hashtags") or []) if str(x).strip()]
        if not tags:
            tags = _extract_hashtags_from_text(new_caption or src)
        return {
            "status": "ok",
            "caption": new_caption,
            "cta": str(payload.get("cta") or "").strip() or _extract_cta_from_text(new_caption or src),
            "hashtags": tags[:15],
            "warnings": [],
            "debug_code": "",
        }
    except Exception:
        rewritten = _local_rewrite(src, instruction)
        return {
            "status": "partial",
            "caption": rewritten,
            "cta": _extract_cta_from_text(rewritten),
            "hashtags": _extract_hashtags_from_text(rewritten),
            "warnings": ["AI rewrite fallback"],
            "debug_code": "rewrite_fallback",
        }


def _local_rewrite(text: str, instruction: str) -> str:
    value = str(text or "").strip()
    key = str(instruction or "").strip().lower()
    if key in {"короче", "shorter"}:
        sentences = re.split(r"(?<=[.!?])\s+", value)
        return " ".join(sentences[: max(1, min(3, len(sentences)))])
    if key in {"длиннее", "longer"}:
        return f"{value}\n\nДобавьте конкретный пример внедрения и ожидаемый результат в цифрах."
    if "прода" in key:
        return f"{value}\n\nЕсли хотите такой же результат, напишите в директ — подберем решение под вашу задачу."
    if "эксперт" in key:
        return f"{value}\n\nПрактический совет: начните с минимального теста и измерьте результат через 7 дней."
    if "эмоц" in key:
        return f"{value}\n\nЭто действительно может снять хаос в контенте и вернуть уверенность в результате."
    return value


def generate_strategy_and_drafts(
    *,
    topic: str,
    offer: str | None,
    language: str,
    tone: str,
    goal: str,
    platforms: list[str],
    variants: int,
) -> ContentGenerationResult:
    language = str(language or "ru").strip().lower()
    tone = str(tone or "neutral").strip().lower()
    goal = str(goal or "engagement").strip().lower()
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("language must be one of ru/ua/de/en")
    if tone not in SUPPORTED_TONES:
        raise ValueError("tone must be one of neutral/friendly/expert/sales")
    if goal not in SUPPORTED_GOALS:
        raise ValueError("goal must be one of awareness/engagement/lead/sales")
    if not topic.strip():
        raise ValueError("topic is required")
    if not platforms:
        raise ValueError("platforms is required")
    platforms = [p for p in platforms if p in SUPPORTED_PLATFORMS]
    if not platforms:
        raise ValueError("platforms must contain facebook/instagram/youtube")
    variants = max(1, min(int(variants or 1), 3))

    warnings: list[str] = []
    debug_code = ""
    if not is_openai_enabled():
        strategy = _mock_strategy(topic=topic, offer=offer, goal=goal)
        drafts = []
        for platform in platforms:
            for idx in range(1, variants + 1):
                draft = _mock_draft(platform=platform, variant_index=idx, topic=topic, strategy=strategy)
                validate_draft_payload(draft)
                drafts.append(draft)
        return ContentGenerationResult(strategy=strategy, drafts=drafts, token_input=0, token_output=0, status="ok", warnings=[], debug_code="mock")

    strategy = None
    total_in = 0
    total_out = 0
    try:
        strategy_res = generate_json_with_retry(
            system_prompt=_strategy_system_prompt(),
            user_prompt=_strategy_user_prompt(
                topic=topic,
                offer=offer,
                language=language,
                tone=tone,
                goal=goal,
                platforms=platforms,
            ),
            validator=validate_strategy_payload,
            max_output_tokens=1800,
            temperature=0.4,
        )
        strategy = strategy_res.payload
        total_in += strategy_res.input_tokens
        total_out += strategy_res.output_tokens
    except Exception:
        strategy = _fallback_strategy(topic=topic, offer=offer, goal=goal)
        warnings.append("Стратегия частично восстановлена fallback-логикой.")
        debug_code = "strategy_fallback"

    drafts: list[dict] = []
    for platform in platforms:
        for idx in range(1, variants + 1):
            try:
                draft_res = generate_json_with_retry(
                    system_prompt=_draft_system_prompt(),
                    user_prompt=_draft_user_prompt(
                        strategy=strategy,
                        topic=topic,
                        offer=offer,
                        language=language,
                        tone=tone,
                        goal=goal,
                        platform=platform,
                        variant_index=idx,
                    ),
                    validator=validate_draft_payload,
                    max_output_tokens=2200 if platform == "youtube" else 1400,
                    temperature=0.65,
                )
                total_in += draft_res.input_tokens
                total_out += draft_res.output_tokens
                drafts.append(_ensure_platform_draft_shape(draft_res.payload, platform=platform, variant_index=idx))
                continue
            except Exception:
                warnings.append(f"{platform} v{idx}: full-schema не прошла, применен simplified fallback.")
                debug_code = (debug_code + "|draft_schema_fallback").strip("|")

            try:
                fallback_draft, in_tok, out_tok = _generate_simplified_draft(
                    topic=topic,
                    offer=offer,
                    language=language,
                    tone=tone,
                    goal=goal,
                    platform=platform,
                    variant_index=idx,
                )
                total_in += in_tok
                total_out += out_tok
                drafts.append(fallback_draft)
                continue
            except Exception:
                warnings.append(f"{platform} v{idx}: simplified не прошел, применен free-text fallback.")
                debug_code = (debug_code + "|draft_text_fallback").strip("|")

            drafts.append(
                _generate_free_text_fallback_draft(
                    platform=platform,
                    variant_index=idx,
                    topic=topic,
                    offer=offer,
                    goal=goal,
                )
            )

    status = "partial" if warnings else "ok"
    return ContentGenerationResult(
        strategy=strategy,
        drafts=drafts,
        token_input=total_in,
        token_output=total_out,
        status=status,
        warnings=warnings,
        debug_code=debug_code,
    )


__all__ = [
    "ContentGenerationResult",
    "OpenAIClientError",
    "generate_strategy_and_drafts",
    "generate_quick_suggestions",
    "rewrite_caption_safe",
    "validate_strategy_payload",
    "validate_draft_payload",
    "STRATEGY_SCHEMA",
    "DRAFT_SCHEMA",
]
