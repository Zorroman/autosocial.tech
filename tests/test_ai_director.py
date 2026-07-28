import importlib
import os
import sys

import pytest


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test_director.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    os.environ["USE_MOCK_PROVIDERS"] = "true"
    os.environ["SYNC_JOBS"] = "true"
    os.environ["ADMIN_EMAIL"] = "admin@test.local"
    os.environ["ADMIN_PASSWORD"] = "adminpass123"
    os.environ["GOOGLE_CLIENT_ID"] = ""
    os.environ["GOOGLE_CLIENT_SECRET"] = ""
    os.environ["FB_LOGIN_APP_ID"] = ""
    os.environ["FB_LOGIN_APP_SECRET"] = ""
    os.environ["ENV"] = "development"
    os.environ["SMTP_HOST"] = ""
    os.environ["SMTP_FROM"] = ""
    os.environ["SMTP_USER"] = ""
    os.environ["SMTP_PASSWORD"] = ""
    os.environ["OPENAI_API_KEY"] = ""

    for name in [
        "app",
        "database",
        "models",
        "saas_models",
        "saas_services",
        "saas_auth",
        "saas_api",
        "saas_queue",
        "saas_settings",
    ]:
        if name in sys.modules:
            del sys.modules[name]

    app_module = importlib.import_module("app")
    with app_module.app.test_client() as test_client:
        yield test_client


def register_user(client, email="director@test.local", password="pass12345"):
    challenge = client.post("/api/auth/register", json={"email": email, "password": password})
    payload = challenge.get_json() or {}
    return client.post("/api/auth/verify-code", json={"challenge_token": payload.get("challenge_token"), "code": payload.get("dev_code")})


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_director_suggest_returns_counts(client):
    reg = register_user(client, "d1@test.local", "pass12345")
    token = reg.get_json()["token"]
    r = client.post(
        "/api/ai/director/suggest",
        json={
            "topic": "Контент-план для локального бизнеса",
            "goal": "engagement",
            "platforms": ["facebook", "instagram"],
            "language": "ru",
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    p = r.get_json()
    data = p.get("data") or {}
    assert len(data.get("topics") or []) == 10
    assert len(data.get("angles") or []) >= 3  # director now offers more angle options (was fixed 3)
    assert len(data.get("cta_options") or []) == 3


def test_director_suggest_respects_esoterics_niche_context(client):
    reg = register_user(client, "esoteric@test.local", "pass12345")
    token = reg.get_json()["token"]
    r = client.post(
        "/api/ai/director/suggest",
        json={
            "topic": "Эзотерика",
            "niche_label": "Эзотерика",
            "niche_context": {
                "label": "Эзотерика",
                "keywords": ["энергия", "интуиция", "лунные циклы"],
                "painPoints": ["Сложно понять свои внутренние сигналы"],
                "contentAngles": ["интуиция", "лунные циклы", "внутреннее состояние"],
                "topicTemplates": [
                    "Как понять, что ваша интуиция пытается вас предупредить",
                    "3 признака энергетического истощения",
                    "Как подготовиться к новолунию",
                    "Почему вы постоянно видите одинаковые числа",
                    "Что такое духовное пробуждение простыми словами",
                    "Как очистить дом от тяжелой энергии",
                    "Почему желания не исполняются, даже если вы очень стараетесь",
                    "Как защитить себя от чужой негативной энергии",
                    "Какие вещи могут блокировать поток изобилия",
                    "Почему важно отпускать старое перед новым этапом жизни",
                ],
                "ctaTemplates": [
                    "Напишите «ЭНЕРГИЯ», и мы подскажем мягкую практику под ваше состояние.",
                    "Сохраните пост, чтобы вернуться к нему в спокойный момент.",
                    "Напишите в сообщения, если хотите разобраться, с чего начать.",
                ],
                "bannedCrossNicheWords": ["автосервис", "барбершоп", "ремонт квартиры"],
            },
            "goal": "engagement",
            "platforms": ["facebook", "instagram"],
            "language": "ru",
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    data = (r.get_json() or {}).get("data") or {}
    topics = data.get("topics") or []
    joined = " ".join(topics).lower()
    assert len(topics) == 10
    assert "интуиц" in joined or "энерг" in joined or "луни" in joined
    assert "автосервис" not in joined


def test_director_generate_drafts_returns_at_least_one(client):
    reg = register_user(client, "d2@test.local", "pass12345")
    token = reg.get_json()["token"]
    r = client.post(
        "/api/ai/director/generate-drafts",
        json={
            "topic": "Контент для стоматологии",
            "angle": "Через частые ошибки клиентов",
            "goal": "lead",
            "platforms": ["facebook"],
            "language": "ru",
            "variants": 3,
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    p = r.get_json()
    drafts = ((p.get("data") or {}).get("drafts") or [])
    assert len(drafts) >= 1


def test_barbershop_awareness_does_not_return_marketing_advice(client):
    reg = register_user(client, "d4@test.local", "pass12345")
    token = reg.get_json()["token"]
    topic = "barbershop"
    r = client.post(
        "/api/ai/director/generate-drafts",
        json={
            "topic": topic,
            "angle": "Полезный разбор для клиентов",
            "goal": "Охват",
            "platforms": ["facebook"],
            "language": "ru",
            "variants": 1,
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    p = r.get_json() or {}
    drafts = ((p.get("data") or {}).get("drafts") or [])
    assert len(drafts) >= 1
    body = str(drafts[0].get("body_text") or "").lower()
    hook = str(drafts[0].get("hook") or "")
    assert "reach" not in body
    assert "engagement" not in body
    assert "content strategy" not in body
    assert "охват" not in body
    assert "вовлечение" not in body
    assert "контент-стратег" not in body
    assert hook.strip().lower() != topic


def test_quality_score_positive_for_valid_text(client):
    reg = register_user(client, "d3@test.local", "pass12345")
    token = reg.get_json()["token"]
    r = client.post(
        "/api/ai/quality-check",
        json={
            "caption": "Как получить больше заявок без роста бюджета?\n\n1) Упростите путь клиента.\n2) Добавьте явный оффер.\nНапишите в директ — пришлю шаблон.",
            "cta": "Напишите в директ",
            "hashtags": ["#маркетинг", "#лиды", "#контент"],
            "goal": "lead",
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    quality = ((r.get_json().get("data") or {}).get("quality") or {})
    assert int(quality.get("score") or 0) > 0


def test_create_ui_route_contains_app_mount():
    html = open("frontend/create/index.html", "r", encoding="utf-8").read()
    js = open("frontend/app.js", "r", encoding="utf-8").read()
    niches = open("frontend/data/nicheTemplates.js", "r", encoding="utf-8").read()
    assert 'id="app"' in html
    assert "pageCreateDirector" in js
    assert "id: 'esoterica'" in niches
    assert "const nicheOptions = DIRECTOR_NICHE_OPTIONS;" in js
    assert "const nicheToCategory = {" not in js


def test_director_generate_image_route_uses_stock_media_provider(client, monkeypatch):
    import saas_api as saas_api_module

    reg = register_user(client, "imgroute@test.local", "pass12345")
    token = reg.get_json()["token"]

    class FakeImage:
        provider = "pexels"
        local_url = "https://api.autosocial.tech/api/media/pexels_777.jpg"

        def to_dict(self):
            return {
                "provider": "pexels",
                "type": "photo",
                "external_id": "777",
                "preview_url": "https://images.pexels.com/photos/777/preview.jpg",
                "full_url": "https://images.pexels.com/photos/777/full.jpg",
                "width": 1200,
                "height": 1500,
                "photographer": "Test",
                "orientation": "portrait",
                "query_used": "moon ritual candles",
                "score": 42.0,
                "local_url": "https://api.autosocial.tech/api/media/pexels_777.jpg",
                "local_path": "/tmp/pexels_777.jpg",
            }

    monkeypatch.setattr(saas_api_module, "_fetch_post_media_or_error", lambda **kwargs: FakeImage())
    monkeypatch.setattr(saas_api_module, "_download_and_store_binary", lambda url, suffix: (url, 1))
    r = client.post(
        "/api/ai/director/generate-image",
        json={
            "topic": "Как распознать знаки Вселенной",
            "niche_label": "Эзотерика",
            "platform": "instagram",
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload["data"]["source"] == "pexels"
    assert "pexels_" in payload["data"]["image_url"]



def test_director_generate_image_route_succeeds_without_image(client, monkeypatch):
    import saas_api as saas_api_module

    reg = register_user(client, "imgnone@test.local", "pass12345")
    token = reg.get_json()["token"]

    monkeypatch.setattr(saas_api_module, "_fetch_post_media_or_error", lambda **kwargs: None)
    r = client.post(
        "/api/ai/director/generate-image",
        json={
            "topic": "Rare topic without matching stock image",
            "niche_label": "Unknown niche",
            "platform": "instagram",
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload["data"]["source"] == "none"
    assert payload["data"]["image_url"] is None
    assert "image_not_found" in (payload.get("warnings") or [])
    assert payload.get("debug_code") == "director_image_not_found"
