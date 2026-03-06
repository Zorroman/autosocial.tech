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
    "контент-стратег",
    "охват",
    "вовлечение",
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
        lambda i: f"РљР»СЋС‡РµРІРѕР№ С‚РµР·РёСЃ {i + 1}",
    )
    payload["hook_ideas"] = _pad_list(
        [str(x).strip() for x in (payload.get("hook_ideas") or []) if str(x).strip()],
        5,
        lambda i: f"РҐСѓРє {i + 1}: РїСЂР°РєС‚РёС‡РµСЃРєРёР№ РёРЅСЃР°Р№С‚ РїРѕ С‚РµРјРµ",
    )
    payload["cta_variants"] = _pad_list(
        [str(x).strip() for x in (payload.get("cta_variants") or []) if str(x).strip()],
        3,
        lambda i: f"CTA {i + 1}: РќР°РїРёС€РёС‚Рµ РІ РґРёСЂРµРєС‚, РїРѕРґР±РµСЂРµРј СЂРµС€РµРЅРёРµ РїРѕРґ РІР°С€Сѓ Р·Р°РґР°С‡Сѓ.",
    )
    payload["visual_ideas"] = _pad_list(
        [str(x).strip() for x in (payload.get("visual_ideas") or []) if str(x).strip()],
        5,
        lambda i: f"Р’РёР·СѓР°Р» {i + 1}: СЂРµР°Р»РёСЃС‚РёС‡РЅС‹Р№ Р±РёР·РЅРµСЃ-СЃСЋР¶РµС‚ Р±РµР· С‚РµРєСЃС‚Р° РЅР° РёР·РѕР±СЂР°Р¶РµРЅРёРё.",
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
            "objection": f"Р’РѕР·СЂР°Р¶РµРЅРёРµ {i + 1}: СЌС‚Рѕ СЃР»РѕР¶РЅРѕ РІРЅРµРґСЂРёС‚СЊ",
            "answer": "Р Р°Р·Р±РёРІР°РµРј РІРЅРµРґСЂРµРЅРёРµ РЅР° 2-3 РєРѕСЂРѕС‚РєРёС… С€Р°РіР° Рё Р·Р°РїСѓСЃРєР°РµРј Р±РµР· РїРµСЂРµРіСЂСѓР·Р° РєРѕРјР°РЅРґС‹.",
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
        lambda _: ["#РєРѕРЅС‚РµРЅС‚", "#РјР°СЂРєРµС‚РёРЅРі", "#Р±РёР·РЅРµСЃ"],
    )
    payload["hashtag_sets"] = [s if len(s) >= 3 else _pad_list(s, 3, lambda __: "#РєРѕРЅС‚РµРЅС‚") for s in hashtag_sets_norm]


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
        "You are a local business content strategist. "
        "Always write from the business perspective to end customers. "
        "Never output marketing-advice language for marketers. "
        "Never mention: reach, engagement, content strategy, охват, вовлечение, контент-стратегия. "
        "Never invent specific product facts if offer is empty. "
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
        "You are a senior copywriter for local businesses. "
        "Write customer-facing content from business perspective. "
        "Audience is end customers, not marketers. "
        "Never mention: reach, engagement, content strategy, охват, вовлечение, контент-стратегия. "
        "Never write marketing advice about algorithms or content systems. "
        "Transform theme into a client hook; never reuse the theme verbatim as headline. "
        "Generate clean, realistic social media hashtags. Do not use random characters. "
        "Do not transliterate incorrectly. No punctuation. "
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
        "sales": "РїСЂРѕРґР°Р¶Р°",
        "lead": "Р»РёРґ",
        "engagement": "РІРѕРІР»РµС‡РµРЅРёРµ",
        "awareness": "СѓР·РЅР°РІР°РµРјРѕСЃС‚СЊ",
        "trust": "доверие",
    }
    return mapping.get(str(goal or "").strip().lower(), "РІРѕРІР»РµС‡РµРЅРёРµ")


def _fallback_strategy(topic: str, offer: str | None, goal: str) -> dict:
    strategy = _mock_strategy(topic=topic, offer=offer, goal=goal)
    strategy["angle"] = f"РџСЂР°РєС‚РёС‡РµСЃРєРёР№ СЂР°Р·Р±РѕСЂ С‚РµРјС‹ В«{topic}В» РїРѕРґ С†РµР»СЊ: {_goal_label(goal)}"
    strategy["context"] = (
        f"РђСѓРґРёС‚РѕСЂРёРё РЅСѓР¶РµРЅ РїРѕРЅСЏС‚РЅС‹Р№ СЃС†РµРЅР°СЂРёР№ РґРµР№СЃС‚РІРёР№ РїРѕ С‚РµРјРµ В«{topic}В»."
        + (f" РћС„С„РµСЂ: {offer}." if offer else "")
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
        tags = ["#локальныйбизнес", "#услуги", "#сервис", "#рекомендуем", "#актуально"]
    return _sanitize_hashtag_list(tags, min_count=min(5, limit), max_count=min(12, limit))


def _normalize_hashtag_language(language: str) -> str:
    key = str(language or "").strip().lower()
    if key in {"русский", "ru", "russian"}:
        return "ru"
    if key in {"deutsch", "de", "german"}:
        return "de"
    return "en"


def _sanitize_hashtag_token(token: str, *, max_len: int = 29) -> str:
    raw = str(token or "").strip().lower()
    if raw.startswith("#"):
        raw = raw[1:]
    cleaned = "".join(ch for ch in raw if ch.isalnum())
    cleaned = cleaned[:max_len].strip()
    return f"#{cleaned}" if cleaned else ""


def _sanitize_hashtag_list(tags: list[str], *, min_count: int = 5, max_count: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        safe = _sanitize_hashtag_token(tag)
        if not safe:
            continue
        if "," in safe or "'" in safe or "’" in safe:
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
        filler = ["#локальныйбизнес", "#услуги", "#вашгород", "#рекомендуем", "#актуально"]
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
                "engagement": ["#стильмужчины", "#мужскойстиль"],
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
            ("barbershop", ["barber", "barbershop", "барбер", "барбершоп"]),
            ("beauty", ["beauty", "салон", "красот"]),
            ("auto", ["auto", "авто", "service", "сервис"]),
            ("restaurant", ["restaurant", "ресторан"]),
            ("cafe", ["cafe", "кафе", "coffee"]),
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
            niche_tags = [f"#{re.sub(r'[^0-9a-zа-я]+', '', niche_raw, flags=re.I) or 'локальныйбизнес'}", "#услуги"]
            service_tags = ["#качество", "#сервис"]
            engagement_tags = ["#рекомендуем", "#актуально"]
        elif lang == "de":
            niche_tags = [f"#{re.sub(r'[^0-9a-zäöüß]+', '', niche_raw, flags=re.I) or 'lokal'}", "#dienstleistung"]
            service_tags = ["#qualität", "#service"]
            engagement_tags = ["#empfehlung", "#regional"]
        else:
            niche_tags = [f"#{re.sub(r'[^0-9a-z]+', '', niche_raw, flags=re.I) or 'localbusiness'}", "#service"]
            service_tags = ["#quality", "#trusted"]
            engagement_tags = ["#recommended", "#local"]

    goal_service_overrides = {
        "lead": {"ru": ["#запись", "#акция"], "de": ["#termin", "#angebot"], "en": ["#booknow", "#offer"]},
        "trust": {"ru": ["#отзывы", "#результат"], "de": ["#kundenstimmen", "#ergebnis"], "en": ["#testimonial", "#results"]},
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
        if any(k in low for k in ["РЅР°РїРёС€РёС‚Рµ", "РѕСЃС‚Р°РІСЊС‚Рµ", "РїРµСЂРµР№РґРёС‚Рµ", "Р·Р°РїРёС€РёС‚РµСЃСЊ", "РєСѓРїРёС‚Рµ", "РїРѕРґРїРёС€РёС‚РµСЃСЊ"]):
            return line
    return "РќР°РїРёС€РёС‚Рµ РІ РґРёСЂРµРєС‚, С‡С‚РѕР±С‹ РїРѕР»СѓС‡РёС‚СЊ РґРµС‚Р°Р»Рё."


def _ensure_platform_draft_shape(draft: dict, *, platform: str, variant_index: int) -> dict:
    out = dict(draft or {})
    out["platform"] = platform
    out["variant_index"] = int(variant_index or 1)
    out["post_text"] = str(out.get("post_text") or "").strip()
    out["cta"] = str(out.get("cta") or "").strip()
    out["hashtags"] = [str(x).strip() for x in (out.get("hashtags") or []) if str(x).strip()]
    out["asset_ideas"] = [str(x).strip() for x in (out.get("asset_ideas") or []) if str(x).strip()]
    if not out["post_text"]:
        out["post_text"] = f"{platform.title()}: {variant_index}. {out.get('title') or 'РџСЂР°РєС‚РёС‡РµСЃРєРёР№ РїРѕСЃС‚ РїРѕ С‚РµРјРµ.'}"
    if not out["cta"]:
        out["cta"] = _extract_cta_from_text(out["post_text"])
    if not out["hashtags"]:
        out["hashtags"] = _extract_hashtags_from_text(out["post_text"])
    if len(out["asset_ideas"]) < 3:
        while len(out["asset_ideas"]) < 3:
            out["asset_ideas"].append("Р РµР°Р»РёСЃС‚РёС‡РЅС‹Р№ РєР°РґСЂ РїРѕ С‚РµРјРµ Р±РµР· С‚РµРєСЃС‚Р° РЅР° РёР·РѕР±СЂР°Р¶РµРЅРёРё.")
    if platform == "youtube":
        out["title"] = str(out.get("title") or "").strip() or "РџСЂР°РєС‚РёС‡РµСЃРєРёР№ СЂР°Р·Р±РѕСЂ С‚РµРјС‹"
        out["description"] = str(out.get("description") or "").strip() or out["post_text"]
        out["pinned_comment_text"] = str(out.get("pinned_comment_text") or "").strip() or "РљР°РєРѕР№ С€Р°Рі РІС‹ РІРЅРµРґСЂРёС‚Рµ РїРµСЂРІС‹Рј?"
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
        "You are a local business copywriter. Return compact JSON only. "
        "Write from business perspective for end customers. "
        "Never write marketing advice for marketers. "
        "Never mention: reach, engagement, content strategy, охват, вовлечение, контент-стратегия. "
        "No extra keys."
    )
    user = (
        f"topic: {topic}\n"
        f"offer: {offer or ''}\n"
        f"language: {language}\n"
        f"tone: {tone}\n"
        f"goal: {goal}\n"
        f"goal_playbook: {', '.join(playbook['content_types'])}\n"
        f"platform: {platform}\n"
        f"variant: {variant_index}\n"
        "theme must be transformed to client hook, not copied verbatim as headline.\n"
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
                "РљСЂСѓРїРЅС‹Р№ РїР»Р°РЅ РїСЂРѕРґСѓРєС‚Р°/СѓСЃР»СѓРіРё Р±РµР· С‚РµРєСЃС‚Р°",
                "РЎС†РµРЅР° РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ РІ СЂРµР°Р»СЊРЅРѕР№ СЃСЂРµРґРµ",
                "Р”Рѕ/РїРѕСЃР»Рµ РёР»Рё РїСЂРѕС†РµСЃСЃ РІ 3 С€Р°РіР°С…",
            ],
            "pinned_comment_text": "РќР°РїРёС€РёС‚Рµ РІР°С€ РІРѕРїСЂРѕСЃ РІ РєРѕРјРјРµРЅС‚Р°СЂРёСЏС….",
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
    goal_mode = _normalize_goal_for_business(goal)
    hook = _topic_to_client_hook(topic, goal_mode)
    goal_part = {
        "lead": "Сделайте акцент на оффере, ограничении по времени и понятной записи.",
        "trust": "Покажите реальный кейс клиента, отзыв и формат «до/после».",
        "awareness": "Дайте полезный совет, разберите миф и предложите простое решение.",
    }.get(goal_mode, "Покажите практическую ценность для клиента.")
    text = (
        f"{hook}\n\n"
        f"{goal_part}\n"
        f"{('Предложение: ' + offer) if offer else ''}\n\n"
        "1) Какая проблема у клиента.\n"
        "2) Как вы решаете ее на практике.\n"
        "3) Что клиент получает в итоге.\n"
        "4) CTA: напишите в сообщения для записи."
    ).strip()
    if _contains_meta_marketing_advice(text):
        text = f"{hook}\n\nПокажите клиенту понятную пользу и завершите призывом к записи."
    return _ensure_platform_draft_shape(
        {
            "platform": platform,
            "variant_index": variant_index,
            "post_text": text,
            "title": f"{hook}: практический разбор" if platform == "youtube" else None,
            "description": text if platform == "youtube" else None,
            "hashtags": _extract_hashtags_from_text(text),
            "cta": "Напишите в сообщения, чтобы забронировать удобное время.",
            "asset_ideas": [
                "Р РµР°Р»РёСЃС‚РёС‡РЅР°СЏ СЃС†РµРЅР° РїРѕ С‚РµРјРµ Р±РµР· С‚РµРєСЃС‚Р°",
                "РџСЂРѕС†РµСЃСЃ/workflow РІ СЂР°Р±РѕС‡РµРј РѕРєСЂСѓР¶РµРЅРёРё",
                "РљСЂСѓРїРЅС‹Р№ РїР»Р°РЅ РєР»СЋС‡РµРІРѕРіРѕ СЌР»РµРјРµРЅС‚Р° РѕС„С„РµСЂР°",
            ],
            "pinned_comment_text": "РљР°РєРѕР№ С€Р°Рі РІС‹ РїРѕРїСЂРѕР±СѓРµС‚Рµ РїРµСЂРІС‹Рј?" if platform == "youtube" else None,
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
            "hook": f"{base}: С‡С‚Рѕ РІР°Р¶РЅРѕ РїСЂРѕРІРµСЂРёС‚СЊ РґРѕ СЃС‚Р°СЂС‚Р°?",
            "angles": [
                f"3 С‡Р°СЃС‚С‹Рµ РѕС€РёР±РєРё РІ С‚РµРјРµ В«{base}В»",
                f"Р§РµРє-Р»РёСЃС‚ РІРЅРµРґСЂРµРЅРёСЏ В«{base}В» Р·Р° 1 РґРµРЅСЊ",
                f"РљРµР№СЃ: РєР°Рє РїСЂРёРјРµРЅРёР»Рё В«{base}В» Рё РїРѕР»СѓС‡РёР»Рё СЂРµР·СѓР»СЊС‚Р°С‚",
            ],
            "cta_variants": [
                "РќР°РїРёС€РёС‚Рµ РІ РґРёСЂРµРєС‚ вЂ” РѕС‚РїСЂР°РІРёРј С‡РµРє-Р»РёСЃС‚.",
                "РћСЃС‚Р°РІСЊС‚Рµ В«РџР›РђРќВ» РІ РєРѕРјРјРµРЅС‚Р°СЂРёСЏС… вЂ” РїСЂРёС€Р»С‘Рј С€Р°РіРё.",
                "РЎРѕС…СЂР°РЅРёС‚Рµ РїРѕСЃС‚ Рё РІРЅРµРґСЂРёС‚Рµ РїРµСЂРІС‹Р№ С€Р°Рі СЃРµРіРѕРґРЅСЏ.",
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
            "hook": f"{topic}: С‡С‚Рѕ РїСЂРѕРІРµСЂРёС‚СЊ РїРµСЂРµРґ Р·Р°РїСѓСЃРєРѕРј?",
            "angles": [
                f"РџРѕС€Р°РіРѕРІС‹Р№ СЂР°Р·Р±РѕСЂ В«{topic}В»",
                f"РўРёРїРёС‡РЅС‹Рµ РѕС€РёР±РєРё РІ В«{topic}В»",
                f"РџСЂР°РєС‚РёС‡РµСЃРєРёР№ РєРµР№СЃ РїРѕ В«{topic}В»",
            ],
            "cta_variants": [
                "РќР°РїРёС€РёС‚Рµ РІ РґРёСЂРµРєС‚, РїРѕРґР±РµСЂРµРј СЂРµС€РµРЅРёРµ РїРѕРґ Р·Р°РґР°С‡Сѓ.",
                "РћСЃС‚Р°РІСЊС‚Рµ РєРѕРјРјРµРЅС‚Р°СЂРёР№ Рё РїРѕР»СѓС‡РёС‚Рµ С€Р°Р±Р»РѕРЅ.",
                "РЎРѕС…СЂР°РЅРёС‚Рµ РїРѕСЃС‚ Рё РІРЅРµРґСЂРёС‚Рµ РїРµСЂРІС‹Р№ С€Р°Рі СЃРµРіРѕРґРЅСЏ.",
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
    if key in {"РєРѕСЂРѕС‡Рµ", "shorter"}:
        sentences = re.split(r"(?<=[.!?])\s+", value)
        return " ".join(sentences[: max(1, min(3, len(sentences)))])
    if key in {"РґР»РёРЅРЅРµРµ", "longer"}:
        return f"{value}\n\nР”РѕР±Р°РІСЊС‚Рµ РєРѕРЅРєСЂРµС‚РЅС‹Р№ РїСЂРёРјРµСЂ РІРЅРµРґСЂРµРЅРёСЏ Рё РѕР¶РёРґР°РµРјС‹Р№ СЂРµР·СѓР»СЊС‚Р°С‚ РІ С†РёС„СЂР°С…."
    if "РїСЂРѕРґР°" in key:
        return f"{value}\n\nР•СЃР»Рё С…РѕС‚РёС‚Рµ С‚Р°РєРѕР№ Р¶Рµ СЂРµР·СѓР»СЊС‚Р°С‚, РЅР°РїРёС€РёС‚Рµ РІ РґРёСЂРµРєС‚ вЂ” РїРѕРґР±РµСЂРµРј СЂРµС€РµРЅРёРµ РїРѕРґ РІР°С€Сѓ Р·Р°РґР°С‡Сѓ."
    if "СЌРєСЃРїРµСЂС‚" in key:
        return f"{value}\n\nРџСЂР°РєС‚РёС‡РµСЃРєРёР№ СЃРѕРІРµС‚: РЅР°С‡РЅРёС‚Рµ СЃ РјРёРЅРёРјР°Р»СЊРЅРѕРіРѕ С‚РµСЃС‚Р° Рё РёР·РјРµСЂСЊС‚Рµ СЂРµР·СѓР»СЊС‚Р°С‚ С‡РµСЂРµР· 7 РґРЅРµР№."
    if "СЌРјРѕС†" in key:
        return f"{value}\n\nР­С‚Рѕ РґРµР№СЃС‚РІРёС‚РµР»СЊРЅРѕ РјРѕР¶РµС‚ СЃРЅСЏС‚СЊ С…Р°РѕСЃ РІ РєРѕРЅС‚РµРЅС‚Рµ Рё РІРµСЂРЅСѓС‚СЊ СѓРІРµСЂРµРЅРЅРѕСЃС‚СЊ РІ СЂРµР·СѓР»СЊС‚Р°С‚Рµ."
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
        warnings.append("РЎС‚СЂР°С‚РµРіРёСЏ С‡Р°СЃС‚РёС‡РЅРѕ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅР° fallback-Р»РѕРіРёРєРѕР№.")
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
                warnings.append(f"{platform} v{idx}: full-schema РЅРµ РїСЂРѕС€Р»Р°, РїСЂРёРјРµРЅРµРЅ simplified fallback.")
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
                warnings.append(f"{platform} v{idx}: simplified РЅРµ РїСЂРѕС€РµР», РїСЂРёРјРµРЅРµРЅ free-text fallback.")
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
        "охват": "awareness",
        "engagement": "awareness",
        "lead": "lead",
        "leads": "lead",
        "лиды": "lead",
        "sales": "lead",
        "доверие": "trust",
        "trust": "trust",
    }
    return mapping.get(key, "awareness")


def _contains_meta_marketing_advice(text: str) -> bool:
    low = str(text or "").lower()
    return any(term in low for term in META_MARKETING_TERMS)


def _goal_playbook(goal: str) -> dict:
    normalized = _normalize_goal_for_business(goal)
    if normalized == "lead":
        return {
            "content_types": ["offer", "limited time", "booking cta", "urgency"],
            "instruction": "Focus on concrete offer, limited-time reason, booking CTA and urgency.",
        }
    if normalized == "trust":
        return {
            "content_types": ["case result", "testimonial style", "before/after"],
            "instruction": "Focus on case result, testimonial style and before/after credibility proof.",
        }
    return {
        "content_types": ["educational tip", "myth busting", "pain + solution", "list post", "trend"],
        "instruction": "Focus on educational tip, myth busting, pain+solution, list format and practical trend.",
    }


def _topic_to_client_hook(topic: str, goal: str) -> str:
    seed = _director_topic_seed(topic, max_words=4)
    normalized = _normalize_goal_for_business(goal)
    templates = {
        "awareness": [
            "Что важно знать клиенту перед визитом",
            "3 ошибки клиента и как их избежать",
            "Как получить лучший результат без лишних трат",
        ],
        "lead": [
            "Свободные окна на этой неделе: как записаться быстрее",
            "Спец-предложение для новых клиентов",
            "Почему лучше бронировать заранее",
        ],
        "trust": [
            "История клиента: было/стало за один визит",
            "Реальный кейс с понятным результатом",
            "Что говорит клиент после услуги",
        ],
    }
    base = templates.get(normalized, templates["awareness"])[0]
    # do not reuse user theme verbatim as headline
    if base.strip().lower() == str(topic or "").strip().lower():
        base = templates.get(normalized, templates["awareness"])[1]
    return f"{base} ({seed})"


def _director_topic_seed(topic: str, *, max_words: int = 5) -> str:
    text = re.sub(r"[\"'В«В»]+", " ", str(topic or ""))
    text = re.sub(r"[\n\r\t]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "РєРѕРЅС‚РµРЅС‚ РІ СЃРѕС†СЃРµС‚СЏС…"
    words: list[str] = []
    for raw in text.split(" "):
        tok = re.sub(r"[^\w\-]+", "", raw, flags=re.U).strip("-_")
        if tok:
            words.append(tok)
    stop = {
        "РґР»СЏ",
        "РєР°Рє",
        "С‡С‚Рѕ",
        "СЌС‚Рѕ",
        "Рё",
        "РІ",
        "РЅР°",
        "РїРѕ",
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
            f"Свободные окна на этой неделе: {seed}",
            f"{seed}: предложение с записью в 1 клик",
            f"Почему сейчас лучшее время записаться на {seed}",
            f"Ограниченное предложение: {offer_short or 'услуга по спец-цене'}",
            f"Что входит в услугу {seed} и как забронировать время",
            f"Быстрая запись: как получить услугу без ожидания",
            f"3 причины записаться сегодня на {seed}",
            f"{seed}: бонус для новых клиентов до конца недели",
        ]
    if normalized == "trust":
        return [
            f"История клиента: было/стало после {seed}",
            f"Реальный результат клиента за один визит",
            f"До и после: как проходит {seed} по шагам",
            f"Отзыв клиента: почему он выбрал нас",
            f"Кейс недели: аккуратная работа и понятный результат",
            f"Как мы работаем: процесс {seed} без сюрпризов",
            f"Что говорят клиенты после {seed}",
            f"Почему нам доверяют: факты и реальные примеры",
        ]
    # awareness-like playbook
    base = [
        f"3 ошибки клиента перед услугой {seed}",
        f"Миф и правда о {seed}",
        f"Проблема и решение: как выбрать {seed} без переплаты",
        f"5 практичных советов клиенту по теме {seed}",
        f"Тренд сезона в теме {seed}: что реально работает",
        f"Что важно знать перед записью на {seed}",
        f"Пошаговый чек-лист клиента: подготовка к {seed}",
        f"Частые вопросы клиентов о {seed} простыми словами",
    ]
    if offer_short:
        base[4] = f"Тренд сезона + {offer_short}: как получить пользу уже сейчас"
    return base


def _director_default_payload(
    topic: str,
    offer: str | None,
    goal: str,
    platforms: list[str],
    tone: str,
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
    offer_part = f" РћС„С„РµСЂ: {offer}." if offer else ""
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
            angle_pool.append(f"Через {angle}: что это значит для клиента на практике")
        for angle in niche_content_angles:
            angle_pool.append(f"Через {angle}: как применить это в реальной жизни")
    elif goal_mode == "lead":
        angle_pool = [
            "Через выгоду: что получает клиент уже в день обращения",
            "Через срочность: почему лучше записаться сейчас",
            "Через оффер: что входит в предложение и как забронировать",
            "Через FAQ: закрываем частые возражения перед записью",
            "Через результат: понятный итог услуги без лишних слов",
        ]
    elif goal_mode == "trust":
        angle_pool = [
            "Через кейс клиента: было/стало и детали процесса",
            "Через отзыв: реальный опыт и аргументы клиента",
            "Через прозрачный процесс: что делаем на каждом этапе",
            "Через до/после: визуальное доказательство результата",
            "Через экспертность: объясняем простыми словами и по делу",
        ]
    else:
        angle_pool = [
            "Через полезный совет: что клиент может применить сразу",
            "Через миф и факт: развеиваем частые заблуждения",
            "Через проблему и решение: как избежать типичных ошибок",
            "Через список: 3-5 конкретных рекомендаций",
            "Через тренд: что нового и как это использовать клиенту",
        ]
    if shift and angle_pool:
        angle_shift = shift % len(angle_pool)
        angle_pool = angle_pool[angle_shift:] + angle_pool[:angle_shift]
    angles = _pad_strings(
        [],
        3,
        lambda i: angle_pool[i],
    )
    cta_source = niche_cta_templates or [
        "Напишите «ХОЧУ» в директ и мы подберем удобное время.",
        "Оставьте заявку в сообщениях, ответим и забронируем слот.",
        "Сохраните пост и отправьте его другу, кому это сейчас нужно.",
    ]
    cta_options = _pad_strings([], 3, lambda i: cta_source[i % len(cta_source)])
    goal_tag_map = {
        "awareness": ["#советы", "#мифыифакты", "#полезно", "#локальныйбизнес", "#клиенты"],
        "lead": ["#запись", "#акция", "#спецпредложение", "#бронируйте", "#услуги"],
        "trust": ["#кейс", "#отзывы", "#доипосле", "#реальныйрезультат", "#доверие"],
    }
    tag_seed_source = niche_label or base
    seed_tags = [f"#{w.lower()}" for w in re.findall(r"\w+", tag_seed_source or "", flags=re.U)[:3] if len(w) > 2]
    keyword_tags = [f"#{w.lower()}" for w in niche_keywords[:4] if len(w) > 2]
    core_tags = goal_tag_map.get(goal_mode, goal_tag_map["awareness"]) + keyword_tags + ["#сервис", "#вашгород"] + seed_tags
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
            "who": niche_audience or "Люди рядом с бизнесом, которые выбирают услугу для себя или семьи",
            "pain": (niche_pain_points[0] if niche_pain_points else "Сложно выбрать исполнителя, есть страх переплаты и некачественного результата"),
            "desire": f"Получить понятную пользу, прозрачную цену и уверенность перед записью.{offer_part}",
        },
        "topics": topics,
        "angles": angles,
        "recommended": _director_recommendation(platforms, goal=goal, tone=tone),
        "cta_options": cta_options,
        "hashtag_sets": tags,
        "reason": f"Темы подобраны под нишу «{niche_label or topic}» и ориентированы на конечных клиентов.",
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
    default = _director_default_payload(topic, offer, goal, platforms, tone, niche_label=niche_label, niche_context=niche_context, variation_seed=variation_seed)
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
        t = str(item).strip()
        if not t:
            continue
        if _contains_meta_marketing_advice(t):
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
    cta_options = _pad_strings(
        _as_clean_list(payload.get("cta_options"), limit=8),
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
                if len(row_tags) < 3:
                    fallback_row = default["hashtag_sets"][idx % len(default["hashtag_sets"])]
                    for tag in fallback_row:
                        if len(row_tags) >= 3:
                            break
                        if tag not in row_tags:
                            row_tags.append(tag)
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
    lines = [x.strip("-вЂў \t") for x in str(text or "").splitlines() if x.strip()]
    topics = [x for x in lines if len(x) > 18][:10]
    angles = [x for x in lines if len(x) > 10][:3]
    return _director_soft_normalize(
        {
            "topics": topics,
            "angles": angles,
            "cta_options": lines[:3],
            "reason": "РћС‚РІРµС‚ РЅРѕСЂРјР°Р»РёР·РѕРІР°РЅ РёР· С‚РµРєСЃС‚РѕРІРѕРіРѕ fallback.",
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
    default_payload = _director_default_payload(topic, offer, goal, platforms, tone, niche_label=niche_label, niche_context=niche_context, variation_seed=variation_seed)
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
                "You are an AI Content Director for local businesses. Return JSON only. "
                "Always write from business perspective to end customers. "
                "Never provide marketing advice for marketers. "
                "Never mention: reach, engagement, content strategy, охват, вовлечение, контент-стратегия. "
                "Do not copy user topic verbatim as headlines. Keep suggestions short, practical and client-facing."
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
                "constraints: return exactly 10 topics max 96 chars, angles max 80 chars, customer-facing wording only.\n"
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

    if not is_openai_enabled():
        for platform in platforms:
            for idx in range(1, variants + 1):
                body = (
                    f"{client_hook_seed}\n\n"
                    f"{angle}\n"
                    "Покажите клиенту конкретную пользу, простой шаг и ожидаемый результат.\n"
                    "Добавьте понятные условия услуги и завершите призывом к записи."
                ).strip()
                if goal == "lead":
                    body += "\n\nТолько на этой неделе действуют специальные условия при записи."
                elif goal == "trust":
                    body += "\n\nДобавьте короткий кейс клиента в формате «было/стало»."
                else:
                    body += "\n\nРазберите миф, дайте практический совет и список из 3 пунктов."
                drafts.append(
                    {
                        "platform": platform,
                        "variant": idx,
                        "hook": client_hook_seed,
                        "body_text": body,
                        "cta": "Напишите в сообщения и мы подберем удобное время.",
                        "hashtags": ["#локальныйбизнес", "#услуги", "#вашгород"],
                        "warnings": [],
                    }
                )
        return {"status": "ok", "data": {"drafts": drafts, "strategy": {}}, "warnings": [], "debug_code": "mock"}

    for platform in platforms:
        for idx in range(1, variants + 1):
            row = None
            try:
                row, _, _ = _generate_simplified_draft(
                    topic=f"{client_hook_seed}. Ниша: {niche_label or topic}. Подход: {angle}",
                    offer=offer,
                    language=language,
                    tone=tone,
                    goal=goal,
                    platform=platform,
                    variant_index=idx,
                )
            except Exception:
                warnings.append(f"{platform} v{idx}: simplified_failed")
                debug_code = (debug_code + "|director_fast_simplified_failed").strip("|")
                try:
                    row = _generate_free_text_fallback_draft(
                        platform=platform,
                        variant_index=idx,
                        topic=f"{client_hook_seed}. Ниша: {niche_label or topic}. Подход: {angle}",
                        offer=offer,
                        goal=goal,
                    )
                except Exception:
                    row = None

            if not row:
                continue

            body_text = str(row.get("post_text") or "").strip()
            cta_text = str(row.get("cta") or "").strip() or "Напишите в сообщения и мы подберем удобное время."
            hashtags = [str(x).strip() for x in (row.get("hashtags") or []) if str(x).strip()]
            generated_tags = generateHashtags(
                niche=niche_label or topic,
                city=None,
                language=language,
                goal=goal,
            )
            if hashtags:
                hashtags = _sanitize_hashtag_list(hashtags + generated_tags, min_count=5, max_count=12)
            else:
                hashtags = generated_tags

            # Make structure explicit for quality-check in fast mode.
            has_newline = "\n" in body_text
            sentence_count = len(re.findall(r"[.!?](?:\s|$)", body_text))
            if (not has_newline and sentence_count < 3) or len(body_text) < 180:
                body_text = (
                    f"{body_text}\n\n"
                    "1) Ключевая проблема аудитории.\n"
                    "2) Практический шаг, который можно сделать сегодня.\n"
                    "3) Ожидаемый результат и следующий шаг."
                ).strip()
            if _contains_meta_marketing_advice(body_text):
                body_text = (
                    f"{client_hook_seed}\n\n"
                    "Сфокусируйтесь на клиентской выгоде: что человек получит после услуги, "
                    "как проходит процесс и почему результат предсказуем."
                )
            if _contains_meta_marketing_advice(cta_text):
                cta_text = "Напишите в сообщения и получите персональную рекомендацию."

            # Keep hashtag ranges closer to platform best-practice.
            if platform == "instagram":
                base_pool = hashtags + generated_tags
                uniq = []
                seen = set()
                for t in base_pool:
                    key = t.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append(t if t.startswith("#") else f"#{t}")
                hashtags = uniq[:15]
                while len(hashtags) < 8:
                    hashtags.append(f"#сервис{len(hashtags)+1}")
            elif platform == "facebook":
                hashtags = hashtags[:8]
                if not hashtags:
                    hashtags = generated_tags[:8]
            elif platform == "youtube":
                hashtags = hashtags[:10]
                if len(hashtags) < 3:
                    hashtags = _sanitize_hashtag_list(hashtags + generated_tags, min_count=3, max_count=10)[:3]

            drafts.append(
                {
                    "platform": str(row.get("platform") or platform).strip().lower(),
                    "variant": int(row.get("variant_index") or idx),
                    "hook": client_hook_seed[:180],
                    "body_text": body_text,
                    "cta": cta_text,
                    "hashtags": hashtags,
                    "warnings": [],
                }
            )

    if not drafts:
        drafts = [
            {
                "platform": platforms[0],
                "variant": 1,
                "hook": client_hook_seed,
                "body_text": (
                    f"{client_hook_seed}\n\n"
                    f"{angle}\n\n"
                    "Покажите клиенту конкретную пользу услуги, добавьте понятные условия и завершите записью."
                ),
                "cta": "Напишите в сообщения и получите свободные слоты на ближайшие дни.",
                "hashtags": ["#локальныйбизнес", "#услуги", "#вашгород"],
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

