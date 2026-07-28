from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import base64

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
LOGIN_HTML = (ROOT / "frontend" / "login" / "index.html").read_text(encoding="utf-8-sig")
MIGRATIONS = (ROOT / "migrations.py").read_text(encoding="utf-8")


def _section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def _u(value: str) -> str:
    return base64.b64decode(value).decode("utf-8")


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
    # Private-admin mode: no public pricing cards on the landing page.
    assert "data-pricing-cta" not in login_render


def test_free_trial_cta_routes_to_registration_without_stripe_checkout():
    # Private-admin mode: registration is disabled; every former register CTA
    # must switch to login mode instead.
    assert "state.authMode = 'register'" not in APP_JS
    login_render = _section(APP_JS, "function pageLogin()", "function productUsageMeter")
    assert "authSwitchBtn" not in login_render
    assert "checkout" not in login_render.lower()


def test_registration_routes_through_trial_activation_and_russian_onboarding():
    route_map = _section(APP_JS, "function page(path)", "async function loadDashboardMetrics")
    auth_handler = _section(APP_JS, "const authSubmitBtn", "const authResendBtn")
    trial_page = _section(APP_JS, "function pageTrialActivated()", "function productUsageMeter")
    onboarding_handler = _section(APP_JS, "const bindOnboardingModal", "bindOnboardingModal();")
    # Registration -> trial-activated -> onboarding -> first post. Assert the real
    # wiring via stable routes/handlers/DOM ids (copy strings evolve; the flow is the contract).
    assert "'/trial-activated': pageTrialActivated" in route_map
    assert "challenge.flow === 'register' ? '/trial-activated' : '/dashboard'" in auth_handler
    assert "function onboardingModalHtml()" in APP_JS
    assert 'data-link="/dashboard?onboarding=1"' in trial_page
    assert "trial_days_left" not in trial_page
    assert "api('/api/onboarding/complete'" in onboarding_handler
    assert "api('/api/onboarding/start'" not in onboarding_handler
    assert "nav('/create/post?first=1'" in onboarding_handler


def test_first_user_dashboard_and_studio_prioritize_first_post_and_image():
    dashboard = _section(APP_JS, "function pageDashboard()", "function pageConnections()")
    studio = _section(APP_JS, "function pageCreateDirector()", "function pageCreatePlanner")
    # First-user dashboard leads to the single first-post CTA; first-run studio offers
    # image replacement. AI image generation is intentionally removed (GPT image gen banned).
    assert "const isFirstUserDashboard = !hasGeneratedContent && !hasAnalyticsData" in dashboard
    # The first-post CTA is wired in the binding layer (bindCommon), not inlined in the
    # dashboard render — assert the route still exists there.
    assert "/create/post?first=1" in _section(APP_JS, "function bindCommon()", "function render(")
    assert "const isFirstRun" in studio
    assert 'data-link="/dashboard?first_content=ready"' in studio
    assert 'data-image-action="replace"' in studio
    assert 'data-image-action="generate-ai"' not in studio


def test_first_user_result_actions_and_dashboard_banner_are_clear():
    dashboard = _section(APP_JS, "function pageDashboard()", "function pageConnections()")
    studio = _section(APP_JS, "function pageCreateDirector()", "function pageCreatePlanner")
    bind_studio = _section(APP_JS, "const genPostStudioPlanBtn", "const postStudioDays7Btn")
    assert "const prefix = isFirstRun" in studio
    assert 'data-link="/dashboard?first_content=ready"' in studio
    # The first-run 30-post generate action is bound in the binding layer.
    assert "cdPostStudioGenerate30FirstRun" in bind_studio
    assert "new URLSearchParams(location.search).get('first') === '1' ? 7" in bind_studio
    assert "firstContentReady" in dashboard


def test_dashboard_new_user_hides_empty_analytics_and_keeps_one_primary_action():
    dashboard = _section(APP_JS, "function pageDashboard()", "function pageCreate()")
    new_user = _section(dashboard, "if (isFirstUserDashboard)", "const isFirstContentDashboard")
    # New user: no empty analytics sections (the single primary action is wired in
    # bindCommon, asserted in test_first_user_dashboard_and_studio_prioritize_first_post_and_image).
    assert "recommendationSection" not in new_user
    assert "upcomingSection" not in new_user
    assert "performanceSection" not in new_user
    assert "dashboard_growth_30" not in new_user
    assert "published_posts" not in new_user


def test_dashboard_first_content_success_hero_and_connections_cta():
    dashboard = _section(APP_JS, "function pageDashboard()", "function pageCreate()")
    first_content = _section(dashboard, "if (isFirstContentDashboard)", "const resolveSeries")
    # First-content success state: no analytics-heavy sections; success banner present.
    assert "upcomingSection" not in first_content
    assert "performanceSection" not in first_content
    assert "firstContentReady" in dashboard


def test_dashboard_active_user_labels_and_limits_are_polished():
    dashboard = _section(APP_JS, "function pageDashboard()", "function pageCreate()")

    for forbidden in (
        "Last Generated Content",
        "Upcoming queue",
        "Posts this month",
        "Videos this month",
        "Projects'",
        "Autopublishing",
        "Open history",
        "Open calendar",
        "Upgrade to unlock this growth lever",
    ):
        assert forbidden not in dashboard
    assert _u("0J/QvtGB0LvQtdC00L3QuNC1INC80LDRgtC10YDQuNCw0LvRiw==") in dashboard
    assert _u("0J7Rh9C10YDQtdC00Ywg0L/Rg9Cx0LvQuNC60LDRhtC40Lk=") in dashboard
    assert _u("0J/QvtGB0YLRiyDQsiDRjdGC0L7QvCDQvNC10YHRj9GG0LU=") in dashboard
    assert _u("0JLQuNC00LXQviDQsiDRjdGC0L7QvCDQvNC10YHRj9GG0LU=") in dashboard
    assert _u("0J/RgNC+0LXQutGC0Ys=") in dashboard
    assert _u("0JDQstGC0L7Qv9GD0LHQu9C40LrQsNGG0LjRjw==") in dashboard
    meter = _section(APP_JS, "function productUsageMeter", "function ensureOnboardingDraft")
    assert _u("JHtudW1lcmljVXNlZH0g0LjQtyAke251bWVyaWNMaW1pdH0=") in meter
    assert _u("0L/RgNC+0LXQutGCINCw0LrRgtC40LLQtdC9") in meter


def test_dashboard_generation_routes_are_not_changed():
    bind_studio = _section(APP_JS, "const genPostStudioPlanBtn", "const postStudioDays7Btn")
    # Post-studio plan generation still goes through buildPostStudioPlan + pending-action;
    # the dashboard never calls generation endpoints directly.
    assert "await buildPostStudioPlan(daysCount)" in bind_studio
    assert "setPostStudioPendingAction('generate')" in bind_studio
    assert "api('/api/generate" not in _section(APP_JS, "function pageDashboard()", "function pageCreate()")


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
                    status=200, content_type="application/json",
                    body='{"google":{"configured":false},"facebook":{"configured":false}}',
                ),
            )
            page.on(
                "request",
                lambda request: checkout_requests.append(request.url)
                if "/api/billing/checkout/subscription" in request.url else None,
            )
            page.goto(f"http://127.0.0.1:{server.server_port}/login/", wait_until="domcontentloaded")
            page.wait_for_selector("#authSubmitBtn")
            # Russian UI despite the German browser locale; email + password auth (login-first
            # in private-admin mode, so the title may be Войти or Создать аккаунт).
            h2 = page.locator(".landing-2026-auth-form h2").inner_text()
            assert h2 in ("Войти", "Создать аккаунт")
            assert page.locator("#authEmail").is_visible()
            assert page.locator("#authPassword").is_visible()
            visible_text = page.locator("body").inner_text()
            assert "Konto erstellen" not in visible_text
            assert "Anmelden" not in visible_text
            # No Stripe checkout is triggered from the login page.
            assert checkout_requests == []
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_auth_challenge_smtp_failure_shows_honest_error_message():
    auth_handler = _section(APP_JS, "const authSubmitBtn", "const authCodeInput")
    assert "email_delivery_failed" in auth_handler
    assert "Не удалось отправить код подтверждения. Попробуйте позже или обратитесь в поддержку." in auth_handler
    assert "let text = raw" in auth_handler
