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


# Calibrated against real OpenAI-TTS renders (project 5: 449 chars → 35.1s ≈
# 12.8 chars/s incl. per-scene padding). Using the measured rate makes the
# estimate track actual rendered duration so the 27–33s publish gate is hit.
_TTS_CHARS_PER_SEC = 12.5


def _estimate_seconds_from_phrases(phrases: list[str]) -> float:
    total_chars = sum(len(str(x or "").strip()) for x in (phrases or []))
    return max(0.0, total_chars / _TTS_CHARS_PER_SEC)


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

    target_seconds = max(20, min(1800, int(target_seconds or 30)))
    fillers = _topic_fillers(topic, offer)

    # Duration is the hard constraint (the 27–33s publish gate for a 30s target),
    # so shape by TIME, not a fixed scene count. Keep a sane minimum of scenes,
    # then pad up to / trim down to the target band. Scene count emerges from the
    # phrase lengths, which lands ~6–8 short scenes for a 30s Short.
    min_scenes = 4
    cursor = 0
    while len(out) < min_scenes:
        out.append(fillers[cursor % len(fillers)])
        cursor += 1
        out = _dedupe_keep_order(out)
        if cursor > 24:
            break

    # Pad up toward the target when the script is too short.
    fill_target_ratio = 0.90 if target_seconds <= 40 else 0.92
    loop_guard = 0
    while _estimate_seconds_from_phrases(out) < float(target_seconds) * fill_target_ratio and loop_guard < 24:
        out.append(fillers[(cursor + loop_guard) % len(fillers)])
        out = _dedupe_keep_order(out)
        loop_guard += 1

    # Trim down when the script overshoots (renders too long → gate rejects it).
    # Never cut the hook (first) or the closing CTA (last); drop the longest
    # middle phrase until inside the band.
    ceiling = float(target_seconds) + 1.0
    guard = 0
    while (len(out) > min_scenes
           and _estimate_seconds_from_phrases(out) > ceiling and guard < 24):
        middle = out[1:-1]
        if not middle:
            break
        longest = max(range(len(middle)), key=lambda i: len(middle[i]))
        del out[1 + longest]
        guard += 1

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


def _generate_longform(topic, offer, language, target_seconds, style, style_pack) -> ScriptBundle:
    """Calm long-form narration (12–20 min). Generated in chunks — an outline of
    distinct sections, then each section expanded — so a 15-minute script stays
    coherent and varied instead of being padded with repetitive filler."""
    from openai_client import generate_json_with_retry

    # More sections + over-ask words: gpt-4o-mini under-delivers ~30%, so we ask
    # for more than the naive target and top up until the estimate hits target.
    n_sections = max(8, min(22, round(target_seconds / 55)))
    words_per_section = max(110, round(target_seconds * 2.9 / n_sections))

    sys1 = ("Ты — сценарист спокойного глубокого закадрового повествования для "
            "длинного медитативного видео. Верни только валидный JSON.")
    usr1 = (f"Тема видео: {topic}\nЯзык: {language}\n"
            f"Составь план из {n_sections} последовательных смысловых частей — каждая "
            "раскрывает отдельную грань темы (учение, идея, притча, практика, "
            "размышление), логично развивая повествование, без повторов.\n"
            'JSON: {"title":"...","description":"...","hashtags":["#..."],'
            '"sections":["краткая тема части 1","краткая тема части 2"]}')

    def _v1(p):
        if not isinstance(p.get("sections"), list) or len(p["sections"]) < 3:
            raise ValueError("sections required")

    out = generate_json_with_retry(system_prompt=sys1, user_prompt=usr1, validator=_v1,
                                   max_output_tokens=1100, temperature=0.7).payload
    sections = [str(s).strip() for s in (out.get("sections") or []) if str(s).strip()][:n_sections]

    phrases: list[str] = []
    sys2 = ("Ты пишешь спокойный естественный закадровый текст для медитативного "
            "видео. Живой человеческий язык, без клише, списков и повторов. "
            "Верни только валидный JSON.")

    def _v2(p):
        if not isinstance(p.get("sentences"), list) or not p["sentences"]:
            raise ValueError("sentences required")

    def _expand(sec: str, i: int, n: int) -> None:
        usr2 = (f"Тема видео: {topic}\nЯзык: {language}\n"
                f"Часть {i + 1} из {n}: {sec}\n"
                f"Напиши примерно {words_per_section} слов связного повествования по этой "
                "части — несколько законченных предложений, спокойный созерцательный тон. "
                "Не повторяй уже сказанное, без вступлений вроде «в этой части».\n"
                'JSON: {"sentences":["предложение","предложение"]}')
        try:
            sp = generate_json_with_retry(system_prompt=sys2, user_prompt=usr2, validator=_v2,
                                          max_output_tokens=900, temperature=0.75).payload
            for s in (sp.get("sentences") or []):
                s = _sanitize_phrase(s, topic)
                if s:
                    phrases.append(s)
        except Exception:
            pass

    for i, sec in enumerate(sections):
        _expand(sec, i, len(sections))

    # Top-up: keep adding fresh distinct sections until we reach ~target duration.
    guard = 0
    while (_estimate_seconds_from_phrases(_dedupe_keep_order(phrases)) < target_seconds * 0.9
           and guard < 10):
        guard += 1
        try:
            covered = "; ".join(sections[-12:])
            usr3 = (f"Тема видео: {topic}\nЯзык: {language}\n"
                    f"Уже раскрыты части: {covered}\n"
                    "Предложи ОДНУ новую, ещё не раскрытую смысловую часть по теме "
                    "(другой аспект/притча/практика/пример), не повторяющую предыдущие.\n"
                    'JSON: {"section":"краткая тема"}')
            def _v3(p):
                if not str(p.get("section") or "").strip():
                    raise ValueError("section required")
            ns = generate_json_with_retry(
                system_prompt=sys1, user_prompt=usr3, validator=_v3, max_output_tokens=200,
                temperature=0.8).payload.get("section", "").strip()
        except Exception:
            ns = ""
        if not ns:
            break
        sections.append(ns)
        _expand(ns, len(sections) - 1, len(sections))

    phrases = _dedupe_keep_order(phrases)
    if len(phrases) < 8:
        raise RuntimeError("longform_too_short")
    shotlist = [{"phrase_index": i, "queries": [], "mood": "calm", "scene_type": "nature"}
                for i in range(len(phrases))]
    return ScriptBundle(
        phrases=phrases, shotlist=shotlist,
        title=str(out.get("title") or topic)[:100],
        description=str(out.get("description") or topic),
        hashtags=[str(h) for h in (out.get("hashtags") or []) if str(h).strip()][:8],
        safety_rules=["only realistic calm footage", "no cgi", "no fantasy creatures"],
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
    target_seconds = max(20, min(1800, int(target_seconds or 30)))
    style_pack = style_pack or {}
    if not is_openai_enabled():
        return _fallback(topic, offer, language, target_seconds, style_pack)

    # Long-form (calm narration, e.g. 12–20 min): different generation path.
    if target_seconds >= 150:
        try:
            return _generate_longform(topic, offer, language, target_seconds, style, style_pack)
        except Exception:
            pass  # fall through to the standard path on any failure

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
        f"ЖЁСТКИЙ бюджет длительности: вся озвучка вместе ~{int(round(target_seconds * 2.0))} слов "
        f"(~{int(round(target_seconds * _TTS_CHARS_PER_SEC))} символов) — это {target_seconds}s при текущем TTS. Не превышай.\n"
        f"Сделай {max(6, min(8, int(round(target_seconds / 4.0))))}–{max(6, min(9, int(round(target_seconds / 4.0)) + 1))} коротких сцен.\n"
        "Требования к phrases:\n"
        "- каждая фраза это законченное предложение 8-12 слов;\n"
        "- первая фраза — цепляющий хук, который бьёт в тему в первые 1-2 секунды (без длинного вступления);\n"
        "- последняя фраза — короткий CTA, ровно одно предложение;\n"
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
