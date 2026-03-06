from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NicheSpec:
    slug: str
    title: str
    description: str
    icon: str
    sort_order: int
    scene: str
    audience_hint: str
    trust_point: str


VARIABLES_SCHEMA: dict[str, Any] = {
    "business_name": {"type": "string", "required": True, "description": "Local business name"},
    "city": {"type": "string", "required": True, "description": "City or district"},
    "offer": {"type": "string", "required": True, "description": "Current offer or service"},
    "usp": {"type": "string", "required": True, "description": "Unique selling point"},
    "price": {"type": "string", "required": True, "description": "Price or price range"},
    "audience": {"type": "string", "required": True, "description": "Target local audience"},
    "cta": {"type": "string", "required": True, "description": "Primary call to action"},
    "contact": {"type": "string", "required": True, "description": "Phone, WhatsApp or DM"},
    "website": {"type": "string", "required": True, "description": "Booking URL or website"},
}


NICHE_SPECS: list[NicheSpec] = [
    NicheSpec(
        slug="barbershop",
        title="Barbershop",
        description="Offline lead generation for neighborhood barber shops and premium grooming services.",
        icon="scissors",
        sort_order=10,
        scene="barber chair, haircut details, beard shaping",
        audience_hint="men 18-45 living within 5 km",
        trust_point="clean tools and precise fades",
    ),
    NicheSpec(
        slug="beauty-salon",
        title="Beauty Salon",
        description="Local promotion templates for beauty salons focused on repeat visits and upsells.",
        icon="sparkles",
        sort_order=20,
        scene="salon room, skin treatment, manicure close-up",
        audience_hint="women 20-50 near city center",
        trust_point="certified specialists and hygiene standards",
    ),
    NicheSpec(
        slug="auto-service",
        title="Auto Service",
        description="High-conversion local content for workshops and diagnostics with urgent offline bookings.",
        icon="wrench",
        sort_order=30,
        scene="car lift, mechanic at work, diagnostics tablet",
        audience_hint="car owners commuting daily",
        trust_point="transparent estimate and warranty on work",
    ),
    NicheSpec(
        slug="tire-service",
        title="Tire Service",
        description="Seasonal and urgent tire service marketing templates for local calls and bookings.",
        icon="circle-dot",
        sort_order=40,
        scene="wheel balancing, tire change, tread check",
        audience_hint="drivers before season change",
        trust_point="fast turnaround and no hidden fees",
    ),
    NicheSpec(
        slug="tattoo-studio",
        title="Tattoo Studio",
        description="Studio-focused local templates to fill booking slots with qualified walk-ins.",
        icon="pen-tool",
        sort_order=50,
        scene="tattoo sketch, sterile setup, artist process",
        audience_hint="young adults seeking custom designs",
        trust_point="sterile process and custom concept",
    ),
    NicheSpec(
        slug="fitness-trainer",
        title="Fitness Trainer",
        description="Local trainer content for trial sessions, referrals and recurring memberships.",
        icon="dumbbell",
        sort_order=60,
        scene="training session, exercise correction, before-after board",
        audience_hint="busy adults wanting measurable results",
        trust_point="structured program and weekly check-ins",
    ),
    NicheSpec(
        slug="restaurant",
        title="Restaurant",
        description="Offline-first restaurant templates optimized for table bookings and walk-in traffic.",
        icon="utensils",
        sort_order=70,
        scene="kitchen pass, plated dishes, evening atmosphere",
        audience_hint="families and office crowd nearby",
        trust_point="fresh ingredients and signature dishes",
    ),
    NicheSpec(
        slug="cafe",
        title="Cafe",
        description="Local cafe templates to increase breakfast and lunch footfall.",
        icon="coffee",
        sort_order=80,
        scene="barista process, latte art, cozy interior",
        audience_hint="students and remote workers nearby",
        trust_point="specialty beans and warm service",
    ),
    NicheSpec(
        slug="child-education",
        title="Child Education Center",
        description="Parent-oriented local marketing templates for enrollments and trial classes.",
        icon="graduation-cap",
        sort_order=90,
        scene="classroom activities, teacher guidance, learning materials",
        audience_hint="parents of children 4-14",
        trust_point="small groups and measurable progress",
    ),
    NicheSpec(
        slug="car-wash",
        title="Car Wash",
        description="Fast-conversion neighborhood content for car wash packages and memberships.",
        icon="droplets",
        sort_order=100,
        scene="foam wash, detailing process, shiny final result",
        audience_hint="drivers who value speed and clean finish",
        trust_point="safe chemicals and quality control",
    ),
]


def _system_prompt(niche: NicheSpec, content_type: str) -> str:
    video_part = (
        "Output must fit 15-40 sec short video script with clear beat-by-beat structure."
        if content_type == "video"
        else "Output must be a practical local post optimized for offline conversion."
    )
    return (
        "You are a senior local performance marketer for German small businesses. "
        "Write realistic, practical, no-hype content for offline sales. "
        "Do not add fantasy, unrealistic promises or invented facts. "
        f"Business vertical: {niche.title}. "
        f"Preferred scenes: {niche.scene}. "
        f"Audience baseline: {niche.audience_hint}. "
        f"Trust signal to reinforce: {niche.trust_point}. "
        f"{video_part}"
    )


def _post_user_prompt(niche: NicheSpec, mode: str) -> tuple[str, str, str, str, str, str]:
    if mode == "promo":
        return (
            "promo-offer-post",
            "Promo Offer: local conversion",
            "Limited slots this week in {{city}}: {{offer}} at {{price}}.",
            "Book now via {{contact}} or {{website}}.",
            "leads",
            "local-friendly",
        )
    if mode == "proof":
        return (
            "social-proof-post",
            "Social Proof: client result",
            "Real local result from {{city}}: what changed after {{offer}}.",
            "Message {{contact}} to get the same plan for your case.",
            "awareness",
            "expert",
        )
    return (
        "education-myth-post",
        "Educational Tip: myth vs reality",
        "Most people in {{city}} believe this myth about {{offer}}.",
        "Send '{{cta}}' to {{contact}} and get a practical checklist.",
        "awareness",
        "expert",
    )


def _video_user_prompt(niche: NicheSpec, mode: str) -> tuple[str, str, str, str, str, str]:
    if mode == "tips":
        return (
            "hook-3-tips-video",
            "Video: Hook + 3 tips",
            "Stop wasting money on the wrong {{offer}} in {{city}}.",
            "Save this and contact {{contact}} for a local recommendation.",
            "awareness",
            "expert",
        )
    if mode == "bts":
        return (
            "behind-scenes-video",
            "Video: Behind the scenes process",
            "What happens from first minute to final result at {{business_name}}.",
            "Book your slot at {{website}} or DM {{contact}}.",
            "awareness",
            "local-friendly",
        )
    return (
        "faq-objection-video",
        "Video: FAQ and objections",
        "Top objection we hear in {{city}}: 'Is {{offer}} worth {{price}}?'",
        "Ask your question at {{contact}} and get a clear quote today.",
        "leads",
        "expert",
    )


def _build_prompt_user(niche: NicheSpec, hook: str, cta: str, content_type: str, frame: str) -> str:
    if content_type == "post":
        return (
            f"Create one high-conversion local post for {niche.title} in Germany.\n"
            f"Frame: {frame}.\n"
            f"Hook line must be: {hook}\n"
            "Use variables naturally: {{business_name}}, {{city}}, {{offer}}, {{usp}}, {{price}}, "
            "{{audience}}, {{cta}}, {{contact}}, {{website}}.\n"
            "Structure:\n"
            "1) Hook\n2) Local relevance\n3) Practical value\n4) Social proof element\n5) Clear CTA\n"
            f"Final CTA must include: {cta}\n"
            "Language style: simple and practical, German local business tone."
        )
    return (
        f"Create a 15-40 sec short video script for {niche.title}.\n"
        f"Frame: {frame}.\n"
        f"Hook line must be: {hook}\n"
        "Use variables naturally: {{business_name}}, {{city}}, {{offer}}, {{usp}}, {{price}}, "
        "{{audience}}, {{cta}}, {{contact}}, {{website}}.\n"
        "Output format:\n"
        "- Hook (0-3 sec)\n"
        "- Main body (3 beats)\n"
        "- CTA ending\n"
        "Keep visuals realistic and local. Avoid fantasy and abstract claims.\n"
        f"Final CTA must include: {cta}\n"
        "Language style: practical, confidence-building, easy to read aloud."
    )


def build_niche_catalog_seed() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for niche in NICHE_SPECS:
        templates: list[dict[str, Any]] = []

        post_modes = [("promo", 10), ("proof", 20), ("education", 30)]
        video_modes = [("tips", 40), ("bts", 50), ("faq", 60)]

        for mode, sort_order in post_modes:
            slug, title, hook, cta, goal, tone = _post_user_prompt(niche, mode)
            preview = (
                f"{hook} {niche.title} {niche.slug} by {{business_name}}. "
                f"USP: {{usp}}. CTA: {cta}"
            )
            templates.append(
                {
                    "slug": slug,
                    "title": title,
                    "description": f"Post template for {niche.title}: {mode}.",
                    "type": "post",
                    "platform": "all",
                    "goal": goal,
                    "tone": tone,
                    "hook_line": hook,
                    "cta": cta,
                    "prompt_system": _system_prompt(niche, "post"),
                    "prompt_user": _build_prompt_user(niche, hook, cta, "post", title),
                    "variables_schema_json": VARIABLES_SCHEMA,
                    "preview_text": preview,
                    "sort_order": sort_order,
                }
            )

        for mode, sort_order in video_modes:
            slug, title, hook, cta, goal, tone = _video_user_prompt(niche, mode)
            preview = (
                f"{hook} 3 beats, realistic local scene in {{city}}. "
                f"End with: {cta}"
            )
            templates.append(
                {
                    "slug": slug,
                    "title": title,
                    "description": f"Short video template for {niche.title}: {mode}.",
                    "type": "video",
                    "platform": "all",
                    "goal": goal,
                    "tone": tone,
                    "hook_line": hook,
                    "cta": cta,
                    "prompt_system": _system_prompt(niche, "video"),
                    "prompt_user": _build_prompt_user(niche, hook, cta, "video", title),
                    "variables_schema_json": VARIABLES_SCHEMA,
                    "preview_text": preview,
                    "sort_order": sort_order,
                }
            )

        out.append(
            {
                "slug": niche.slug,
                "title": niche.title,
                "description": niche.description,
                "icon": niche.icon,
                "sort_order": niche.sort_order,
                "templates": templates,
            }
        )
    return out

