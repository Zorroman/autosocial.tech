"""Duration shaping for 30s Shorts: the estimator is calibrated to real TTS and
_ensure_target_duration_phrases pads short scripts up and trims long ones down
into the target band, without ever cutting the hook or the closing CTA."""
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
