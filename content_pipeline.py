import json
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


def _ensure_list_of_strings(value: Any, field: str, min_len: int = 1) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    items = [str(x).strip() for x in value if str(x).strip()]
    if len(items) < min_len:
        raise ValueError(f"{field} must contain at least {min_len} items")
    return items


def validate_strategy_payload(payload: dict) -> None:
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

    if not is_openai_enabled():
        strategy = _mock_strategy(topic=topic, offer=offer, goal=goal)
        drafts = []
        for platform in platforms:
            for idx in range(1, variants + 1):
                draft = _mock_draft(platform=platform, variant_index=idx, topic=topic, strategy=strategy)
                validate_draft_payload(draft)
                drafts.append(draft)
        return ContentGenerationResult(strategy=strategy, drafts=drafts, token_input=0, token_output=0)

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

    drafts: list[dict] = []
    total_in = strategy_res.input_tokens
    total_out = strategy_res.output_tokens
    for platform in platforms:
        for idx in range(1, variants + 1):
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
            drafts.append(draft_res.payload)

    return ContentGenerationResult(strategy=strategy, drafts=drafts, token_input=total_in, token_output=total_out)


__all__ = [
    "ContentGenerationResult",
    "OpenAIClientError",
    "generate_strategy_and_drafts",
    "validate_strategy_payload",
    "validate_draft_payload",
    "STRATEGY_SCHEMA",
    "DRAFT_SCHEMA",
]
