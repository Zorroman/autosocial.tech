"""Duration shaping for 30s Shorts: the estimator is calibrated to real TTS and
_ensure_target_duration_phrases pads short scripts up and trims long ones down
into the target band, without ever cutting the hook or the closing CTA."""
import pytest

import video_script_generator as g


def _est(phrases):
    return g._estimate_seconds_from_phrases(phrases)


def test_estimator_matches_real_tts():
    # project 175 (onyx + voice_tone="calm", the current Shorts narrator):
    # 397 chars rendered to 42.16s -> ~9.4 chars/s. Supersedes the old 12.5
    # chars/s calibration (project 5), which predates the voice unification
    # onto onyx+calm and was measured against a faster voice/pace.
    assert abs(_est(["x" * 397]) - 42.23) < 1.5


def test_overlong_script_trimmed_into_band():
    # 5 long phrases (~35s, the project-6/5 failure mode)
    phrases = [
        "Символы окружают нас повсюду и они рассказывают свои истории каждый день.",
        "Мы часто не замечаем как символы формируют нашу реальность и восприятие мира.",
        "Символы связывают нас с культурой историей и глубокими традициями предков.",
        "Каждый символ это отражение нашей жизни и окружения вокруг нас сегодня.",
        "Понимание символов помогает лучше ориентироваться в этом сложном мире.",
    ]
    out = g._ensure_target_duration_phrases(list(phrases), "символы", 30, None)
    assert 27 <= _est(out) <= 33
    # hook and CTA preserved (first stays first; last is a real closing line)
    assert out[0] == phrases[0]


def test_hook_and_cta_never_cut_when_trimming():
    # distinct middles (no dedupe) and an over-target total → pure trim path
    phrases = (["ХУК номер один про тайные знаки судьбы вокруг нас."]
               + [f"Сцена {i} раскрывает отдельную грань этой большой темы подробно." for i in range(6)]
               + ["ФИНАЛ подпишись чтобы не потерять остальные знаки."])
    assert _est(phrases) > 34  # starts over the band
    out = g._ensure_target_duration_phrases(list(phrases), "тема", 30, None)
    assert out[0].startswith("ХУК")
    assert out[-1].startswith("ФИНАЛ")  # closing CTA preserved as last
    assert _est(out) <= 34  # trimmed toward the band


def test_realistic_short_script_in_band():
    phrases = [
        "Хук про скрытый знак вокруг тебя сегодня.",
        "Число 11 11 повторяется в жизни не случайно.",
        "Оно мягко тянет внимание к твоей главной цели.",
        "Древние видели в нём знак важного перехода.",
        "Проверь где именно оно встречается сегодня.",
        "Запиши свою первую мысль в этот момент.",
        "Так простой символ становится твоим ориентиром.",
        "Подпишись чтобы не потерять эти знаки.",
    ]
    out = g._ensure_target_duration_phrases(list(phrases), "знаки", 30, None)
    assert 27 <= _est(out) <= 33


# ---------------------------------------- minimum phrase count + retry

def test_min_phrases_matches_prompt_lower_bound():
    # Same formula as the "Сделай N-M коротких сцен" prompt line in
    # generate() -- kept as one function (_min_phrases_for) so a prompt edit
    # can't silently drift out of sync with what the retry validator accepts.
    assert g._min_phrases_for(30) == 8
    assert g._min_phrases_for(20) == 6  # floor: never demand fewer than 6


def test_raw_count_passing_but_sanitized_too_short_is_rejected(monkeypatch):
    """Real project-180 failure mode: the model returned 9 phrases (passing
    a raw count check), but _sanitize_phrase drops short/banned lines and
    _dedupe_keep_order merges near-duplicates, leaving only ~4 phrases
    totalling ~19s against a 27s floor -- _ensure_target_duration_phrases
    then silently padded with generic filler anyway. The validator must
    check the *sanitized* survivor set, not the raw payload count."""
    monkeypatch.setattr(g, "is_openai_enabled", lambda: True)

    calls = []

    def fake_generate(*, validator, **kwargs):
        if calls.count("accepted_full") >= 1:
            class _HookResult:
                payload = {"hook": "Настоящий хук уже был принят без изменений."}
            return _HookResult()

        # 9 raw phrases: 5 are under _sanitize_phrase's 20-char floor (empty
        # after cleanup), the other 4 total well under the 27s duration floor.
        raw_9 = {
            "phrases": (
                ["Коротко.", "Ещё.", "Да.", "Верно.", "Именно так."]
                + ["Первая настоящая мысль про тему сегодня.",
                   "Вторая настоящая мысль про эту же тему.",
                   "Третья мысль тоже про эту самую тему.",
                   "Четвёртая мысль подводит итог всему."]
            ),
            "shotlist": [], "title": "t", "description": "d", "hashtags": [], "safety_rules": [],
        }
        with pytest.raises(ValueError, match="too short after cleanup"):
            validator(raw_9)
        calls.append("rejected_short_after_cleanup")

        enough = {
            "phrases": [f"Мысль {i} про личные границы человека сегодня." for i in range(8)],
            "shotlist": [], "title": "t", "description": "d", "hashtags": [], "safety_rules": [],
        }
        validator(enough)
        calls.append("accepted_full")

        class _Result:
            payload = enough
        return _Result()

    monkeypatch.setattr(g, "generate_json_with_retry", fake_generate)

    bundle = g.generate(topic="Тема", offer=None, language="ru", target_seconds=30, style="")
    assert calls == ["rejected_short_after_cleanup", "accepted_full"]
    assert bundle.used_fallback is False
    assert "Добавим короткий пример из жизни" not in " ".join(bundle.phrases)


def test_short_first_response_retried_then_accepted(monkeypatch):
    """A too-short first response (the project-176 failure mode: 2-3 real
    phrases padded out with generic _topic_fillers() filler) must not reach
    the caller as-is -- generate_json_with_retry's validator should reject
    it, and only a response with enough phrases should come back."""
    monkeypatch.setattr(g, "is_openai_enabled", lambda: True)

    calls = []

    def fake_generate(*, validator, **kwargs):
        # generate() makes exactly one such call for the phrases payload;
        # _apply_hook_diversity may make further, differently-shaped calls
        # afterward (hook regeneration) if it judges phrases[0] a weak hook
        # -- not what this test is about, so hand those a trivial pass.
        if calls.count("accepted_full") >= 1:
            class _HookResult:
                payload = {"hook": "Реальный хук уже был принят без изменений."}
            return _HookResult()

        too_short = {
            "phrases": ["Хук про границы.", "Второй короткий вывод.", "Подпишись."],
            "shotlist": [], "title": "t", "description": "d", "hashtags": [], "safety_rules": [],
        }
        with pytest.raises(ValueError):
            validator(too_short)
        calls.append("rejected_short")

        # Short phrases, deliberately under the 282-char (30s * 9.4 chars/s)
        # budget in total -- enough phrases to pass the count floor without
        # also tripping _ensure_target_duration_phrases's separate ceiling
        # trim, which would otherwise remove some regardless of count.
        enough = {
            "phrases": [f"Мысль {i} про личные границы человека сегодня." for i in range(8)],
            "shotlist": [], "title": "t", "description": "d", "hashtags": [], "safety_rules": [],
        }
        validator(enough)  # must not raise
        calls.append("accepted_full")

        class _Result:
            payload = enough
        return _Result()

    monkeypatch.setattr(g, "generate_json_with_retry", fake_generate)

    bundle = g.generate(topic="Личные границы", offer=None, language="ru",
                        target_seconds=30, style="")
    assert calls == ["rejected_short", "accepted_full"]
    assert bundle.used_fallback is False
    # the generic padding filler must not appear when the model supplied
    # enough real content
    assert "Добавим короткий пример из жизни" not in " ".join(bundle.phrases)


def test_persistently_short_response_falls_back(monkeypatch):
    """If the model can't produce enough phrases even after the retry,
    generate_json_with_retry itself raises (matching its real two-attempt
    exhaustion behavior) -- generate() must fall back to the deterministic
    template rather than accept a too-short script."""
    monkeypatch.setattr(g, "is_openai_enabled", lambda: True)

    def fake_generate(*, validator, **kwargs):
        too_short = {
            "phrases": ["Хук.", "Вывод."],
            "shotlist": [], "title": "t", "description": "d", "hashtags": [], "safety_rules": [],
        }
        with pytest.raises(ValueError):
            validator(too_short)
        raise g.OpenAIClientError("still too short after retry", error_class="other")

    monkeypatch.setattr(g, "generate_json_with_retry", fake_generate)

    bundle = g.generate(topic="Личные границы", offer=None, language="ru",
                        target_seconds=30, style="")
    assert bundle.used_fallback is True
