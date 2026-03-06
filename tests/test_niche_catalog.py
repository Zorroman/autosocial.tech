import importlib
import os
import sys

import pytest


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test_niche_catalog.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    os.environ["USE_MOCK_PROVIDERS"] = "true"
    os.environ["SYNC_JOBS"] = "true"
    os.environ["ADMIN_EMAIL"] = "admin@test.local"
    os.environ["ADMIN_PASSWORD"] = "adminpass123"
    os.environ["GOOGLE_CLIENT_ID"] = ""
    os.environ["GOOGLE_CLIENT_SECRET"] = ""
    os.environ["FACEBOOK_APP_ID"] = ""
    os.environ["FACEBOOK_APP_SECRET"] = ""
    os.environ["ENV"] = "development"
    os.environ["SMTP_HOST"] = ""
    os.environ["SMTP_FROM"] = ""

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
        "niche_catalog",
    ]:
        if name in sys.modules:
            del sys.modules[name]

    app_module = importlib.import_module("app")
    with app_module.app.test_client() as test_client:
        yield test_client


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register_and_token(client, email="catalog@test.local", password="pass12345") -> str:
    challenge = client.post("/api/auth/register", json={"email": email, "password": password})
    assert challenge.status_code == 200
    payload = challenge.get_json() or {}
    verify = client.post(
        "/api/auth/verify-code",
        json={"challenge_token": payload.get("challenge_token"), "code": payload.get("dev_code")},
    )
    assert verify.status_code == 200
    body = verify.get_json() or {}
    return str(body.get("token") or "")


def test_niche_catalog_contains_10_niches_and_6_templates_each(client):
    token = _register_and_token(client, "catalog-1@test.local")
    res = client.get("/api/create/niche-catalog", headers=_auth_headers(token))
    assert res.status_code == 200
    body = res.get_json() or {}
    assert body.get("status") == "ok"
    items = body.get("items") or []
    assert len(items) == 10

    expected_slugs = {
        "barbershop",
        "beauty-salon",
        "auto-service",
        "tire-service",
        "tattoo-studio",
        "fitness-trainer",
        "restaurant",
        "cafe",
        "child-education",
        "car-wash",
    }
    actual_slugs = {str(x.get("slug") or "") for x in items}
    assert actual_slugs == expected_slugs

    for niche in items:
        templates = niche.get("templates") or []
        assert len(templates) == 6
        for tpl in templates:
            assert tpl.get("type") in {"post", "video"}
            assert tpl.get("platform") == "all"
            assert tpl.get("goal") in {"leads", "awareness"}
            assert tpl.get("tone") in {"local-friendly", "expert"}
            assert isinstance(tpl.get("hook_line"), str) and tpl.get("hook_line")
            assert isinstance(tpl.get("cta"), str) and tpl.get("cta")
            assert isinstance(tpl.get("prompt_system"), str) and tpl.get("prompt_system")
            assert isinstance(tpl.get("prompt_user"), str) and tpl.get("prompt_user")
            schema = tpl.get("variables_schema_json") or {}
            for key in [
                "business_name",
                "city",
                "offer",
                "usp",
                "price",
                "audience",
                "cta",
                "contact",
                "website",
            ]:
                assert key in schema


def test_import_catalog_template_creates_user_template(client):
    token = _register_and_token(client, "catalog-2@test.local")
    res = client.post(
        "/api/create/templates/import-catalog",
        headers=_auth_headers(token),
        json={"niche_slug": "barbershop", "template_slug": "promo-offer-post"},
    )
    assert res.status_code == 201
    body = res.get_json() or {}
    assert body.get("status") == "ok"
    item = body.get("item") or {}
    assert item.get("name")

    listed = client.get("/api/create/templates", headers=_auth_headers(token))
    assert listed.status_code == 200
    rows = (listed.get_json() or {}).get("items") or []
    assert any("Barbershop" in str(x.get("name") or "") for x in rows)
