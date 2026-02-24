import json
from dataclasses import dataclass

from openai_client import OpenAIClientError, generate_json_with_retry, is_openai_enabled


@dataclass
class ScriptBundle:
    phrases: list[str]
    shotlist: list[dict]
    title: str
    description: str
    hashtags: list[str]
    safety_rules: list[str]


def _normalize_phrases(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split("\n") if x.strip()]
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
    return out[:120]


def _normalize_shotlist(raw, phrase_count: int) -> list[dict]:
    if not isinstance(raw, list):
        raw = []
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
        out.append(
            {
                "phrase_index": max(0, min(max(phrase_count - 1, 0), phrase_index)),
                "queries": clean_queries[:2] or ["business teamwork", "city office"],
                "mood": str(item.get("mood") or "calm").strip().lower()[:20],
                "scene_type": str(item.get("scene_type") or "work").strip().lower()[:30],
            }
        )
    return out


def _validator(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload must be object")
    phrases = _normalize_phrases(payload.get("phrases"))
    if not phrases:
        raise ValueError("phrases required")


def _fallback(topic: str, offer: str | None, language: str, target_seconds: int) -> ScriptBundle:
    lines = [
        f"Сегодня разберем тему: {topic}.",
        "Покажу, как подойти к задаче пошагово и без лишней теории.",
        "Разделим процесс на простые действия, которые можно сделать уже сегодня.",
        "Добавим пример из практики, чтобы было понятно, как это работает.",
        "В конце подведем итог и зафиксируем следующий шаг.",
    ]
    if offer:
        lines.insert(3, f"Аккуратно встроим оффер: {offer}, без навязчивых продаж.")
    shotlist = []
    for i in range(len(lines)):
        shotlist.append(
            {
                "phrase_index": i,
                "queries": ["real people work", "city office teamwork"] if i % 2 == 0 else ["closeup hands laptop", "business planning board"],
                "mood": "calm",
                "scene_type": "work",
            }
        )
    return ScriptBundle(
        phrases=lines,
        shotlist=shotlist,
        title=f"{topic}: практический разбор"[:70],
        description=f"Разбор темы {topic}. Конкретные шаги и примеры. Язык: {language}.",
        hashtags=["#бизнес", "#контент", "#маркетинг"],
        safety_rules=[
            "only realistic scenes",
            "no fantasy creatures",
            "no cartoon or CGI looking footage",
            "avoid ai generated or synthetic visuals",
        ],
    )


def generate(topic: str, offer: str | None, language: str, target_seconds: int, style: str) -> ScriptBundle:
    topic = str(topic or "").strip()
    if not topic:
        raise ValueError("topic is required")
    target_seconds = max(20, min(480, int(target_seconds or 30)))
    if not is_openai_enabled():
        return _fallback(topic, offer, language, target_seconds)

    system_prompt = (
        "Ты senior видео-копирайтер и режиссер монтажа. "
        "Верни только JSON. Реалистичный контент: без фантастики, мультяшности, CGI, AI-арта."
    )
    user_prompt = (
        "Сформируй сценарий и шот-лист для видео.\n"
        f"topic: {topic}\n"
        f"offer: {offer or ''}\n"
        f"language: {language}\n"
        f"target_seconds: {target_seconds}\n"
        f"style: {style}\n"
        "schema:\n"
        "{\n"
        ' "phrases": ["..."],\n'
        ' "shotlist": [{"phrase_index":0,"queries":["...","..."],"mood":"calm|dynamic","scene_type":"work|city|people|nature"}],\n'
        ' "title":"...",\n'
        ' "description":"...",\n'
        ' "hashtags":["#..."],\n'
        ' "safety_rules":["..."]\n'
        "}\n"
        "Фразы краткие, живые, для озвучки."
    )
    try:
        result = generate_json_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            validator=_validator,
            max_output_tokens=1800,
            temperature=0.6,
        )
        payload = result.payload
    except OpenAIClientError:
        return _fallback(topic, offer, language, target_seconds)

    phrases = _normalize_phrases(payload.get("phrases"))
    if not phrases:
        return _fallback(topic, offer, language, target_seconds)
    shotlist = _normalize_shotlist(payload.get("shotlist"), len(phrases))
    if not shotlist:
        shotlist = _fallback(topic, offer, language, target_seconds).shotlist[: len(phrases)]
    hashtags = payload.get("hashtags")
    if not isinstance(hashtags, list):
        hashtags = []
    tags = [str(x).strip() for x in hashtags if str(x).strip()][:20]
    if not tags:
        tags = ["#контент", "#маркетинг", "#бизнес"]
    safety = payload.get("safety_rules")
    if not isinstance(safety, list):
        safety = []
    safety_rules = [str(x).strip() for x in safety if str(x).strip()]
    if not safety_rules:
        safety_rules = _fallback(topic, offer, language, target_seconds).safety_rules
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
