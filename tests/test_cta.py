"""Final subscribe-CTA: generation, validation, de-duplication, settings."""
from types import SimpleNamespace

import cta_generator as cta


def fake_llm(text, ctype="subscribe_benefit"):
    def _call(**kwargs):
        v = kwargs.get("validator")
        payload = {"cta": text, "type": ctype}
        if v:
            v(payload)
        return SimpleNamespace(payload=payload)
    return _call


# 1) CTA generated for a new video
def test_generates_cta():
    out = cta.generate_cta({"language": "ru", "niche": "ЭЗОТЕРИКА", "recent_ctas": [], "recent_types": []},
                           llm=fake_llm("Подпишись, чтобы каждый день узнавать новые удивительные факты о символах."))
    assert out["source"] == "generated" and out["fallback_used"] is False
    assert out["type"] in cta.CTA_TYPES
    assert "подпиш" in out["text"].lower()


# 2) CTA matches project language (ru → Cyrillic; en → latin)
def test_language_match():
    ru = cta.generate_cta({"language": "ru", "recent_ctas": [], "recent_types": []},
                          llm=fake_llm("Подпишись, чтобы не пропустить новые истории и полезные разборы."))
    assert ru["language"] == "ru"
    # an English CTA offered for a ru video is rejected → falls back to ru
    bad = cta.generate_cta({"language": "ru", "recent_ctas": [], "recent_types": []},
                           llm=fake_llm("Subscribe to keep learning more amazing facts every single day."))
    assert bad["language"] == "ru" and "подпиш" in bad["text"].lower()


# 3) cta_enabled default true, and read_cta_settings honors channel overrides
def test_settings_defaults_and_override():
    d = cta.default_settings()
    assert d["cta_enabled"] is True and d["cta_history_window"] == 20 and d["cta_max_same_type_streak"] == 3
    ch = SimpleNamespace(generation_settings_json='{"cta": {"cta_enabled": false, "cta_visual_enabled": false}}')
    s = cta.read_cta_settings(ch)
    assert s["cta_enabled"] is False and s["cta_visual_enabled"] is False
    assert s["cta_voice_enabled"] is True  # untouched keys keep defaults


# 4/5) voice/visual toggles are independent keys
def test_voice_and_visual_independent():
    ch = SimpleNamespace(generation_settings_json='{"cta": {"cta_voice_enabled": false}}')
    s = cta.read_cta_settings(ch)
    assert s["cta_voice_enabled"] is False and s["cta_visual_enabled"] is True


# 6) same phrase not reused within window (normalized + near-dup)
def test_repeat_protection():
    recent = ["Подпишись, чтобы каждый день узнавать новые удивительные факты."]
    assert cta.is_repeat("подпишись чтобы каждый день узнавать новые удивительные факты", recent, "ru")
    assert cta.is_repeat("Подпишись, чтобы каждый день узнавать новые удивительные факты!!!", recent, "ru")
    assert not cta.is_repeat("Подпишись и загляни в следующий ролик про древние символы.", recent, "ru")


# 7) one type not chosen more than 3 in a row
def test_type_streak():
    assert cta.type_streak_blocked("subscribe_benefit", ["subscribe_benefit"] * 3, 3)
    assert not cta.type_streak_blocked("subscribe_benefit", ["subscribe_benefit"] * 2, 3)
    # _choose_type rotates away from a maxed streak
    t = cta._choose_type(["subscribe_benefit"] * 3, 3)
    assert t != "subscribe_benefit"


# 8) generation error → safe fallback, never crash
def test_generation_error_falls_back():
    def _boom(**kwargs):
        raise RuntimeError("llm down")
    out = cta.generate_cta({"language": "ru", "recent_ctas": [], "recent_types": []}, llm=_boom)
    assert out["source"] == "fallback" and out["fallback_used"] is True
    assert "подпиш" in out["text"].lower()


# 9) validation rejects the bad cases
def test_validation_rules():
    v = cta.validate_cta
    assert v("", "ru", 8, 16) == "empty"
    assert v("Подпишись сейчас же друзья.", "ru", 8, 16).startswith("too_short")
    assert v(" ".join(["Подпишись"] + ["слово"] * 20), "ru", 8, 16).startswith("too_long")
    assert v("Это просто финальная мысль без всякого призыва к действию сегодня.", "ru", 8, 16) == "no_subscribe_call"
    assert v("Подпишись, поставь лайк и напиши комментарий под этим роликом обязательно.", "ru", 8, 16) == "multiple_actions"
    # valid
    assert v("Подпишись, чтобы не пропустить новые истории и открытия по теме.", "ru", 8, 16) is None


# 10) a generated CTA that repeats a recent one is rejected → fallback
def test_generated_repeat_rejected():
    recent = ["Подпишись, чтобы каждый день узнавать новые удивительные факты о мире."]
    out = cta.generate_cta({"language": "ru", "recent_ctas": recent, "recent_types": []},
                           llm=fake_llm(recent[0]))  # LLM returns a repeat every time
    assert out["fallback_used"] is True   # couldn't get a unique one → safe fallback
    assert not cta.is_repeat(out["text"], recent, "ru")


# 11) fallback itself respects repeat + streak
def test_fallback_varies():
    pool_first = cta._FALLBACKS["ru"][0][0]
    text, ctype = cta.pick_fallback("ru", [pool_first], [], 3)
    assert cta.normalize(text) != cta.normalize(pool_first)
