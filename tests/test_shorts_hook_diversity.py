"""Shorts hook diversity fix.

Scope: only the opening 1-2 phrases of a Shorts script. Scheduler, media
selection, TTS, subtitles, music, CTA, render, YouTube upload, and the
long-form generator are untouched -- see test_factory_pipeline_e2e.py,
test_footage_subtitles.py, and test_cta.py for proof those still pass
unchanged.

Root cause covered here: video_script_generator._fallback() used one
hardcoded opening line. Repeated OpenAI failures (or, in tests,
USE_MOCK_PROVIDERS=true) all landed on that same fallback, producing a run
of visually-identical Shorts openers.
"""
import pytest

from tests.test_private_admin import _fresh_app, _seed_admin, _token_for


@pytest.fixture()
def client(tmp_path):
    app_module = _fresh_app(tmp_path)
    admin_id = _seed_admin()
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)
        yield c


def _h(c):
    return {"Authorization": f"Bearer {c.admin_token}"}


def _mk_channel(c, name="Эзотерика"):
    r = c.post("/api/channels", json={"name": name, "niche": "эзотерика"}, headers=_h(c))
    assert r.status_code == 201
    return r.get_json()["channel"]["id"]


def _mk_short(c, channel_id, title):
    r = c.post("/api/video-projects", json={"channel_id": channel_id, "title": title,
                                             "duration_target_seconds": 30}, headers=_h(c))
    assert r.status_code == 201
    return r.get_json()["project"]["id"]


# ---------------------------------------------------------------- 1. forbidden templates

def test_forbidden_templates_are_rejected():
    from shorts_hook_diversity import is_templated_hook

    banned = [
        "Сегодня коротко и понятно разбираем тему «Числа».",
        "Сегодня мы разберём признаки расставания.",
        "Давайте разберемся, почему вам снится умерший человек.",
        "В этом видео покажем три сигнала опасности.",
        "Вы когда-нибудь задумывались, почему так происходит?",
        "Мало кто знает эту особенность чисел.",
        "А вы знали, что это совпадение неслучайно?",
        "Сейчас расскажу, как распознать три сигнала.",
        "Сегодня поговорим о признаках расставания.",
        "Разберём тему счастливых чисел подробно.",
    ]
    for hook in banned:
        assert is_templated_hook(hook), f"should be rejected: {hook!r}"

    good = [
        "Одно число может преследовать вас не случайно.",
        "Есть три сигнала, после которых отношения уже почти закончены.",
        "Если умерший человек снова приходит во сне, это может быть не просто память.",
    ]
    for hook in good:
        assert not is_templated_hook(hook), f"should be accepted: {hook!r}"


# ------------------------------------------------------------- 2. adjacent hooks differ

def test_two_adjacent_hooks_do_not_collide():
    from shorts_hook_diversity import hook_similarity, most_similar_score

    a = "Есть три сигнала, после которых отношения уже почти закончены."
    b = "Есть три сигнала, после которых отношения почти всегда заканчиваются."
    c = "Одно число может преследовать вас не случайно."

    assert hook_similarity(a, b) > 0.6  # near-duplicate wording, same structure
    assert hook_similarity(a, c) < 0.3  # unrelated hooks
    assert most_similar_score(a, [c]) < 0.3
    assert most_similar_score(a, [b, c]) > 0.6


# --------------------------------------------------------- 3+4. similarity triggers regen

def test_similarity_above_threshold_regenerates_only_hook(monkeypatch):
    import video_script_generator as vsg

    monkeypatch.setattr(vsg, "is_openai_enabled", lambda: True)

    calls = {"n": 0}

    body = [
        "Второй шаг — простое действие, которое можно сделать сразу, без долгой подготовки и лишних условий.",
        "Третий момент — частая ошибка, которую легко избежать, если знать, на что обратить внимание заранее.",
        "В финале — четкий шаг, который можно проверить на практике уже сегодня вечером, без специальных инструментов.",
    ]

    def fake_generate(system_prompt, user_prompt, validator, max_output_tokens, temperature):
        calls["n"] += 1
        if "phrases" in user_prompt or "shotlist" in user_prompt:
            payload = {
                "phrases": ["Сегодня коротко и понятно разбираем тему «Числа»."] + body,  # hook is templated, must be replaced
                "shotlist": [],
                "title": "Числа: практический разбор",
                "description": "desc",
                "hashtags": ["#числа"],
                "safety_rules": ["only realistic scenes"],
            }
        else:
            # hook-regeneration call
            payload = {"hook": "Одно число может преследовать вас не случайно."}
        validator(payload)

        class _R:
            pass
        r = _R()
        r.payload = payload
        return r

    monkeypatch.setattr(vsg, "generate_json_with_retry", fake_generate)

    bundle = vsg.generate(topic="Числа", offer=None, language="ru", target_seconds=30, style="")

    assert bundle.phrases[0] == "Одно число может преследовать вас не случайно."
    # everything else in the script is untouched -- only the hook was regenerated
    assert bundle.phrases[1:1 + len(body)] == body
    assert bundle.hook_type is not None


def test_regeneration_checks_against_recent_channel_hooks(monkeypatch):
    import video_script_generator as vsg

    monkeypatch.setattr(vsg, "is_openai_enabled", lambda: True)
    responses = iter([
        {"hook": "Одно число может преследовать вас не случайно."},  # too similar to recent_hooks[0]
        {"hook": "Мало кто замечает, как одно число влияет на решения каждый день подряд."},  # accepted
    ])

    def fake_generate(system_prompt, user_prompt, validator, max_output_tokens, temperature):
        if "phrases" in user_prompt:
            payload = {
                "phrases": [
                    "Сегодня поговорим про числа.",  # templated -> forces regeneration
                    "Второй шаг — простое действие.",
                    "Третий момент — частая ошибка.",
                    "В финале — четкий шаг.",
                ],
                "shotlist": [], "title": "t", "description": "d",
                "hashtags": [], "safety_rules": [],
            }
        else:
            payload = next(responses)
        validator(payload)

        class _R:
            pass
        r = _R()
        r.payload = payload
        return r

    monkeypatch.setattr(vsg, "generate_json_with_retry", fake_generate)

    bundle = vsg.generate(
        topic="Числа", offer=None, language="ru", target_seconds=30, style="",
        recent_hooks=["Одно число может преследовать вас не случайно."],
    )

    assert bundle.phrases[0] == "Мало кто замечает, как одно число влияет на решения каждый день подряд."


# --------------------------------------------------------------- 5. hook matches topic

def test_deterministic_hook_mentions_the_topic():
    from shorts_hook_diversity import HOOK_TYPES, deterministic_hook

    for t in HOOK_TYPES:
        hook = deterministic_hook("счастливые числа", t)
        assert "счастливые числа" in hook


# ----------------------------------------------------- 6. numeric promise preserved

def test_hook_regeneration_never_touches_the_rest_of_the_script(monkeypatch):
    import video_script_generator as vsg

    monkeypatch.setattr(vsg, "is_openai_enabled", lambda: False)  # forces total fallback
    bundle = vsg.generate(topic="Три признака расставания", offer=None, language="ru",
                          target_seconds=30, style="")
    body_before = bundle.phrases[1:]

    # A second call with the same topic must trigger regeneration (same
    # fallback hook would otherwise repeat) -- body phrases must still be
    # generated the same way, untouched by hook substitution.
    bundle2 = vsg.generate(topic="Три признака расставания", offer=None, language="ru",
                           target_seconds=30, style="", recent_hooks=[bundle.phrases[0]])
    assert bundle2.phrases[1:] == body_before


# ------------------------------------------------------- 7. no more than 2 same type

def test_no_more_than_two_same_hook_type_in_a_row():
    from shorts_hook_diversity import HOOK_TYPES, next_hook_type

    history: list[str] = []
    for _ in range(20):
        t = next_hook_type(history)
        history.append(t)
        last_three = history[-3:]
        if len(last_three) == 3:
            assert not (last_three[0] == last_three[1] == last_three[2])
    assert set(history) <= set(HOOK_TYPES)


# --------------------------------------------------------- 8. last 50 hooks considered

def test_repeated_fallback_topic_does_not_repeat_the_same_hook(client):
    """The exact reported bug: consecutive Shorts landing on the same
    templated opener. USE_MOCK_PROVIDERS=true (test default) means every
    /generate-script call here takes the total-fallback path -- this is the
    worst case from the bug report, verified end-to-end through the real API
    and the real channel-scoped history query, not just the pure function."""
    ch = _mk_channel(client)
    topic = "Эмоциональная связь: что это значит"

    hooks = []
    for _ in range(3):
        pid = _mk_short(client, ch, topic)
        r = client.post(f"/api/video-projects/{pid}/generate-script", json={}, headers=_h(client))
        assert r.status_code == 200
        script = r.get_json()["script_text"]
        hooks.append(script.split("\n", 1)[0].strip())

    assert len(set(hooks)) == len(hooks), f"hooks repeated: {hooks}"


# ------------------------------------------------------------------ 9. long-form untouched

def test_longform_bypasses_hook_diversity_entirely(monkeypatch):
    import video_script_generator as vsg

    monkeypatch.setattr(vsg, "is_openai_enabled", lambda: True)

    # Deliberately templated -- if hook-diversity logic ran on this, it would
    # replace phrases[0]. Proving it comes back untouched proves generate()
    # never routes a long-form result through _apply_hook_diversity.
    canned = vsg.ScriptBundle(
        phrases=["Сегодня коротко и понятно разбираем тему медитации."] + [f"Раздел {i} длинного повествования." for i in range(1, 9)],
        shotlist=[{"phrase_index": i, "queries": [], "mood": "calm", "scene_type": "nature"} for i in range(9)],
        title="t", description="d", hashtags=[], safety_rules=[],
    )
    monkeypatch.setattr(vsg, "_generate_longform", lambda *a, **k: canned)

    bundle = vsg.generate(topic="Медитация", offer=None, language="ru", target_seconds=600, style="спокойный")
    assert bundle is canned
    assert bundle.phrases[0] == "Сегодня коротко и понятно разбираем тему медитации."
    assert bundle.hook_type is None  # never touched by hook-diversity logic


# -------------------------------------------------- 10. full Shorts pipeline to render

def test_shorts_pipeline_still_reaches_scene_split_after_hook_fix(client):
    ch = _mk_channel(client)
    pid = _mk_short(client, ch, "Три признака перемен")
    gen = client.post(f"/api/video-projects/{pid}/generate-script", json={}, headers=_h(client))
    assert gen.status_code == 200

    split = client.post(f"/api/video-projects/{pid}/split-scenes", headers=_h(client))
    assert split.status_code == 201
    scenes = split.get_json()["scenes"]
    assert len(scenes) >= 4
