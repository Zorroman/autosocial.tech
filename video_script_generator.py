import json
import re
from dataclasses import dataclass

from footage.shots import DEFAULT_SCENE_QUERIES
from openai_client import OpenAIClientError, generate_json_with_retry, is_openai_enabled
from style_packs import normalize_scene


@dataclass
class ScriptBundle:
    phrases: list[str]
    shotlist: list[dict]
    title: str
    description: str
    hashtags: list[str]
    safety_rules: list[str]


_BAD_FRAGMENTS = (
    "покажем один",
    "добавим конкретику",
    "фиксируем ожидаемый эффект",
    "плавно подводим",
    "кратко покажем",
    "обозначьте",
    "уточните",
    "завершите",
)


def _normalize_phrases(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split("\n") if x.strip()]
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = " ".join(str(item or "").split()).strip()
        if text:
            out.append(text)
    return out[:120]


def _estimate_seconds_from_phrases(phrases: list[str]) -> float:
    total_chars = sum(len(str(x or "").strip()) for x in (phrases or []))
    # Средняя скорость живой речи ~13-15 символов/сек с паузами.
    return max(0.0, total_chars / 14.0)


def _sanitize_phrase(text: str, topic: str) -> str:
    s = " ".join(str(text or "").split()).strip()
    s = s.replace("□", "").replace("�", "").strip()
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\.\s*\.", ".", s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    if not s:
        s = f"Разбираем тему: {topic}."
    low = s.lower()
    if any(frag in low for frag in _BAD_FRAGMENTS):
        return ""
    if len(s) < 20:
        return ""
    if s[-1] not in ".!?":
        s = f"{s}."
    return s[:220]


def _topic_fillers(topic: str, offer: str | None) -> list[str]:
    pool = [
        f"{topic}: начнем с простой практики, которую можно применить уже сегодня.",
        f"Покажем, как тема «{topic}» помогает получить понятный результат без перегруза.",
        "Разберем типичную ошибку новичков и сразу дадим рабочую альтернативу.",
        "Добавим короткий пример из жизни, чтобы идея была понятна даже без подготовки.",
        "Соберем мини-план действий на ближайшие 24 часа и зафиксируем ожидаемый эффект.",
        "В финале оставим четкий следующий шаг, который легко проверить на практике.",
    ]
    if offer:
        pool.insert(
            2,
            f"Аккуратно встроим оффер «{offer}» в контекст пользы, без навязчивых продаж.",
        )
    return pool


def _dedupe_keep_order(lines: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = re.sub(r"[^a-zA-Zа-яА-Я0-9]+", "", line.lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def _ensure_target_duration_phrases(phrases: list[str], topic: str, target_seconds: int, offer: str | None) -> list[str]:
    cleaned = [_sanitize_phrase(x, topic) for x in (phrases or [])]
    out = _dedupe_keep_order([x for x in cleaned if x])

    if not out:
        out = [f"Разбираем тему: {topic}.", f"Переходим к практическим шагам по теме «{topic}»."]

    target_seconds = max(20, min(480, int(target_seconds or 30)))
    desired_scenes = max(4, int(round(float(target_seconds) / 4.0)))
    if target_seconds <= 30:
        desired_scenes = max(4, min(desired_scenes, 6))
    elif target_seconds <= 40:
        desired_scenes = max(5, min(desired_scenes, 8))
    fillers = _topic_fillers(topic, offer)
    cursor = 0
    while len(out) < desired_scenes:
        out.append(fillers[cursor % len(fillers)])
        cursor += 1
        out = _dedupe_keep_order(out)
        if cursor > 24:
            break

    # Добиваем длительность, но не раздуваем бесконечно.
    loop_guard = 0
    fill_target_ratio = 0.92
    if target_seconds <= 30:
        fill_target_ratio = 0.78
    elif target_seconds <= 40:
        fill_target_ratio = 0.84
    while _estimate_seconds_from_phrases(out) < float(target_seconds) * fill_target_ratio and loop_guard < 24:
        out.append(fillers[(cursor + loop_guard) % len(fillers)])
        out = _dedupe_keep_order(out)
        loop_guard += 1

    return out[:120]


def _normalize_shotlist(raw, phrase_count: int, style_pack: dict) -> list[dict]:
    if not isinstance(raw, list):
        raw = []
    allowed_scenes = list(style_pack.get("allowed_scenes") or [])
    default_mood = str(style_pack.get("mood") or "neutral").strip().lower()
    out = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        phrase_index = int(item.get("phrase_index") if str(item.get("phrase_index", "")).isdigit() else idx)
        queries = item.get("queries")
        if isinstance(queries, str):
            queries = [x.strip() for x in queries.split(",") if x.strip()]
        if not isinstance(queries, list):
            queries = []
        clean_queries = [str(x).strip() for x in queries if str(x).strip()][:4]
        scene = normalize_scene(str(item.get("scene_type") or "work"), allowed_scenes)
        mood = str(item.get("mood") or default_mood or "neutral").strip().lower()
        if mood not in {"calm", "neutral", "dynamic"}:
            mood = default_mood if default_mood in {"calm", "neutral", "dynamic"} else "neutral"
        out.append(
            {
                "phrase_index": max(0, min(max(phrase_count - 1, 0), phrase_index)),
                "queries": clean_queries[:2] or [DEFAULT_SCENE_QUERIES.get(scene, "real life"), "real life scene"],
                "mood": mood,
                "scene_type": scene,
            }
        )
    return out


def _validator(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload must be object")
    phrases = _normalize_phrases(payload.get("phrases"))
    if not phrases:
        raise ValueError("phrases required")


def _fallback(topic: str, offer: str | None, language: str, target_seconds: int, style_pack: dict) -> ScriptBundle:
    lines = [
        f"Сегодня коротко и понятно разбираем тему «{topic}».",
        "Начнем с базового принципа и сразу переведем его в практическое действие.",
        "Покажем пример из реальной ситуации, чтобы было ясно, как это работает.",
        "Отметим частую ошибку и дадим простой способ ее избежать.",
        "Закрепим итог и обозначим следующий шаг для зрителя.",
    ]
    if offer:
        lines.insert(3, f"Встроим оффер «{offer}» аккуратно и по делу, без агрессивной рекламы.")
    lines = _ensure_target_duration_phrases(lines, topic, target_seconds, offer)

    allowed_scenes = list(style_pack.get("allowed_scenes") or [])
    primary_scene = normalize_scene("work", allowed_scenes)
    alt_scene = normalize_scene("nature", allowed_scenes)
    shotlist = []
    for i in range(len(lines)):
        scene = primary_scene if i % 2 == 0 else alt_scene
        shotlist.append(
            {
                "phrase_index": i,
                "queries": [DEFAULT_SCENE_QUERIES.get(scene, "real life"), "real life scene"],
                "mood": str(style_pack.get("mood") or "neutral"),
                "scene_type": scene,
            }
        )

    return ScriptBundle(
        phrases=lines,
        shotlist=shotlist,
        title=f"{topic}: практический разбор"[:70],
        description=f"Разбор темы «{topic}» с конкретными шагами и примерами. Язык: {language}.",
        hashtags=["#контент", "#маркетинг", "#smm"],
        safety_rules=[
            "only realistic scenes",
            "no fantasy creatures",
            "no cartoon or CGI looking footage",
            "avoid ai generated or synthetic visuals",
        ],
    )


def generate(
    topic: str,
    offer: str | None,
    language: str,
    target_seconds: int,
    style: str,
    style_pack: dict | None = None,
) -> ScriptBundle:
    topic = str(topic or "").strip()
    if not topic:
        raise ValueError("topic is required")
    target_seconds = max(20, min(480, int(target_seconds or 30)))
    style_pack = style_pack or {}
    if not is_openai_enabled():
        return _fallback(topic, offer, language, target_seconds, style_pack)

    allowed_scenes = list(style_pack.get("allowed_scenes") or [])
    query_bias = list(style_pack.get("query_bias") or [])
    banned_tokens = list(style_pack.get("banned_tokens") or [])
    mood = str(style_pack.get("mood") or "neutral")
    motion_level = str(style_pack.get("motion_level") or "medium")

    system_prompt = (
        "Ты senior video copywriter и режиссёр монтажа. "
        "Верни только валидный JSON по схеме. "
        "Пиши естественным живым языком, как человек. "
        "Никаких обрывков, техно-фраз и повторов."
    )
    user_prompt = (
        "Сформируй сценарный план и shotlist для короткого ролика.\n"
        f"topic: {topic}\n"
        f"offer: {offer or ''}\n"
        f"language: {language}\n"
        f"target_seconds: {target_seconds}\n"
        f"style: {style}\n"
        f"style_pack_id: {style_pack.get('id') or 'default_pro'}\n"
        f"allowed_scenes: {json.dumps(allowed_scenes, ensure_ascii=False)}\n"
        f"query_bias: {json.dumps(query_bias, ensure_ascii=False)}\n"
        f"banned_tokens: {json.dumps(banned_tokens, ensure_ascii=False)}\n"
        f"preferred_mood: {mood}\n"
        f"motion_level: {motion_level}\n"
        "Требования к phrases:\n"
        "- каждая фраза это законченное предложение 8-16 слов;\n"
        "- не используй императивные заготовки вида «покажем один», «добавим конкретику»;\n"
        "- фразы должны быть уникальны и логично развивать мысль;\n"
        "- никакой фантастики или AI-арта.\n"
        "JSON schema:\n"
        "{\n"
        ' "phrases": ["..."],\n'
        ' "shotlist": [{"phrase_index":0,"queries":["...","..."],"mood":"calm|dynamic|neutral","scene_type":"work|city|people|nature|home|product|abstract_real"}],\n'
        ' "title":"...",\n'
        ' "description":"...",\n'
        ' "hashtags":["#..."],\n'
        ' "safety_rules":["..."]\n'
        "}\n"
        "scene_type выбирай только из allowed_scenes."
    )

    try:
        result = generate_json_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            validator=_validator,
            max_output_tokens=1800,
            temperature=0.55,
        )
        payload = result.payload
    except OpenAIClientError:
        return _fallback(topic, offer, language, target_seconds, style_pack)

    phrases = _normalize_phrases(payload.get("phrases"))
    phrases = _ensure_target_duration_phrases(phrases, topic, target_seconds, offer)
    if not phrases:
        return _fallback(topic, offer, language, target_seconds, style_pack)

    shotlist = _normalize_shotlist(payload.get("shotlist"), len(phrases), style_pack)
    if not shotlist:
        shotlist = _fallback(topic, offer, language, target_seconds, style_pack).shotlist[: len(phrases)]

    hashtags = payload.get("hashtags")
    if not isinstance(hashtags, list):
        hashtags = []
    tags = [str(x).strip() for x in hashtags if str(x).strip()][:20]
    if not tags:
        tags = ["#контент", "#маркетинг", "#smm"]

    safety = payload.get("safety_rules")
    if not isinstance(safety, list):
        safety = []
    safety_rules = [str(x).strip() for x in safety if str(x).strip()]
    if not safety_rules:
        safety_rules = _fallback(topic, offer, language, target_seconds, style_pack).safety_rules

    return ScriptBundle(
        phrases=phrases,
        shotlist=shotlist,
        title=str(payload.get("title") or f"{topic}: практический разбор")[:70],
        description=str(payload.get("description") or f"Видео по теме: {topic}")[:5000],
        hashtags=tags,
        safety_rules=safety_rules,
    )


def to_json(bundle: ScriptBundle) -> str:
    return json.dumps(
        {
            "phrases": bundle.phrases,
            "shotlist": bundle.shotlist,
            "title": bundle.title,
            "description": bundle.description,
            "hashtags": bundle.hashtags,
            "safety_rules": bundle.safety_rules,
        },
        ensure_ascii=False,
    )
