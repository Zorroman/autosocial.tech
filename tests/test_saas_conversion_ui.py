from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
LOGIN_HTML = (ROOT / "frontend" / "login" / "index.html").read_text(encoding="utf-8-sig")
MIGRATIONS = (ROOT / "migrations.py").read_text(encoding="utf-8")


def _section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_login_defaults_to_document_russian_before_browser_locale():
    state_init = _section(APP_JS, "const state = {", "authMode: 'register'")
    assert '<html lang="ru">' in LOGIN_HTML
    assert "normalizeLang(document.documentElement.getAttribute('lang'))" in state_init
    assert state_init.index("document.documentElement") < state_init.index("detectBrowserLang()")
    assert "form_title_register: 'Создать аккаунт'" in APP_JS
    assert "auth_hint_default: 'Введите email и пароль." in APP_JS


def test_login_form_and_pricing_have_no_broken_conditional_text():
    login_render = _section(APP_JS, "function pageLogin()", "function productUsageMeter")
    assert "field('authEmail'" in login_render
    assert "field('authPassword'" in login_render
    assert "? '\\u0431\\u0435\\u0437 \\u043b\\u0438\\u043c\\u0438\\u0442\\u0430'" not in login_render
    assert "data-pricing-cta=\"${p.key}\"" in login_render


def test_free_trial_cta_routes_to_registration_without_stripe_checkout():
    pricing_handler = _section(
        APP_JS,
        "document.querySelectorAll('[data-pricing-cta]')",
        "const authBackBtn",
    )
    free_branch = _section(pricing_handler, "if (plan === 'free')", "nav('/billing')")
    assert "state.authMode = 'register'" in free_branch
    assert "render()" in free_branch
    assert "focusAuthEmail()" in free_branch
    assert "checkout" not in free_branch.lower()


def test_postgres_migration_keeps_datetime_compatibility_hotfix():
    assert 'engine.dialect.name == "postgresql" and ddl_type == "DATETIME"' in MIGRATIONS
    assert 'ddl_type = "TIMESTAMP"' in MIGRATIONS


def test_login_renders_russian_and_free_trial_opens_registration():
    sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT / "frontend"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checkout_requests = []

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Exception as exc:
                pytest.skip(f"Playwright Chromium is unavailable: {exc}")
            page = browser.new_page(locale="de-DE")
            page.add_init_script("localStorage.clear()")
            page.route(
                "**/api/auth/providers",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"google":{"configured":false},"facebook":{"configured":false}}',
                ),
            )
            page.on(
                "request",
                lambda request: checkout_requests.append(request.url)
                if "/api/billing/checkout/subscription" in request.url
                else None,
            )
            page.goto(f"http://127.0.0.1:{server.server_port}/login/", wait_until="domcontentloaded")
            page.wait_for_selector("#authSubmitBtn")

            assert page.locator(".landing-2026-auth-form h2").inner_text() == "Создать аккаунт"
            assert "Введите email и пароль" in page.locator(".mobile-microcopy").inner_text()
            assert page.locator("#authEmail").is_visible()
            assert page.locator("#authPassword").is_visible()
            visible_text = page.locator("body").inner_text()
            assert "Konto erstellen" not in visible_text
            assert "? 'без лимита'" not in visible_text

            page.locator('[data-pricing-cta="free"]').click()
            page.wait_for_selector("#authEmail:focus")
            assert page.locator(".landing-2026-auth-form h2").inner_text() == "Создать аккаунт"
            assert checkout_requests == []
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
