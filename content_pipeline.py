import json
import re
from dataclasses import dataclass
from typing import Any

from openai_client import OpenAIClientError, generate_json_with_retry, is_openai_enabled


SUPPORTED_LANGUAGES = {"ru", "ua", "de", "en"}
SUPPORTED_TONES = {"neutral", "friendly", "expert", "sales"}
SUPPORTED_GOALS = {"awareness", "engagement", "lead", "sales", "trust"}
SUPPORTED_PLATFORMS = {"facebook", "instagram", "youtube"}

META_MARKETING_TERMS = (
    "reach",
    "engagement",
    "content strategy",
    "РєРѕРЅС‚РµРЅС‚-СЃС‚СЂР°С‚РµРі",
    "РѕС…РІР°С‚",
    "РІРѕРІР»РµС‡РµРЅРёРµ",
)

HARD_SELL_CTA_TERMS = (
    "приходите",
    "приходите к нам",
    "приходи",
    "запишитесь",
    "записывайтесь",
    "запишитесь на",
    "пробное занятие",
    "напишите в сообщения",
    "напишите в директ",
    "напишите нам",
    "оставьте заявку",
    "мы подскажем",
    "подскажем лучший вариант",
    "узнайте больше",
    "присоединяйтесь к нам",
    "консультац",
    "бесплатное пробное занятие",
    "забронируйте",
    "book now",
    "dm us",
    "send a dm",
    "book a call",
    "nachricht",
    "termin buchen",
)


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
        "hashtags",
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
        lambda i: f"Р С™Р В»РЎР‹РЎвЂЎР ВµР Р†Р С•Р в„– РЎвЂљР ВµР В·Р С‘РЎРѓ {i + 1}",
    )
    payload["hook_ideas"] = _pad_list(
        [str(x).strip() for x in (payload.get("hook_ideas") or []) if str(x).strip()],
        5,
        lambda i: f"Р ТђРЎС“Р С” {i + 1}: Р С—РЎР‚Р В°Р С”РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С‘Р в„– Р С‘Р Р…РЎРѓР В°Р в„–РЎвЂљ Р С—Р С• РЎвЂљР ВµР СР Вµ",
    )
    payload["cta_variants"] = _pad_list(
        [str(x).strip() for x in (payload.get("cta_variants") or []) if str(x).strip()],
        3,
        lambda i: f"CTA {i + 1}: Р СњР В°Р С—Р С‘РЎв‚¬Р С‘РЎвЂљР Вµ Р Р† Р Т‘Р С‘РЎР‚Р ВµР С”РЎвЂљ, Р С—Р С•Р Т‘Р В±Р ВµРЎР‚Р ВµР С РЎР‚Р ВµРЎв‚¬Р ВµР Р…Р С‘Р Вµ Р С—Р С•Р Т‘ Р Р†Р В°РЎв‚¬РЎС“ Р В·Р В°Р Т‘Р В°РЎвЂЎРЎС“.",
    )
    payload["visual_ideas"] = _pad_list(
        [str(x).strip() for x in (payload.get("visual_ideas") or []) if str(x).strip()],
        5,
        lambda i: f"Р вЂ™Р С‘Р В·РЎС“Р В°Р В» {i + 1}: РЎР‚Р ВµР В°Р В»Р С‘РЎРѓРЎвЂљР С‘РЎвЂЎР Р…РЎвЂ№Р в„– Р В±Р С‘Р В·Р Р…Р ВµРЎРѓ-РЎРѓРЎР‹Р В¶Р ВµРЎвЂљ Р В±Р ВµР В· РЎвЂљР ВµР С”РЎРѓРЎвЂљР В° Р Р…Р В° Р С‘Р В·Р С•Р В±РЎР‚Р В°Р В¶Р ВµР Р…Р С‘Р С‘.",
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
            "objection": f"Р вЂ™Р С•Р В·РЎР‚Р В°Р В¶Р ВµР Р…Р С‘Р Вµ {i + 1}: РЎРЊРЎвЂљР С• РЎРѓР В»Р С•Р В¶Р Р…Р С• Р Р†Р Р…Р ВµР Т‘РЎР‚Р С‘РЎвЂљРЎРЉ",
            "answer": "Р В Р В°Р В·Р В±Р С‘Р Р†Р В°Р ВµР С Р Р†Р Р…Р ВµР Т‘РЎР‚Р ВµР Р…Р С‘Р Вµ Р Р…Р В° 2-3 Р С”Р С•РЎР‚Р С•РЎвЂљР С”Р С‘РЎвЂ¦ РЎв‚¬Р В°Р С–Р В° Р С‘ Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°Р ВµР С Р В±Р ВµР В· Р С—Р ВµРЎР‚Р ВµР С–РЎР‚РЎС“Р В·Р В° Р С”Р С•Р СР В°Р Р…Р Т‘РЎвЂ№.",
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
        lambda _: ["#Р С”Р С•Р Р…РЎвЂљР ВµР Р…РЎвЂљ", "#Р СР В°РЎР‚Р С”Р ВµРЎвЂљР С‘Р Р…Р С–", "#Р В±Р С‘Р В·Р Р…Р ВµРЎРѓ"],
    )
    payload["hashtag_sets"] = [s if len(s) >= 3 else _pad_list(s, 3, lambda __: "#Р С”Р С•Р Р…РЎвЂљР ВµР Р…РЎвЂљ") for s in hashtag_sets_norm]


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
    if not isinstance(objections, list):
        raise ValueError("objections_answers must be a list")
    for row in objections:
        if not isinstance(row, dict):
            raise ValueError("objections_answers item must be object")
        if not str(row.get("objection") or "").strip():
            raise ValueError("objection is empty")
        if not str(row.get("answer") or "").strip():
            raise ValueError("answer is empty")

    hashtag_sets = payload.get("hashtag_sets")
    if not isinstance(hashtag_sets, list):
        raise ValueError("hashtag_sets must be a list")
    for tag_set in hashtag_sets:
        _ensure_list_of_strings(tag_set, "hashtag_set", min_len=1)

    _ensure_list_of_strings(payload.get("visual_ideas"), "visual_ideas", min_len=5)


def validate_draft_payload(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("draft payload must be object")
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
    asset_ideas = payload.get("asset_ideas") or []
    if asset_ideas and not isinstance(asset_ideas, list):
        raise ValueError("asset_ideas must be a list")
    if platform == "youtube":
        if not str(payload.get("title") or "").strip():
            raise ValueError("youtube title is required")
        if not str(payload.get("description") or "").strip():
            raise ValueError("youtube description is required")
        if not str(payload.get("pinned_comment_text") or "").strip():
            raise ValueError("youtube pinned_comment_text is required")


def _strategy_system_prompt() -> str:
    return (
        "You are a niche-aware social content strategist. "
        "Always write value-first content for real people and keep the meaning useful, clear and credible. "
        "Never output marketing-advice language for marketers. "
        "Never mention: reach, engagement, content strategy, РѕС…РІР°С‚, РІРѕРІР»РµС‡РµРЅРёРµ, РєРѕРЅС‚РµРЅС‚-СЃС‚СЂР°С‚РµРіРёСЏ. "
        "Never invent specific product facts if offer is empty. When offer is empty, do not force sales CTA. "
        "Generate clean, realistic social media hashtags. Do not use random characters. "
        "Do not transliterate incorrectly. No punctuation. "
        "Visual ideas must be image concepts without text on image. "
        "Return JSON only."
    )


def _strategy_user_prompt(*, topic: str, offer: str | None, language: str, tone: str, goal: str, platforms: list[str]) -> str:
    playbook = _goal_playbook(goal)
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
        f"- goal playbook: {', '.join(playbook['content_types'])}\n"
        "- transform topic into customer-facing hooks; do not copy topic verbatim as headline.\n"
        "- Expand topic with context, angle and structure.\n"
        "- Return strict JSON with this schema:\n"
        f"{json.dumps(schema_hint, ensure_ascii=False)}"
    )


def _draft_system_prompt() -> str:
    return (
        "You are a senior niche-aware social copywriter. "
        "Write useful, credible social content for real people, not marketers. "
        "Start with one useful idea, one practical point or one meaningful observation. "
        "Do not default to local-service sales language unless the offer is explicit. "
        "When offer is empty, keep CTA soft, reflective or optional. "
        "Never mention: reach, engagement, content strategy, РѕС…РІР°С‚, РІРѕРІР»РµС‡РµРЅРёРµ, РєРѕРЅС‚РµРЅС‚-СЃС‚СЂР°С‚РµРіРёСЏ. "
        "Never write marketing advice about algorithms or content systems. "
        "Transform theme into a human hook; never reuse the theme verbatim as headline. "
        "Generate clean, realistic social media hashtags. Do not use random characters. "
        "Do not transliterate incorrectly. No punctuation. "
        "Write practical, readable social content. "
        "No fake product facts. If offer is empty keep messaging universal and non-promotional. "
        "Return JSON only."
    )


def _has_explicit_offer(offer: str | None) -> bool:
    return bool(str(offer or "").strip())


def _cta_mode(goal: str, offer: str | None) -> str:
    goal_mode = _normalize_goal_for_business(goal)
    if goal_mode == "lead" and _has_explicit_offer(offer):
        return "service"
    if goal_mode == "trust":
        return "discussion"
    return "soft"


def _cta_defaults(language: str, mode: str) -> list[str]:
    lang = str(language or "ru").strip().lower()
    if lang == "de":
        soft = [
            "Speichern Sie den Beitrag, wenn Sie den Gedanken spaeter noch einmal brauchen.",
            "Worauf achten Sie in so einer Situation zuerst?",
            "Welche dieser Fehler sehen Sie am haeufigsten?",
        ]
        discussion = [
            "Haben Sie so etwas schon einmal bemerkt?",
            "Welche Variante wirkt fuer Sie realistischer?",
            "Woran wuerde man das bei Ihnen zuerst erkennen?",
        ]
        service = [
            "Wenn Sie dazu ein konkretes Angebot wollen, schreiben Sie uns kurz.",
            "Wenn Sie genau fuer Ihre Situation eine Empfehlung brauchen, schicken Sie uns eine Nachricht.",
            "Wenn Sie das Thema mit einem klaren naechsten Schritt loesen wollen, schreiben Sie uns.",
        ]
    elif lang == "en":
        soft = [
            "Save this post if you want to come back to the idea later.",
            "What do you usually notice first in a situation like this?",
            "Which of these mistakes feels the most common to you?",
        ]
        discussion = [
            "Have you noticed something similar before?",
            "Which option feels more realistic to you?",
            "What would you check first in this situation?",
        ]
        service = [
            "If you want a tailored option for your situation, send us a message.",
            "If you need a concrete recommendation based on your case, message us.",
            "If you want help turning this into a clear next step, write to us.",
        ]
    else:
        soft = [
            "Сохраните пост, если хотите вернуться к этой мысли позже.",
            "А вы замечали что-то похожее?",
            "Какая из этих ошибок кажется самой частой?",
        ]
        discussion = [
            "Было ли у вас что-то похожее?",
            "Какой вариант вам ближе?",
            "На что вы обычно обращаете внимание в такой ситуации?",
        ]
        service = [
            "Если вам нужно подобрать вариант под свою ситуацию, напишите нам.",
            "Если хотите понятную рекомендацию под ваш запрос, напишите в сообщения.",
            "Если нужен следующий шаг именно для вашей ситуации, напишите нам.",
        ]
    if mode == "service":
        return service
    if mode == "discussion":
        return discussion
    return soft


def _looks_hard_sell_cta(text: str) -> bool:
    low = str(text or "").strip().lower()
    return any(term in low for term in HARD_SELL_CTA_TERMS)


NO_OFFER_SERVICE_FRAMING_TERMS = (
    "перед визит",
    "первым визит",
    "визитом в",
    "визитом к",
    "посетить наш центр",
    "наш центр",
    "нашего центра",
    "к нам",
    "к психологу",
    "в фитнес-клуб",
    "в фитнес-зал",
    "на консультац",
    "консультац",
    "обратиться к нам",
    "присоединяйтесь к нам",
    "запишитесь",
    "подрядчику",
    "подскажем лучший вариант",
    "напишите в сообщения",
    "напишите в директ",
)


NO_OFFER_SERVICE_TAGS = {
    "#услуги",
    "#запись",
    "#акция",
    "#рекомендуем",
    "#recommended",
    "#local",
    "#localbusiness",
    "#service",
    "#angebot",
    "#booknow",
}


def _looks_service_framed_no_offer(text: str) -> bool:
    low = str(text or "").strip().lower()
    if not low:
        return False
    return any(term in low for term in NO_OFFER_SERVICE_FRAMING_TERMS)


def _looks_service_framed_topic_no_offer(text: str) -> bool:
    low = str(text or "").strip().lower()
    if not low:
        return False
    topic_terms = (
        "клиента перед услугой",
        "перед услугой",
        "услугой",
        "перед выбором решения",
        "свободные окна",
        "визитом",
        "консультац",
    )
    return any(term in low for term in topic_terms)


def _pick_default_cta(goal: str, offer: str | None, language: str, *, preferred: str | None = None) -> str:
    preferred_text = str(preferred or "").strip()
    mode = _cta_mode(goal, offer)
    if preferred_text:
        if mode != "service" and _looks_hard_sell_cta(preferred_text):
            preferred_text = ""
        elif not _contains_meta_marketing_advice(preferred_text):
            return preferred_text
    return _cta_defaults(language, mode)[0]


def _default_cta_options(goal: str, offer: str | None, language: str, niche_cta_templates: list[str] | None = None) -> list[str]:
    mode = _cta_mode(goal, offer)
    templates = [str(x).strip() for x in (niche_cta_templates or []) if str(x).strip()]
    if mode != "service":
        templates = [x for x in templates if not _looks_hard_sell_cta(x)]
    pool = templates + _cta_defaults(language, mode)
    out: list[str] = []
    seen: set[str] = set()
    for item in pool:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= 3:
            break
    defaults = _cta_defaults(language, mode)
    while len(out) < 3:
        out.append(defaults[len(out) % len(defaults)])
    return out[:3]


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    return [str(x).strip() for x in parts if str(x).strip()]


def _format_core_for_platform(core_text: str, platform: str) -> str:
    text = str(core_text or "").strip()
    if not text:
        return ""
    lines = [str(x).strip() for x in text.splitlines() if str(x).strip()]
    bullet_like = [line for line in lines if re.match(r"^(\d+[).:-]|[-*•])\s*", line)]
    if bullet_like:
        intro = [line for line in lines if line not in bullet_like]
        intro_text = "\n\n".join(intro[:2]).strip()
        bullets = bullet_like[:4 if platform == "instagram" else 5]
        return "\n\n".join(([intro_text] if intro_text else []) + bullets).strip()
    sentences = _split_sentences(text)
    if not sentences:
        return text
    if platform == "instagram":
        return "\n\n".join(sentences[: min(len(sentences), 5)]).strip()
    if platform == "facebook":
        chunks = []
        current = []
        for sentence in sentences[: min(len(sentences), 6)]:
            current.append(sentence)
            if len(current) >= 2:
                chunks.append(" ".join(current).strip())
                current = []
        if current:
            chunks.append(" ".join(current).strip())
        return "\n\n".join(chunks).strip()
    return text


def _shared_core_fallback_text(topic: str, angle: str, goal: str, offer: str | None, language: str) -> str:
    lang = str(language or "ru").strip().lower()
    angle_text = _repair_mojibake_text(str(angle or "").strip())
    topic_text = _repair_mojibake_text(str(topic or "").strip())
    if lang == "de":
        intro = f"{topic_text}. {angle_text}".strip(". ")
        close = "Wenn es dazu ein klares Angebot gibt, kann daraus ein naechster Schritt werden." if _has_explicit_offer(offer) else "Der naechste Schritt darf ruhig klein und realistisch sein."
        return (
            f"{intro}.\n\n"
            "Nennen Sie zuerst ein konkretes Muster oder einen typischen Fehler, den man wirklich wiedererkennt.\n\n"
            "Geben Sie danach einen einfachen, brauchbaren Hinweis, den man sofort fuer die eigene Situation pruefen kann.\n\n"
            f"{close}"
        ).strip()
    if lang == "en":
        intro = f"{topic_text}. {angle_text}".strip(". ")
        close = "If there is a real offer behind it, the next step can be explicit." if _has_explicit_offer(offer) else "The next step should stay light and useful, not pushy."
        return (
            f"{intro}.\n\n"
            "Start with one recognizable mistake, signal or situation the audience will instantly understand.\n\n"
            "Then add one practical takeaway they can use right away in real life.\n\n"
            f"{close}"
        ).strip()
    intro = f"{topic_text}. {angle_text}".strip(". ")
    close = "Если за темой стоит конкретное предложение, его можно упомянуть мягко и по делу." if _has_explicit_offer(offer) else "Следующий шаг здесь должен оставаться мягким и полезным, а не давящим."
    return (
        f"{intro}.\n\n"
        "Сначала покажите один узнаваемый сигнал, ошибку или ситуацию, с которой человек действительно сталкивается.\n\n"
        "Затем дайте одну практическую мысль или шаг, который можно применить без лишней теории.\n\n"
        f"{close}"
    ).strip()

def _adapt_core_row_for_platform(source_row: dict, *, platform: str, variant_index: int, topic: str, niche_label: str | None, language: str, goal: str, offer: str | None) -> dict:
    no_offer = not _has_explicit_offer(offer)
    safe_core_text = _shared_core_fallback_text(topic, "", goal, offer, language)
    body_text = _format_core_for_platform(str(source_row.get("post_text") or "").strip(), platform)
    if not body_text or _contains_meta_marketing_advice(body_text):
        body_text = _format_core_for_platform(safe_core_text, platform)
    elif no_offer:
        body_text = _format_core_for_platform(safe_core_text, platform)
    cta_text = _pick_default_cta(goal, offer, language, preferred=str(source_row.get("cta") or "").strip())
    hashtags = [str(x).strip() for x in (source_row.get("hashtags") or []) if str(x).strip()]
    generated_tags = generateHashtags(niche=niche_label or topic, city=None, language=language, goal=goal)
    if hashtags:
        hashtags = _sanitize_hashtag_list(hashtags + generated_tags, min_count=5, max_count=12)
    else:
        hashtags = generated_tags
    if no_offer:
        cta_text = _cta_defaults(language, "soft")[0]
        hashtags = [tag for tag in generated_tags if str(tag).strip().lower() not in NO_OFFER_SERVICE_TAGS]
        hashtags = _sanitize_hashtag_list(hashtags, min_count=5, max_count=12 if platform != "instagram" else 15)
    if platform == "instagram":
        hashtags = hashtags[:15]
        prev_len = -1
        while len(hashtags) < 8 and len(hashtags) != prev_len:
            prev_len = len(hashtags)
            hashtags = _sanitize_hashtag_list(hashtags + generated_tags, min_count=8, max_count=15)
    elif platform == "facebook":
        hashtags = hashtags[:8] or generated_tags[:8]
    elif platform == "youtube":
        hashtags = _sanitize_hashtag_list(hashtags + generated_tags, min_count=3, max_count=10)[:3]
    row = {
        "platform": platform,
        "variant_index": variant_index,
        "post_text": body_text,
        "title": source_row.get("title"),
        "description": source_row.get("description"),
        "hashtags": hashtags,
        "cta": cta_text,
        "asset_ideas": source_row.get("asset_ideas") or [],
        "pinned_comment_text": source_row.get("pinned_comment_text"),
    }
    return _ensure_platform_draft_shape(row, platform=platform, variant_index=variant_index)


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
    playbook = _goal_playbook(goal)
    hook_hint = _topic_to_client_hook(topic, goal)
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
        f"- goal playbook: {', '.join(playbook['content_types'])}\n"
        f"- hook example (not verbatim topic): {hook_hint}\n"
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
        "lead": "лиды",
        "engagement": "вовлечение",
        "awareness": "охват",
        "trust": "РґРѕРІРµСЂРёРµ",
    }
    return mapping.get(str(goal or "").strip().lower(), "вовлечение")


def _fallback_strategy(topic: str, offer: str | None, goal: str) -> dict:
    strategy = _mock_strategy(topic=topic, offer=offer, goal=goal)
    strategy["angle"] = f"Р СџРЎР‚Р В°Р С”РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С‘Р в„– РЎР‚Р В°Р В·Р В±Р С•РЎР‚ РЎвЂљР ВµР СРЎвЂ№ Р’В«{topic}Р’В» Р С—Р С•Р Т‘ РЎвЂ Р ВµР В»РЎРЉ: {_goal_label(goal)}"
    strategy["context"] = (
        f"Р С’РЎС“Р Т‘Р С‘РЎвЂљР С•РЎР‚Р С‘Р С‘ Р Р…РЎС“Р В¶Р ВµР Р… Р С—Р С•Р Р…РЎРЏРЎвЂљР Р…РЎвЂ№Р в„– РЎРѓРЎвЂ Р ВµР Р…Р В°РЎР‚Р С‘Р в„– Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р в„– Р С—Р С• РЎвЂљР ВµР СР Вµ Р’В«{topic}Р’В»."
        + (f" Р С›РЎвЂћРЎвЂћР ВµРЎР‚: {offer}." if offer else "")
    )
    _normalize_strategy_payload(strategy)
    return strategy


def _extract_hashtags_from_text(text: str, *, limit: int = 12) -> list[str]:
    found = re.findall(r"#([\w_]+)", text or "", flags=re.U)
    tags: list[str] = []
    for token in found:
        val = f"#{str(token).lower()}"
        if val not in tags:
            tags.append(val)
        if len(tags) >= limit:
            break
    if not tags:
        tags = ["#полезно", "#совет", "#практика", "#разбор", "#соцсети"]
    return _sanitize_hashtag_list(tags, min_count=min(5, limit), max_count=min(12, limit))


def _normalize_hashtag_language(language: str) -> str:
    key = str(language or "").strip().lower()
    if key in {"русский", "ru", "russian"}:
        return "ru"
    if key in {"deutsch", "de", "german"}:
        return "de"
    return "en"


def _sanitize_hashtag_token(token: str, *, max_len: int = 29) -> str:
    raw = _repair_mojibake_text(str(token or "")).strip().lower()
    if raw.startswith("#"):
        raw = raw[1:]
    cleaned_chars = []
    for ch in raw:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9") or ("\u0430" <= ch <= "\u044f") or ch in {"ё"}:
            cleaned_chars.append(ch)
    cleaned = "".join(cleaned_chars)
    cleaned = cleaned[:max_len].strip()
    return f"#{cleaned}" if cleaned else ""


def _sanitize_hashtag_list(tags: list[str], *, min_count: int = 5, max_count: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        safe = _sanitize_hashtag_token(tag)
        if not safe:
            continue
        if "," in safe or "'" in safe or "вЂ™" in safe:
            continue
        if len(safe) >= 30:
            safe = safe[:29]
            safe = _sanitize_hashtag_token(safe)
        if not safe or safe in seen:
            continue
        seen.add(safe)
        out.append(safe)
        if len(out) >= max_count:
            break
    if len(out) < min_count:
        filler = ["#полезно", "#совет", "#разбор", "#практика", "#соцсети"]
        for tag in filler:
            safe = _sanitize_hashtag_token(tag)
            if safe and safe not in seen:
                seen.add(safe)
                out.append(safe)
            if len(out) >= min_count:
                break
    return out[:max_count]


def generateHashtags(niche: str, city: str | None, language: str, goal: str) -> list[str]:
    lang = _normalize_hashtag_language(language)
    goal_mode = _normalize_goal_for_business(goal)
    niche_raw = str(niche or "").strip().lower()
    city_raw = str(city or "").strip()

    niche_templates = {
        "ru": {
            "barbershop": {
                "niche": ["#барбершоп", "#барбер"],
                "service": ["#мужскаястрижка", "#борода"],
                "engagement": ["#мужскойстиль", "#уход"],
            }
        },
        "de": {
            "barbershop": {
                "niche": ["#barbershop", "#barber"],
                "service": ["#herrenhaarschnitt", "#bartpflege"],
                "engagement": ["#herrenstyle", "#lokalempfohlen"],
            }
        },
        "en": {
            "barbershop": {
                "niche": ["#barbershop", "#barber"],
                "service": ["#menshaircut", "#beardtrim"],
                "engagement": ["#mensstyle", "#localbusiness"],
            }
        },
    }

    def _detect_niche_key() -> str:
        checks = (
            ("barbershop", ["barber", "barbershop", "Р±Р°СЂР±РµСЂ", "Р±Р°СЂР±РµСЂС€РѕРї"]),
            ("beauty", ["beauty", "СЃР°Р»РѕРЅ", "РєСЂР°СЃРѕС‚"]),
            ("auto", ["auto", "Р°РІС‚Рѕ", "service", "СЃРµСЂРІРёСЃ"]),
            ("restaurant", ["restaurant", "СЂРµСЃС‚РѕСЂР°РЅ"]),
            ("cafe", ["cafe", "РєР°С„Рµ", "coffee"]),
        )
        for key, needles in checks:
            if any(n in niche_raw for n in needles):
                return key
        return "generic"

    niche_key = _detect_niche_key()
    spec = niche_templates.get(lang, {}).get("barbershop" if niche_key == "barbershop" else "")
    if spec:
        niche_tags = spec["niche"][:2]
        service_tags = spec["service"][:2]
        engagement_tags = spec["engagement"][:2]
    else:
        if lang == "ru":
            niche_tags = [f"#{re.sub(r'[^0-9a-zа-я]+', '', niche_raw, flags=re.I) or 'ниша'}", "#практика"]
            service_tags = ["#разбор", "#польза"]
            engagement_tags = ["#совет", "#полезно"]
        elif lang == "de":
            niche_tags = [f"#{re.sub(r'[^0-9a-zГ¤Г¶ГјГџ]+', '', niche_raw, flags=re.I) or 'lokal'}", "#dienstleistung"]
            service_tags = ["#qualitГ¤t", "#service"]
            engagement_tags = ["#empfehlung", "#regional"]
        else:
            niche_tags = [f"#{re.sub(r'[^0-9a-z]+', '', niche_raw, flags=re.I) or 'localbusiness'}", "#service"]
            service_tags = ["#quality", "#trusted"]
            engagement_tags = ["#recommended", "#local"]

    goal_service_overrides = {
        "lead": {"ru": ["#решение", "#помощь"], "de": ["#termin", "#angebot"], "en": ["#booknow", "#offer"]},
        "trust": {"ru": ["#опыт", "#результат"], "de": ["#kundenstimmen", "#ergebnis"], "en": ["#testimonial", "#results"]},
        "awareness": {"ru": ["#совет", "#полезно"], "de": ["#tipp", "#wissen"], "en": ["#tips", "#insight"]},
    }
    if (not spec) and goal_mode in goal_service_overrides:
        service_tags = goal_service_overrides[goal_mode].get(lang, service_tags)

    geo_tags: list[str] = []
    if city_raw:
        geo_tags.append(f"#{city_raw}")
        if lang == "de":
            geo_tags.append(f"#{city_raw}stadt")
        elif lang == "en":
            geo_tags.append(f"#{city_raw}local")

    ordered = niche_tags[:2] + service_tags[:2] + geo_tags[:3] + engagement_tags[:2]
    return _sanitize_hashtag_list(ordered, min_count=5, max_count=12)


def generate_hashtags(niche: str, city: str | None, language: str, goal: str) -> list[str]:
    return generateHashtags(niche=niche, city=city, language=language, goal=goal)


def _extract_cta_from_text(text: str) -> str:
    lines = [str(x).strip() for x in str(text or "").splitlines() if str(x).strip()]
    for line in reversed(lines):
        low = line.lower()
        if any(k in low for k in ["напишите", "оставьте", "перейдите", "запишитесь", "купите", "подпишитесь"]):
            return line
    return "Сохраните пост, если хотите вернуться к этой мысли позже."


def _ensure_platform_draft_shape(draft: dict, *, platform: str, variant_index: int) -> dict:
    out = dict(draft or {})
    out["platform"] = platform
    out["variant_index"] = int(variant_index or 1)
    out["post_text"] = _repair_mojibake_text(str(out.get("post_text") or "").strip())
    out["cta"] = _repair_mojibake_text(str(out.get("cta") or "").strip())
    out["hashtags"] = _repair_mojibake_list([str(x).strip() for x in (out.get("hashtags") or []) if str(x).strip()])
    out["asset_ideas"] = _repair_mojibake_list([str(x).strip() for x in (out.get("asset_ideas") or []) if str(x).strip()])
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
        out["title"] = _repair_mojibake_text(str(out.get("title") or "").strip()) or "Практический разбор темы"
        out["description"] = _repair_mojibake_text(str(out.get("description") or "").strip()) or out["post_text"]
        out["pinned_comment_text"] = _repair_mojibake_text(str(out.get("pinned_comment_text") or "").strip()) or "Какая мысль здесь откликается сильнее всего?"
        out["hashtags"] = out["hashtags"][:3]
    else:
        out["title"] = _repair_mojibake_text(str(out.get("title") or "").strip()) or None
        out["description"] = _repair_mojibake_text(str(out.get("description") or "").strip()) or None
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
    angle: str | None = None,
) -> tuple[dict, int, int]:
    goal_mode = _normalize_goal_for_business(goal)
    playbook = _goal_playbook(goal_mode)
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
        "You create one shared semantic core for a social post. Return compact JSON only. "
        "Write useful niche-aware content for real people. "
        "The post must contain one clear idea, one useful point and one believable takeaway. "
        "Do not default to local-service sales language unless the offer is explicit. "
        "When offer is empty, keep CTA soft, reflective or optional. "
        "Never write marketing advice for marketers. "
        "Never mention: reach, engagement, content strategy, content marketing metrics or creator strategy language. "
        "No extra keys."
    )
    user = (
        f"topic: {topic}\n"
        f"offer: {offer or ''}\n"
        f"language: {language}\n"
        f"tone: {tone}\n"
        f"goal: {goal}\n"
        f"goal_playbook: {', '.join(playbook['content_types'])}\n"
        f"variant: {variant_index}\n"
        "Create a platform-neutral core first. Facebook and Instagram will be adapted later from the same meaning.\n"
        "Theme must be transformed into a human hook, not copied verbatim as headline.\n"
        "Content must feel useful, calm, category-native and not falsely promotional by default.\n"
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
            "cta": _pick_default_cta(goal, offer, language, preferred=payload_get(res.payload, "cta")),
            "asset_ideas": [
                "Крупный план детали или процесса без текста на кадре",
                "Обычная рабочая ситуация или деталь из реальной среды",
                "Наглядное сравнение, понятный визуальный акцент или процесс по шагам",
            ],
            "pinned_comment_text": "Какая мысль здесь откликается сильнее всего?",
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
    angle: str | None = None,
) -> dict:
    goal_mode = _normalize_goal_for_business(goal)
    hook = _topic_to_client_hook(topic, goal_mode)
    body = _shared_core_fallback_text(topic, str(angle or hook).strip(), goal, offer, "ru")
    return _ensure_platform_draft_shape(
        {
            "platform": platform,
            "variant_index": variant_index,
            "post_text": _format_core_for_platform(body, platform),
            "title": f"{hook}: практический разбор" if platform == "youtube" else None,
            "description": body if platform == "youtube" else None,
            "hashtags": _extract_hashtags_from_text(body),
            "cta": _pick_default_cta(goal, offer, "ru"),
            "asset_ideas": [
                "Реалистичный кадр по теме без текста на изображении",
                "Процесс, деталь или рабочая ситуация из реальной среды",
                "До/после, сравнение или понятный визуальный акцент по теме",
            ],
            "pinned_comment_text": "Какой вариант вам ближе?" if platform == "youtube" else None,
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
            "hook": f"{base}: РЎвЂЎРЎвЂљР С• Р Р†Р В°Р В¶Р Р…Р С• Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С‘РЎвЂљРЎРЉ Р Т‘Р С• РЎРѓРЎвЂљР В°РЎР‚РЎвЂљР В°?",
            "angles": [
                f"3 РЎвЂЎР В°РЎРѓРЎвЂљРЎвЂ№Р Вµ Р С•РЎв‚¬Р С‘Р В±Р С”Р С‘ Р Р† РЎвЂљР ВµР СР Вµ Р’В«{base}Р’В»",
                f"Р В§Р ВµР С”-Р В»Р С‘РЎРѓРЎвЂљ Р Р†Р Р…Р ВµР Т‘РЎР‚Р ВµР Р…Р С‘РЎРЏ Р’В«{base}Р’В» Р В·Р В° 1 Р Т‘Р ВµР Р…РЎРЉ",
                f"Р С™Р ВµР в„–РЎРѓ: Р С”Р В°Р С” Р С—РЎР‚Р С‘Р СР ВµР Р…Р С‘Р В»Р С‘ Р’В«{base}Р’В» Р С‘ Р С—Р С•Р В»РЎС“РЎвЂЎР С‘Р В»Р С‘ РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ",
            ],
            "cta_variants": [
                "Р СњР В°Р С—Р С‘РЎв‚¬Р С‘РЎвЂљР Вµ Р Р† Р Т‘Р С‘РЎР‚Р ВµР С”РЎвЂљ РІР‚вЂќ Р С•РЎвЂљР С—РЎР‚Р В°Р Р†Р С‘Р С РЎвЂЎР ВµР С”-Р В»Р С‘РЎРѓРЎвЂљ.",
                "Р С›РЎРѓРЎвЂљР В°Р Р†РЎРЉРЎвЂљР Вµ Р’В«Р СџР вЂєР С’Р СњР’В» Р Р† Р С”Р С•Р СР СР ВµР Р…РЎвЂљР В°РЎР‚Р С‘РЎРЏРЎвЂ¦ РІР‚вЂќ Р С—РЎР‚Р С‘РЎв‚¬Р В»РЎвЂР С РЎв‚¬Р В°Р С–Р С‘.",
                "Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…Р С‘РЎвЂљР Вµ Р С—Р С•РЎРѓРЎвЂљ Р С‘ Р Р†Р Р…Р ВµР Т‘РЎР‚Р С‘РЎвЂљР Вµ Р С—Р ВµРЎР‚Р Р†РЎвЂ№Р в„– РЎв‚¬Р В°Р С– РЎРѓР ВµР С–Р С•Р Т‘Р Р…РЎРЏ.",
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
            "hook": f"{topic}: РЎвЂЎРЎвЂљР С• Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С‘РЎвЂљРЎРЉ Р С—Р ВµРЎР‚Р ВµР Т‘ Р В·Р В°Р С—РЎС“РЎРѓР С”Р С•Р С?",
            "angles": [
                f"Р СџР С•РЎв‚¬Р В°Р С–Р С•Р Р†РЎвЂ№Р в„– РЎР‚Р В°Р В·Р В±Р С•РЎР‚ Р’В«{topic}Р’В»",
                f"Р СћР С‘Р С—Р С‘РЎвЂЎР Р…РЎвЂ№Р Вµ Р С•РЎв‚¬Р С‘Р В±Р С”Р С‘ Р Р† Р’В«{topic}Р’В»",
                f"Р СџРЎР‚Р В°Р С”РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С‘Р в„– Р С”Р ВµР в„–РЎРѓ Р С—Р С• Р’В«{topic}Р’В»",
            ],
            "cta_variants": [
                "Р СњР В°Р С—Р С‘РЎв‚¬Р С‘РЎвЂљР Вµ Р Р† Р Т‘Р С‘РЎР‚Р ВµР С”РЎвЂљ, Р С—Р С•Р Т‘Р В±Р ВµРЎР‚Р ВµР С РЎР‚Р ВµРЎв‚¬Р ВµР Р…Р С‘Р Вµ Р С—Р С•Р Т‘ Р В·Р В°Р Т‘Р В°РЎвЂЎРЎС“.",
                "Р С›РЎРѓРЎвЂљР В°Р Р†РЎРЉРЎвЂљР Вµ Р С”Р С•Р СР СР ВµР Р…РЎвЂљР В°РЎР‚Р С‘Р в„– Р С‘ Р С—Р С•Р В»РЎС“РЎвЂЎР С‘РЎвЂљР Вµ РЎв‚¬Р В°Р В±Р В»Р С•Р Р….",
                "Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…Р С‘РЎвЂљР Вµ Р С—Р С•РЎРѓРЎвЂљ Р С‘ Р Р†Р Р…Р ВµР Т‘РЎР‚Р С‘РЎвЂљР Вµ Р С—Р ВµРЎР‚Р Р†РЎвЂ№Р в„– РЎв‚¬Р В°Р С– РЎРѓР ВµР С–Р С•Р Т‘Р Р…РЎРЏ.",
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
    if key in {"Р С”Р С•РЎР‚Р С•РЎвЂЎР Вµ", "shorter"}:
        sentences = re.split(r"(?<=[.!?])\s+", value)
        return " ".join(sentences[: max(1, min(3, len(sentences)))])
    if key in {"Р Т‘Р В»Р С‘Р Р…Р Р…Р ВµР Вµ", "longer"}:
        return f"{value}\n\nР вЂќР С•Р В±Р В°Р Р†РЎРЉРЎвЂљР Вµ Р С”Р С•Р Р…Р С”РЎР‚Р ВµРЎвЂљР Р…РЎвЂ№Р в„– Р С—РЎР‚Р С‘Р СР ВµРЎР‚ Р Р†Р Р…Р ВµР Т‘РЎР‚Р ВµР Р…Р С‘РЎРЏ Р С‘ Р С•Р В¶Р С‘Р Т‘Р В°Р ВµР СРЎвЂ№Р в„– РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ Р Р† РЎвЂ Р С‘РЎвЂћРЎР‚Р В°РЎвЂ¦."
    if "Р С—РЎР‚Р С•Р Т‘Р В°" in key:
        return f"{value}\n\nР вЂўРЎРѓР В»Р С‘ РЎвЂ¦Р С•РЎвЂљР С‘РЎвЂљР Вµ РЎвЂљР В°Р С”Р С•Р в„– Р В¶Р Вµ РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ, Р Р…Р В°Р С—Р С‘РЎв‚¬Р С‘РЎвЂљР Вµ Р Р† Р Т‘Р С‘РЎР‚Р ВµР С”РЎвЂљ РІР‚вЂќ Р С—Р С•Р Т‘Р В±Р ВµРЎР‚Р ВµР С РЎР‚Р ВµРЎв‚¬Р ВµР Р…Р С‘Р Вµ Р С—Р С•Р Т‘ Р Р†Р В°РЎв‚¬РЎС“ Р В·Р В°Р Т‘Р В°РЎвЂЎРЎС“."
    if "РЎРЊР С”РЎРѓР С—Р ВµРЎР‚РЎвЂљ" in key:
        return f"{value}\n\nР СџРЎР‚Р В°Р С”РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С‘Р в„– РЎРѓР С•Р Р†Р ВµРЎвЂљ: Р Р…Р В°РЎвЂЎР Р…Р С‘РЎвЂљР Вµ РЎРѓ Р СР С‘Р Р…Р С‘Р СР В°Р В»РЎРЉР Р…Р С•Р С–Р С• РЎвЂљР ВµРЎРѓРЎвЂљР В° Р С‘ Р С‘Р В·Р СР ВµРЎР‚РЎРЉРЎвЂљР Вµ РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ РЎвЂЎР ВµРЎР‚Р ВµР В· 7 Р Т‘Р Р…Р ВµР в„–."
    if "РЎРЊР СР С•РЎвЂ " in key:
        return f"{value}\n\nР В­РЎвЂљР С• Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘РЎвЂљР ВµР В»РЎРЉР Р…Р С• Р СР С•Р В¶Р ВµРЎвЂљ РЎРѓР Р…РЎРЏРЎвЂљРЎРЉ РЎвЂ¦Р В°Р С•РЎРѓ Р Р† Р С”Р С•Р Р…РЎвЂљР ВµР Р…РЎвЂљР Вµ Р С‘ Р Р†Р ВµРЎР‚Р Р…РЎС“РЎвЂљРЎРЉ РЎС“Р Р†Р ВµРЎР‚Р ВµР Р…Р Р…Р С•РЎРѓРЎвЂљРЎРЉ Р Р† РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљР Вµ."
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
        warnings.append("Р РЋРЎвЂљРЎР‚Р В°РЎвЂљР ВµР С–Р С‘РЎРЏ РЎвЂЎР В°РЎРѓРЎвЂљР С‘РЎвЂЎР Р…Р С• Р Р†Р С•РЎРѓРЎРѓРЎвЂљР В°Р Р…Р С•Р Р†Р В»Р ВµР Р…Р В° fallback-Р В»Р С•Р С–Р С‘Р С”Р С•Р в„–.")
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
                warnings.append(f"{platform} v{idx}: full-schema Р Р…Р Вµ Р С—РЎР‚Р С•РЎв‚¬Р В»Р В°, Р С—РЎР‚Р С‘Р СР ВµР Р…Р ВµР Р… simplified fallback.")
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
                warnings.append(f"{platform} v{idx}: simplified Р Р…Р Вµ Р С—РЎР‚Р С•РЎв‚¬Р ВµР В», Р С—РЎР‚Р С‘Р СР ВµР Р…Р ВµР Р… free-text fallback.")
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


def _as_clean_list(value: Any, limit: int | None = None) -> list[str]:
    if isinstance(value, str):
        value = [x.strip() for x in value.split("\n") if x.strip()]
    if not isinstance(value, list):
        return []
    out = [str(x).strip() for x in value if str(x).strip()]
    if limit is not None:
        return out[:limit]
    return out


def _pad_strings(items: list[str], size: int, factory) -> list[str]:
    out = [str(x).strip() for x in items if str(x).strip()]
    while len(out) < size:
        out.append(str(factory(len(out))).strip())
    return out[:size]


def _normalize_director_platforms(platforms: list[str] | None) -> list[str]:
    out = []
    for p in platforms or []:
        key = str(p or "").strip().lower()
        if key in SUPPORTED_PLATFORMS and key not in out:
            out.append(key)
    if not out:
        out = ["facebook", "instagram"]
    return out


def _normalize_goal_for_business(goal: str) -> str:
    key = str(goal or "").strip().lower()
    mapping = {
        "awareness": "awareness",
        "РѕС…РІР°С‚": "awareness",
        "engagement": "awareness",
        "lead": "lead",
        "leads": "lead",
        "Р»РёРґС‹": "lead",
        "sales": "lead",
        "РґРѕРІРµСЂРёРµ": "trust",
        "trust": "trust",
    }
    return mapping.get(key, "awareness")


def _contains_meta_marketing_advice(text: str) -> bool:
    low = str(text or "").lower()
    return any(term in low for term in META_MARKETING_TERMS)


def _mojibake_score(text: str) -> int:
    s = str(text or "")
    return sum(s.count(ch) for ch in ("Р", "С", "Ð", "Ñ", "Â", "Ã"))


def _cyrillic_score(text: str) -> int:
    s = str(text or "")
    return sum(1 for ch in s if "\u0400" <= ch <= "\u04ff")


def _repair_mojibake_text(text: str) -> str:
    s = str(text or "")
    if not s:
        return s
    if _mojibake_score(s) < 2:
        return s
    candidates = []
    for src_enc in ("cp1251", "latin1"):
        try:
            candidate = s.encode(src_enc, errors="strict").decode("utf-8", errors="strict")
        except Exception:
            continue
        if candidate and candidate != s:
            candidates.append(candidate)
    for candidate in candidates:
        if _mojibake_score(candidate) < _mojibake_score(s) and _cyrillic_score(candidate) >= _cyrillic_score(s):
            return candidate
    return s


def _repair_mojibake_list(values: list[str]) -> list[str]:
    return [_repair_mojibake_text(v) for v in (values or [])]


def _goal_playbook(goal: str) -> dict:
    normalized = _normalize_goal_for_business(goal)
    if normalized == "lead":
        return {
            "content_types": ["useful angle", "clear value", "offer only if explicit", "next step without pressure"],
            "instruction": "Lead intent may support a commercial CTA only when the offer is explicit. Otherwise keep the post useful first and the CTA low-pressure.",
        }
    if normalized == "trust":
        return {
            "content_types": ["case insight", "specific observation", "before/after logic", "credibility without hype"],
            "instruction": "Focus on specific observations, believable proof and calm credibility instead of sales pressure.",
        }
    return {
        "content_types": ["educational tip", "common mistake", "myth vs reality", "practical checklist", "useful observation"],
        "instruction": "Focus on useful content first: one concrete point, one practical takeaway, one recognizable pattern or one simple next step.",
    }


def _topic_to_client_hook(topic: str, goal: str) -> str:
    seed = _director_topic_seed(topic, max_words=4)
    normalized = _normalize_goal_for_business(goal)
    templates = {
        "awareness": [
            "\u041e \u0447\u0451\u043c \u0441\u0442\u043e\u0438\u0442 \u043f\u043e\u043c\u043d\u0438\u0442\u044c \u0432 \u0442\u0430\u043a\u043e\u0439 \u0441\u0438\u0442\u0443\u0430\u0446\u0438\u0438",
            "3 \u043e\u0448\u0438\u0431\u043a\u0438, \u043a\u043e\u0442\u043e\u0440\u044b\u0435 \u0432\u0441\u0442\u0440\u0435\u0447\u0430\u044e\u0442\u0441\u044f \u0447\u0430\u0449\u0435 \u0432\u0441\u0435\u0433\u043e",
            "\u041a\u0430\u043a \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0431\u043e\u043b\u044c\u0448\u0435 \u043f\u043e\u043b\u044c\u0437\u044b \u0431\u0435\u0437 \u043b\u0438\u0448\u043d\u0438\u0445 \u0448\u0430\u0433\u043e\u0432",
        ],
        "lead": [
            "\u0421 \u0447\u0435\u0433\u043e \u043d\u0430\u0447\u0430\u0442\u044c, \u0435\u0441\u043b\u0438 \u0445\u043e\u0447\u0435\u0442\u0441\u044f \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 \u0431\u0435\u0437 \u0441\u0443\u0435\u0442\u044b",
            "\u041a\u0430\u043a \u043f\u043e\u043d\u044f\u0442\u044c, \u0447\u0442\u043e \u043f\u043e\u0440\u0430 \u043f\u0435\u0440\u0435\u0439\u0442\u0438 \u043a \u0441\u043b\u0435\u0434\u0443\u044e\u0449\u0435\u043c\u0443 \u0448\u0430\u0433\u0443",
            "\u041a\u0430\u043a\u043e\u0439 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 \u043c\u043e\u0436\u043d\u043e \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u043f\u0440\u0438 \u043f\u043e\u043d\u044f\u0442\u043d\u043e\u043c \u043f\u043e\u0434\u0445\u043e\u0434\u0435",
        ],
        "trust": [
            "\u0418\u0441\u0442\u043e\u0440\u0438\u044f, \u0432 \u043a\u043e\u0442\u043e\u0440\u043e\u0439 \u0440\u0435\u0448\u0438\u043b\u0438 \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0443 \u0431\u0435\u0437 \u043b\u0438\u0448\u043d\u0435\u0433\u043e \u0448\u0443\u043c\u0430",
            "\u0420\u0435\u0430\u043b\u044c\u043d\u044b\u0439 \u043a\u0435\u0439\u0441 \u0441 \u043f\u043e\u043d\u044f\u0442\u043d\u044b\u043c \u0438\u0442\u043e\u0433\u043e\u043c",
            "\u0427\u0442\u043e \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442\u0441\u044f \u0432\u0430\u0436\u043d\u0435\u0435 \u0432\u0441\u0435\u0433\u043e \u043d\u0430 \u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0435",
        ],
    }
    base = templates.get(normalized, templates["awareness"])[0]
    if base.strip().lower() == str(topic or "").strip().lower():
        base = templates.get(normalized, templates["awareness"])[1]
    return base if not seed else f"{base}: {seed}"

def _director_topic_seed(topic: str, *, max_words: int = 5) -> str:
    text = _repair_mojibake_text(str(topic or ""))
    text = re.sub(r"[\"'«»]+", " ", text)
    text = re.sub(r"[\n\r\t]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "контент в соцсетях"
    words: list[str] = []
    for raw in text.split(" "):
        tok = re.sub(r"[^\w\-]+", "", raw, flags=re.U).strip("-_")
        if tok:
            words.append(tok)
    stop = {
        "для",
        "как",
        "что",
        "это",
        "и",
        "в",
        "на",
        "по",
        "the",
        "and",
        "for",
        "with",
    }
    clean = []
    for w in words:
        low = w.lower()
        if len(low) <= 1 or low in stop:
            continue
        clean.append(w)
        if len(clean) >= max_words:
            break
    if not clean:
        clean = words[:max_words]
    seed = " ".join(clean).strip()
    if len(seed) < 8 and len(words) >= 2:
        seed = " ".join(words[:max_words]).strip()
    return seed[:72] if len(seed) > 72 else seed


def _director_recommendation(platforms: list[str], goal: str, tone: str) -> dict:
    ordered = _normalize_director_platforms(platforms)
    platform = "instagram" if "instagram" in ordered else ordered[0]
    fmt = "video" if platform == "youtube" else ("reel" if platform == "instagram" else "post")
    return {"platform": platform, "format": fmt, "tone": tone if tone in SUPPORTED_TONES else "friendly"}


def _director_goal_topic_templates(seed: str, goal: str, offer: str | None) -> list[str]:
    normalized = _normalize_goal_for_business(goal)
    offer_short = re.sub(r"\s+", " ", str(offer or "").strip())[:56]
    if normalized == "lead":
        return [
            f"С чего начать, если вам нужен понятный результат по теме {seed}",
            f"{seed}: что входит в предложение и кому это подходит",
            f"Почему сейчас подходящий момент заняться темой {seed}",
            f"Что вы получите, если выбрать {offer_short or seed}",
            f"Какие вопросы стоит задать перед выбором решения по теме {seed}",
            f"Как понять, что вам подходит именно такой формат помощи",
            f"3 причины не откладывать следующий шаг по теме {seed}",
            f"{seed}: как получить пользу уже на первом этапе",
        ]
    if normalized == "trust":
        return [
            f"История, в которой результат по теме {seed} стал заметен без лишнего шума",
            f"Реальный пример: что меняется, когда подход к теме {seed} становится понятным",
            f"До и после: как выглядит путь по теме {seed} по шагам",
            f"Что обычно оказывается самым важным в теме {seed} на практике",
            f"Кейс недели: аккуратный процесс и понятный результат",
            f"Как обычно проходит работа по теме {seed} без сюрпризов",
            f"Что люди чаще всего отмечают после такого опыта",
            f"Почему доверие к теме {seed} строится на понятных фактах, а не обещаниях",
        ]
    # awareness-like playbook
    base = [
        f"3 ошибки, которые часто мешают в теме {seed}",
        f"Миф и правда о теме {seed}",
        f"Почему люди часто сталкиваются с трудностями в теме {seed}",
        f"5 практических наблюдений по теме {seed}",
        f"О чём стоит помнить, если вас касается тема {seed}",
        f"Что важно понять до того, как делать следующий шаг в теме {seed}",
        f"Простой чек-лист по теме {seed} без лишней теории",
        f"Частые вопросы по теме {seed} простыми словами",
    ]
    if offer_short:
        base[4] = f"Как получить пользу уже сейчас, если вам подходит {offer_short}"
    return base


def _director_default_payload(
    topic: str,
    offer: str | None,
    goal: str,
    platforms: list[str],
    tone: str,
    language: str = "ru",
    niche_label: str | None = None,
    niche_context: dict | None = None,
    variation_seed: int = 0,
) -> dict:
    niche_context = niche_context if isinstance(niche_context, dict) else {}
    niche_label = str(niche_label or niche_context.get("label") or topic or "").strip()
    niche_keywords = [str(x).strip() for x in (niche_context.get("keywords") or []) if str(x).strip()]
    niche_pain_points = [str(x).strip() for x in (niche_context.get("painPoints") or []) if str(x).strip()]
    niche_content_angles = [str(x).strip() for x in (niche_context.get("contentAngles") or []) if str(x).strip()]
    niche_topic_templates = [str(x).strip() for x in (niche_context.get("topicTemplates") or []) if str(x).strip()]
    niche_cta_templates = [str(x).strip() for x in (niche_context.get("ctaTemplates") or []) if str(x).strip()]
    niche_audience = str(niche_context.get("audience") or "").strip()
    goal_mode = _normalize_goal_for_business(goal)
    base = _director_topic_seed(topic)
    offer_part = f" Р С›РЎвЂћРЎвЂћР ВµРЎР‚: {offer}." if offer else ""
    topic_templates = niche_topic_templates or _director_goal_topic_templates(base, goal, offer)
    shift = abs(int(variation_seed or 0))
    topics_pool = topic_templates[:]
    if shift and topics_pool:
        shift = shift % len(topics_pool)
        topics_pool = topics_pool[shift:] + topics_pool[:shift]
    topics = _pad_strings(
        [],
        10,
        lambda i: topics_pool[i] if i < len(topics_pool) else topic_templates[i % len(topic_templates)],
    )
    if niche_content_angles:
        angle_pool = []
        for angle in niche_content_angles:
            clean_angle = _repair_mojibake_text(angle)
            angle_pool.append(f"Через {clean_angle}: что это значит для человека на практике")
        for angle in niche_content_angles:
            clean_angle = _repair_mojibake_text(angle)
            angle_pool.append(f"Через {clean_angle}: как это применить в реальной жизни")
    elif goal_mode == "lead":
        angle_pool = [
            "Через пользу: что человек получает уже в первый день",
            "Через срочность: почему лучше не откладывать следующий шаг",
            "Через оффер: что входит в предложение и кому это подходит",
            "Через FAQ: закрываем частые сомнения перед обращением",
            "Через результат: понятный итог без лишних обещаний",
        ]
    elif goal_mode == "trust":
        angle_pool = [
            "Через кейс: что изменилось и за счёт чего",
            "Через отзыв: реальный опыт и аргументы без шума",
            "Через прозрачный процесс: что происходит на каждом этапе",
            "Через до/после: наглядное доказательство результата",
            "Через экспертность: объясняем простыми словами и по делу",
        ]
    else:
        angle_pool = [
            "Через полезный совет: что можно применить сразу",
            "Через миф и факт: разбираем частое заблуждение",
            "Через проблему и решение: как избежать типичной ошибки",
            "Через список: 3-5 конкретных рекомендаций",
            "Через тренд: что нового и как это использовать с пользой",
        ]
    if shift and angle_pool:
        angle_shift = shift % len(angle_pool)
        angle_pool = angle_pool[angle_shift:] + angle_pool[:angle_shift]
    angles = _pad_strings(
        [],
        3,
        lambda i: angle_pool[i],
    )
    cta_options = _default_cta_options(goal, offer, language, niche_cta_templates)
    goal_tag_map = {
        "awareness": ["#советы", "#мифыифакты", "#полезно", "#разбор", "#практика"],
        "lead": ["#решение", "#помощь", "#предложение", "#следующийшаг", "#услуги"],
        "trust": ["#кейс", "#отзывы", "#доипосле", "#результат", "#доверие"],
    }
    tag_seed_source = niche_label or base
    seed_tags = []
    for raw_word in re.findall(r"\w+", tag_seed_source or "", flags=re.U)[:6]:
        safe_tag = _sanitize_hashtag_token(raw_word)
        if safe_tag and len(safe_tag) > 3 and safe_tag not in seed_tags:
            seed_tags.append(safe_tag)
        if len(seed_tags) >= 3:
            break
    keyword_tags = [f"#{w.lower()}" for w in niche_keywords[:4] if len(w) > 2]
    core_tags = goal_tag_map.get(goal_mode, goal_tag_map["awareness"]) + keyword_tags + ["#практика", "#разбор"] + seed_tags
    # unique + stable order
    uniq = []
    seen_tags = set()
    for t in core_tags:
        tt = str(t).strip().lower()
        if not tt.startswith("#"):
            tt = f"#{tt}"
        if tt in seen_tags:
            continue
        seen_tags.add(tt)
        uniq.append(tt)
    if shift and uniq:
        s = shift % len(uniq)
        uniq = uniq[s:] + uniq[:s]
    tags = [
        uniq[:5],
        uniq[2:7] if len(uniq) >= 7 else uniq[:5],
        uniq[4:9] if len(uniq) >= 9 else uniq[:5],
    ]
    return {
        "audience": {
            "who": _repair_mojibake_text(niche_audience) or "Люди, которым нужен понятный и полезный контент по теме",
            "pain": _repair_mojibake_text(niche_pain_points[0] if niche_pain_points else "") or "Сложно понять, что действительно важно и как избежать типичных ошибок",
            "desire": f"Получить понятную пользу, реальную ясность и уверенность перед следующим шагом.{offer_part}",
        },
        "topics": topics,
        "angles": _repair_mojibake_list(angles),
        "recommended": _director_recommendation(platforms, goal=goal, tone=tone),
        "cta_options": _repair_mojibake_list(cta_options),
        "hashtag_sets": [_repair_mojibake_list(row) for row in tags],
        "reason": f"Темы подобраны под нишу «{_repair_mojibake_text(niche_label or topic)}» и ориентированы на полезный, понятный контент для людей.",
    }


def _director_soft_normalize(
    payload: dict,
    *,
    topic: str,
    offer: str | None,
    goal: str,
    platforms: list[str],
    tone: str,
    niche_label: str | None = None,
    niche_context: dict | None = None,
    variation_seed: int = 0,
) -> dict:
    default = _director_default_payload(topic, offer, goal, platforms, tone, language=language, niche_label=niche_label, niche_context=niche_context, variation_seed=variation_seed)
    if not isinstance(payload, dict):
        return default
    audience = payload.get("audience")
    if not isinstance(audience, dict):
        audience = {}
    audience_norm = {
        "who": str(audience.get("who") or default["audience"]["who"]).strip(),
        "pain": str(audience.get("pain") or default["audience"]["pain"]).strip(),
        "desire": str(audience.get("desire") or default["audience"]["desire"]).strip(),
    }
    source_topics = _as_clean_list(payload.get("topics"), limit=16)
    cleaned_topics = []
    original_topic_low = str(topic or "").strip().lower()
    for item in source_topics:
        t = _repair_mojibake_text(str(item).strip())
        if not t:
            continue
        if _contains_meta_marketing_advice(t):
            continue
        if not _has_explicit_offer(offer) and _looks_service_framed_topic_no_offer(t):
            continue
        if t.lower() == original_topic_low:
            t = _topic_to_client_hook(topic, goal)
        cleaned_topics.append(t)
    topics = _pad_strings(
        cleaned_topics,
        10,
        lambda i: default["topics"][i],
    )
    topics = [str(x).strip()[:96] for x in topics]
    source_angles = _as_clean_list(payload.get("angles"), limit=8)
    cleaned_angles = [a for a in source_angles if not _contains_meta_marketing_advice(a)]
    angles = _pad_strings(
        cleaned_angles,
        3,
        lambda i: default["angles"][i],
    )
    angles = [str(x).strip()[:80] for x in angles]
    raw_cta_options = _as_clean_list(payload.get("cta_options"), limit=8)
    if _cta_mode(goal, offer) != "service":
        raw_cta_options = [x for x in raw_cta_options if not _looks_hard_sell_cta(x)]
    cta_options = _pad_strings(
        raw_cta_options,
        3,
        lambda i: default["cta_options"][i],
    )
    recommended = payload.get("recommended")
    if not isinstance(recommended, dict):
        recommended = {}
    rec_platform = str(recommended.get("platform") or default["recommended"]["platform"]).strip().lower()
    if rec_platform not in SUPPORTED_PLATFORMS:
        rec_platform = default["recommended"]["platform"]
    rec_format = str(recommended.get("format") or default["recommended"]["format"]).strip().lower()
    if rec_format not in {"post", "reel", "video"}:
        rec_format = default["recommended"]["format"]
    rec_tone = str(recommended.get("tone") or default["recommended"]["tone"]).strip().lower()
    if rec_tone not in SUPPORTED_TONES:
        rec_tone = default["recommended"]["tone"]
    hashtag_sets = payload.get("hashtag_sets")
    tags_norm: list[list[str]] = []
    if isinstance(hashtag_sets, list):
        for idx, row in enumerate(hashtag_sets):
            row_tags = [str(x).strip() for x in (row if isinstance(row, list) else []) if str(x).strip()]
            if row_tags:
                row_tags = _sanitize_hashtag_list(row_tags, min_count=min(3, max(1, len(row_tags))), max_count=15)
                if len(row_tags) < 3:
                    fallback_row = default["hashtag_sets"][idx % len(default["hashtag_sets"])]
                    for tag in fallback_row:
                        if len(row_tags) >= 3:
                            break
                        if tag not in row_tags:
                            row_tags.append(tag)
                row_tags = _sanitize_hashtag_list(row_tags, min_count=3, max_count=15)
                tags_norm.append(row_tags[:15])
    while len(tags_norm) < 3:
        tags_norm.append(default["hashtag_sets"][len(tags_norm)])
    tags_norm = tags_norm[:3]
    reason = str(payload.get("reason") or default["reason"]).strip()
    return {
        "audience": audience_norm,
        "topics": topics,
        "angles": angles,
        "recommended": {"platform": rec_platform, "format": rec_format, "tone": rec_tone},
        "cta_options": cta_options,
        "hashtag_sets": tags_norm,
        "reason": reason,
    }


def _parse_director_text_fallback(
    text: str,
    *,
    topic: str,
    offer: str | None,
    goal: str,
    platforms: list[str],
    tone: str,
    niche_label: str | None = None,
    niche_context: dict | None = None,
    variation_seed: int = 0,
) -> dict:
    lines = [x.strip("-РІР‚Сћ \t") for x in str(text or "").splitlines() if x.strip()]
    topics = [x for x in lines if len(x) > 18][:10]
    angles = [x for x in lines if len(x) > 10][:3]
    return _director_soft_normalize(
        {
            "topics": topics,
            "angles": angles,
            "cta_options": lines[:3],
            "reason": "Р С›РЎвЂљР Р†Р ВµРЎвЂљ Р Р…Р С•РЎР‚Р СР В°Р В»Р С‘Р В·Р С•Р Р†Р В°Р Р… Р С‘Р В· РЎвЂљР ВµР С”РЎРѓРЎвЂљР С•Р Р†Р С•Р С–Р С• fallback.",
        },
        topic=topic,
        offer=offer,
        goal=goal,
        platforms=platforms,
        tone=tone,
        niche_label=niche_label,
        niche_context=niche_context,
        variation_seed=variation_seed,
    )


def director_suggest(
    *,
    topic: str,
    offer: str | None,
    language: str,
    tone: str,
    goal: str,
    platforms: list[str],
    niche_label: str | None = None,
    niche_context: dict | None = None,
    variation_seed: int = 0,
) -> dict:
    topic = str(topic or "").strip()
    if not topic:
        raise ValueError("topic is required")
    language = str(language or "ru").strip().lower()
    if language not in SUPPORTED_LANGUAGES:
        language = "ru"
    tone = str(tone or "friendly").strip().lower()
    if tone not in SUPPORTED_TONES:
        tone = "friendly"
    goal = str(goal or "engagement").strip().lower()
    if goal not in SUPPORTED_GOALS:
        goal = "engagement"
    goal = _normalize_goal_for_business(goal)
    platforms = _normalize_director_platforms(platforms)
    default_payload = _director_default_payload(topic, offer, goal, platforms, tone, language=language, niche_label=niche_label, niche_context=niche_context, variation_seed=variation_seed)
    if not is_openai_enabled():
        return {"status": "ok", "data": default_payload, "warnings": [], "debug_code": "mock"}

    warnings = []
    debug_code = ""
    schema = {
        "audience": {"who": "string", "pain": "string", "desire": "string"},
        "topics": ["string", "string", "string", "string", "string", "string", "string", "string", "string", "string"],
        "angles": ["string", "string", "string"],
        "recommended": {"platform": "facebook", "format": "post", "tone": "friendly"},
        "cta_options": ["string", "string", "string"],
        "hashtag_sets": [["#one", "#two", "#three"], ["#four", "#five", "#six"], ["#seven", "#eight", "#nine"]],
        "reason": "string",
    }

    def _soft_validator(payload: dict) -> None:
        if not isinstance(payload, dict):
            raise ValueError("payload must be object")
        if not _as_clean_list(payload.get("topics")):
            raise ValueError("topics empty")
        if not _as_clean_list(payload.get("angles")):
            raise ValueError("angles empty")

    try:
        res = generate_json_with_retry(
            system_prompt=(
                "You are an AI Content Director for niche-aware social content. Return JSON only. "
                "Always write value-first ideas for real people. "
                "Never provide marketing advice for marketers. "
                "Never mention: reach, engagement, content strategy, РѕС…РІР°С‚, РІРѕРІР»РµС‡РµРЅРёРµ, РєРѕРЅС‚РµРЅС‚-СЃС‚СЂР°С‚РµРіРёСЏ. "
                "Do not copy user topic verbatim as headlines. Keep suggestions short, practical, useful and not falsely promotional by default."
            ),
            user_prompt=(
                f"topic: {topic}\noffer: {offer or ''}\nlanguage: {language}\ntone: {tone}\ngoal: {goal}\n"
                f"niche_label: {niche_label or ''}\n"
                f"niche_audience: {str((niche_context or {}).get('audience') or '')}\n"
                f"niche_pain_points: {', '.join((niche_context or {}).get('painPoints') or [])}\n"
                f"niche_angles: {', '.join((niche_context or {}).get('contentAngles') or [])}\n"
                f"avoid_cross_niche_words: {', '.join((niche_context or {}).get('bannedCrossNicheWords') or [])}\n"
                f"platforms: {', '.join(platforms)}\n"
                f"goal interpretation: {_goal_playbook(goal)['instruction']}\n"
                "constraints: return exactly 10 topics max 96 chars, angles max 80 chars, useful and niche-native wording only.\n"
                f"schema: {json.dumps(schema, ensure_ascii=False)}"
            ),
            validator=_soft_validator,
            max_output_tokens=900,
            temperature=0.5,
        )
        data = _director_soft_normalize(
            res.payload,
            topic=topic,
            offer=offer,
            goal=goal,
            platforms=platforms,
            tone=tone,
            niche_label=niche_label,
            niche_context=niche_context,
            variation_seed=variation_seed,
        )
        return {"status": "ok", "data": data, "warnings": warnings, "debug_code": debug_code}
    except Exception as exc:
        if "insufficient_quota" in str(exc).lower():
            return {
                "status": "partial",
                "data": default_payload,
                "warnings": ["openai_quota_exceeded"],
                "debug_code": "director_openai_quota",
            }
        warnings.append("structured_json_failed")
        debug_code = "director_structured_failed"

    try:
        # simplified schema fallback
        res = generate_json_with_retry(
            system_prompt="Return only JSON with arrays topics/angles/cta_options.",
            user_prompt=f"topic: {topic}\nneed 10 topics, 3 angles, 3 cta\nschema: {{\"topics\":[\"\"],\"angles\":[\"\"],\"cta_options\":[\"\"]}}",
            validator=lambda p: None if isinstance(p, dict) else (_ for _ in ()).throw(ValueError("bad")),
            max_output_tokens=500,
            temperature=0.45,
        )
        data = _director_soft_normalize(
            res.payload,
            topic=topic,
            offer=offer,
            goal=goal,
            platforms=platforms,
            tone=tone,
            niche_label=niche_label,
            niche_context=niche_context,
            variation_seed=variation_seed,
        )
        warnings.append("simplified_schema_used")
        return {"status": "partial", "data": data, "warnings": warnings, "debug_code": f"{debug_code}|director_simplified"}
    except Exception as exc:
        if "insufficient_quota" in str(exc).lower():
            return {
                "status": "partial",
                "data": default_payload,
                "warnings": ["openai_quota_exceeded"],
                "debug_code": "director_openai_quota",
            }
        warnings.append("simplified_failed")

    try:
        # free text fallback
        from openai_client import _client as _raw_client  # local import to avoid exporting internals globally

        model = "gpt-4o-mini"
        cli = _raw_client()
        resp = cli.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Return concise text with topics, angles, CTA ideas."},
                {"role": "user", "content": f"topic: {topic}\nProvide 10 topics, 3 angles, 3 CTA lines."},
            ],
            max_tokens=500,
            temperature=0.5,
        )
        text = (resp.choices[0].message.content or "").strip()
        data = _parse_director_text_fallback(
            text,
            topic=topic,
            offer=offer,
            goal=goal,
            platforms=platforms,
            tone=tone,
            niche_label=niche_label,
            niche_context=niche_context,
            variation_seed=variation_seed,
        )
        warnings.append("free_text_parsed")
        return {"status": "partial", "data": data, "warnings": warnings, "debug_code": f"{debug_code}|director_text_parse"}
    except Exception:
        pass

    return {
        "status": "partial",
        "data": default_payload,
        "warnings": warnings + ["hard_fallback_default"],
        "debug_code": f"{debug_code}|director_default",
    }


def director_generate_drafts(
    *,
    topic: str,
    offer: str | None,
    angle: str,
    goal: str,
    platforms: list[str],
    tone: str,
    language: str,
    niche_label: str | None = None,
    niche_context: dict | None = None,
    variants: int = 3,
) -> dict:
    platforms = _normalize_director_platforms(platforms)
    variants = max(1, min(int(variants or 3), 3))
    goal = _normalize_goal_for_business(goal)
    warnings: list[str] = []
    debug_code = ""
    drafts: list[dict] = []
    client_hook_seed = _topic_to_client_hook(topic, goal)
    niche_label = str(niche_label or (niche_context or {}).get("label") or "").strip()
    core_rows: dict[int, dict] = {}
    primary_platform = platforms[0] if platforms else "facebook"
    core_topic = str(topic or "").strip()

    if not is_openai_enabled():
        for idx in range(1, variants + 1):
            core_rows[idx] = _generate_free_text_fallback_draft(
                platform=primary_platform,
                variant_index=idx,
                topic=core_topic,
                offer=offer,
                goal=goal,
                angle=angle,
            )
        for platform in platforms:
            for idx in range(1, variants + 1):
                row = _adapt_core_row_for_platform(
                    core_rows[idx],
                    platform=platform,
                    variant_index=idx,
                    topic=topic,
                    niche_label=niche_label,
                    language=language,
                    goal=goal,
                    offer=offer,
                )
                drafts.append(
                    {
                        "platform": platform,
                        "variant": idx,
                        "hook": client_hook_seed[:180],
                        "body_text": row["post_text"],
                        "cta": row["cta"],
                        "hashtags": row["hashtags"],
                        "warnings": [],
                    }
                )
        return {"status": "ok", "data": {"drafts": drafts, "strategy": {}}, "warnings": [], "debug_code": "mock"}

    for idx in range(1, variants + 1):
        row = None
        try:
            row, _, _ = _generate_simplified_draft(
                topic=core_topic,
                offer=offer,
                language=language,
                tone=tone,
                goal=goal,
                platform=primary_platform,
                variant_index=idx,
            )
        except Exception:
            warnings.append(f"core v{idx}: simplified_failed")
            debug_code = (debug_code + "|director_fast_simplified_failed").strip("|")
            try:
                row = _generate_free_text_fallback_draft(
                    platform=primary_platform,
                    variant_index=idx,
                    topic=core_topic,
                    offer=offer,
                    goal=goal,
                    angle=angle,
                )
            except Exception:
                row = None
        if row:
            core_rows[idx] = row

    for platform in platforms:
        for idx in range(1, variants + 1):
            source_row = core_rows.get(idx)
            if not source_row:
                continue
            row = _adapt_core_row_for_platform(
                source_row,
                platform=platform,
                variant_index=idx,
                topic=topic,
                niche_label=niche_label,
                language=language,
                goal=goal,
                offer=offer,
            )
            drafts.append(
                {
                    "platform": platform,
                    "variant": idx,
                    "hook": client_hook_seed[:180],
                    "body_text": row["post_text"],
                    "cta": row["cta"],
                    "hashtags": row["hashtags"],
                    "warnings": [],
                }
            )

    if not drafts:
        fallback_row = _adapt_core_row_for_platform(
            _generate_free_text_fallback_draft(
                platform=primary_platform,
                variant_index=1,
                topic=core_topic,
                offer=offer,
                goal=goal,
                angle=angle,
            ),
            platform=primary_platform,
            variant_index=1,
            topic=topic,
            niche_label=niche_label,
            language=language,
            goal=goal,
            offer=offer,
        )
        drafts = [
            {
                "platform": primary_platform,
                "variant": 1,
                "hook": client_hook_seed,
                "body_text": fallback_row["post_text"],
                "cta": fallback_row["cta"],
                "hashtags": fallback_row["hashtags"],
                "warnings": ["hard_fallback_default"],
            }
        ]
        warnings.append("hard_fallback_default")

    status = "partial" if warnings else "ok"
    return {
        "status": status,
        "data": {"drafts": drafts, "strategy": {}},
        "warnings": warnings,
        "debug_code": debug_code,
    }


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
    "director_suggest",
    "director_generate_drafts",
    "generateHashtags",
    "generate_hashtags",
]





