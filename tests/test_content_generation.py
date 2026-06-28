import importlib
import os
import sys

import pytest


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "content_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    os.environ["USE_MOCK_PROVIDERS"] = "true"
    os.environ["SYNC_JOBS"] = "true"
    os.environ["ADMIN_EMAIL"] = "admin@test.local"
    os.environ["ADMIN_PASSWORD"] = "adminpass123"
    os.environ["GOOGLE_CLIENT_ID"] = ""
    os.environ["GOOGLE_CLIENT_SECRET"] = ""
    os.environ["FACEBOOK_APP_ID"] = ""
    os.environ["FACEBOOK_APP_SECRET"] = ""
    os.environ["FACEBOOK_CLIENT_ID"] = ""
    os.environ["FACEBOOK_CLIENT_SECRET"] = ""
    os.environ["FB_APP_ID"] = ""
    os.environ["FB_APP_SECRET"] = ""
    os.environ["FB_LOGIN_APP_ID"] = ""
    os.environ["FB_LOGIN_APP_SECRET"] = ""
    os.environ["FB_LOGIN_SCOPE"] = "public_profile,email"
    os.environ["ENV"] = "development"
    os.environ["SMTP_HOST"] = ""
    os.environ["SMTP_FROM"] = ""
    os.environ["SMTP_USER"] = ""
    os.environ["SMTP_PASSWORD"] = ""

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
        "content_pipeline",
        "openai_client",
    ]:
        if name in sys.modules:
            del sys.modules[name]

    app_module = importlib.import_module("app")
    with app_module.app.test_client() as test_client:
        yield test_client


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def register_user(client, email="user@test.local", password="pass12345"):
    challenge = client.post("/api/auth/register", json={"email": email, "password": password})
    assert challenge.status_code == 200
    payload = challenge.get_json() or {}
    return client.post(
        "/api/auth/verify-code",
        json={"challenge_token": payload["challenge_token"], "code": payload["dev_code"]},
    )


def test_content_pipeline_strategy_validator_accepts_valid_payload():
    from content_pipeline import validate_strategy_payload

    payload = {
        "audience": "SMB owners",
        "angle": "Practical approach",
        "context": "Need practical steps",
        "usp": "Simple framework",
        "structure": "Hook -> steps -> CTA",
        "key_points": ["A", "B", "C"],
        "hook_ideas": ["H1", "H2", "H3", "H4", "H5"],
        "objections_answers": [
            {"objection": "No time", "answer": "Reuse assets"},
            {"objection": "No team", "answer": "Start with one channel"},
            {"objection": "No budget", "answer": "Use organic first"},
        ],
        "cta_variants": ["CTA1", "CTA2", "CTA3"],
        "hashtag_sets": [["#a", "#b", "#c"], ["#d", "#e", "#f"]],
        "visual_ideas": ["v1", "v2", "v3", "v4", "v5"],
    }
    validate_strategy_payload(payload)


def test_content_pipeline_draft_validator_accepts_valid_payload():
    from content_pipeline import validate_draft_payload

    payload = {
        "platform": "youtube",
        "variant_index": 1,
        "post_text": "Main script text",
        "title": "Title",
        "description": "Long description",
        "hashtags": ["#a", "#b", "#c"],
        "cta": "Subscribe",
        "asset_ideas": ["v1", "v2", "v3"],
        "pinned_comment_text": "Tell me your case",
    }
    validate_draft_payload(payload)


def test_content_generate_saves_brief_strategy_and_drafts(client):
    from database import SessionLocal
    from saas_models import ContentBrief, ContentDraft, ContentStrategy

    reg = register_user(client, "content-gen@test.local", "pass12345")
    assert reg.status_code == 200
    token = reg.get_json()["token"]

    resp = client.post(
        "/api/content/generate",
        json={
            "topic": "How a local service can increase repeat sales",
            "offer": "",
            "language": "ru",
            "tone": "friendly",
            "goal": "engagement",
            "platforms": ["facebook", "instagram", "youtube"],
            "variants": 3,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["brief_id"] > 0
    assert isinstance(payload.get("strategy"), dict)
    assert len(payload.get("drafts") or []) == 9

    brief_id = payload["brief_id"]
    db = SessionLocal()
    try:
        brief = db.query(ContentBrief).filter(ContentBrief.id == brief_id).first()
        assert brief is not None
        strategy = db.query(ContentStrategy).filter(ContentStrategy.brief_id == brief_id).first()
        assert strategy is not None
        drafts = db.query(ContentDraft).filter(ContentDraft.brief_id == brief_id).all()
        assert len(drafts) == 9
    finally:
        db.close()


def test_generate_hashtags_russian_barbershop_city_clean():
    from content_pipeline import generateHashtags

    tags = generateHashtags(
        niche="Барбершоп",
        city="Ингольштадт",
        language="Русский",
        goal="Охват",
    )
    assert 5 <= len(tags) <= 12
    assert len(tags) == len(set(tags))
    assert all(t.startswith("#") for t in tags)
    assert all("," not in t and "'" not in t and "’" not in t for t in tags)
    assert all(len(t) < 30 for t in tags)
    assert all(all(ch == "#" or ch.isalnum() for ch in t) for t in tags)

    expected = {
        "#барбершоп",
        "#барбер",
        "#мужскаястрижка",
        "#борода",
        "#ингольштадт",
        "#стильмужчины",
        "#мужскойстиль",
    }
    assert expected.issubset(set(tags))


def test_create_generate_hides_technical_fallback_warnings(client, monkeypatch):
    import saas_api as saas_api_module
    from content_pipeline import ContentGenerationResult

    reg = register_user(client, "createwarn@test.local", "pass12345")
    assert reg.status_code == 200
    token = reg.get_json()["token"]

    fake = ContentGenerationResult(
        strategy={"audience": "local clients"},
        drafts=[
            {
                "platform": "facebook",
                "variant_index": 1,
                "post_text": "Готовый текст для клиентов.",
                "hashtags": ["#бизнес", "#услуги", "#город"],
                "cta": "Напишите нам в директ.",
            }
        ],
        token_input=1,
        token_output=1,
        status="partial",
        warnings=[
            "structured_json_failed",
            "simplified_failed",
            "hard_fallback_default",
            "facebook v1: full-schema не прошла, применен simplified fallback.",
        ],
        debug_code="draft_schema_fallback|draft_text_fallback",
    )

    monkeypatch.setattr(saas_api_module, "generate_strategy_and_drafts", lambda **kwargs: fake)
    resp = client.post(
        "/api/create/generate",
        json={
            "mode": "quick",
            "topic": "Тест",
            "offer": "Оффер",
            "language": "ru",
            "tone": "friendly",
            "goal": "sales",
            "platforms": ["facebook"],
            "variants": 1,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    warnings = payload.get("warnings") or []
    assert any("structured_json_failed" in str(w) for w in warnings)
    assert any("simplified_failed" in str(w) for w in warnings)
    assert payload.get("debug_code") == "draft_schema_fallback|draft_text_fallback"




def test_pexels_media_query_uses_caption_meaning_not_cta():
    from backend.services.media.pexels_service import build_media_query

    caption = (
        "Calm cosmetology consultation before treatment. "
        "Sterile tools, skincare steps, soft beauty room. "
        "Write to direct to book today."
    )
    meta = build_media_query(
        niche="cosmetology",
        topic="generic post",
        post_text=caption,
        platform="instagram",
    )
    query_blob = " ".join([meta["primary_query"], *meta["fallback_queries"]]).lower()
    assert "consultation" in query_blob or "treatment" in query_blob or "skincare" in query_blob
    assert "direct" not in query_blob


def test_pexels_media_query_uses_caption_when_topic_generic():
    from backend.services.media.pexels_service import build_media_query

    meta = build_media_query(
        niche="autoservice",
        topic="generic post",
        post_text=(
            "We show engine diagnostics, mechanic tools and a clean service bay "
            "so the client understands how vehicle inspection works."
        ),
        platform="facebook",
    )
    joined = " ".join(meta["topic_terms"]).lower()
    assert "engine" in joined or "mechanic" in joined or "vehicle" in joined



def test_media_resolver_prefers_pexels(monkeypatch):
    import saas_services

    class FakeImage:
        local_url = "https://api.autosocial.tech/api/media/pexels_101.jpg"

    monkeypatch.setattr(saas_services, "fetch_post_image", lambda **kwargs: FakeImage())
    monkeypatch.setattr(
        saas_services,
        "fetch_pixabay_post_image",
        lambda **kwargs: pytest.fail("Pixabay should not be called when Pexels succeeds"),
    )

    assert saas_services._resolve_post_media_url(
        db=None,
        project_id=1,
        platform="instagram",
        topic="skincare consultation",
        category="cosmetology",
        language="ru",
        generated_text="calm skincare consultation",
    ) == "https://api.autosocial.tech/api/media/pexels_101.jpg"


def test_media_resolver_falls_back_to_pixabay(monkeypatch):
    import saas_services

    class FakeImage:
        local_url = "https://api.autosocial.tech/api/media/pixabay_202.jpg"

    def pexels_empty(**kwargs):
        raise saas_services.PexelsEmptyResultError("no pexels image")

    monkeypatch.setattr(saas_services, "fetch_post_image", pexels_empty)
    monkeypatch.setattr(saas_services, "fetch_pixabay_post_image", lambda **kwargs: FakeImage())

    assert saas_services._resolve_post_media_url(
        db=None,
        project_id=1,
        platform="instagram",
        topic="engine diagnostics",
        category="autoservice",
        language="ru",
        generated_text="mechanic checks engine diagnostics",
    ) == "https://api.autosocial.tech/api/media/pixabay_202.jpg"


def test_media_resolver_allows_post_without_image(monkeypatch):
    import saas_services

    def pexels_empty(**kwargs):
        raise saas_services.PexelsEmptyResultError("no pexels image")

    monkeypatch.setattr(saas_services, "fetch_post_image", pexels_empty)
    monkeypatch.setattr(saas_services, "fetch_pixabay_post_image", lambda **kwargs: None)

    assert saas_services._resolve_post_media_url(
        db=None,
        project_id=1,
        platform="instagram",
        topic="rare narrow topic",
        category="unknown",
        language="ru",
        generated_text="rare narrow topic",
    ) is None


def test_openai_image_generation_is_disabled_in_runtime_source():
    from pathlib import Path

    generator_source = Path("gpt_generator.py").read_text(encoding="utf-8")
    assert "client.images.generate" not in generator_source
    assert "build_semantic_fallback_image_url" not in generator_source
    assert "OPENAI_IMAGE_MODEL" not in generator_source
