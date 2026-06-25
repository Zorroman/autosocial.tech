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


def test_registration_routes_through_trial_activation_and_russian_onboarding():
    route_map = _section(APP_JS, "function page(path)", "async function loadDashboardMetrics")
    auth_handler = _section(APP_JS, "const authSubmitBtn", "const authResendBtn")
    trial_page = _section(APP_JS, "function pageTrialActivated()", "function productUsageMeter")
    onboarding = _section(APP_JS, "function onboardingModalHtml()", "function paywallLockCard")
    onboarding_handler = _section(APP_JS, "const bindOnboardingModal", "bindOnboardingModal();")

    assert "'/trial-activated': pageTrialActivated" in route_map
    assert "challenge.flow === 'register' ? '/trial-activated' : '/dashboard'" in auth_handler
    assert _u("0JHQtdGB0L/Qu9Cw0YLQvdGL0Lkg0L/QtdGA0LjQvtC0INCw0LrRgtC40LLQuNGA0L7QstCw0L0=") in trial_page
    assert _u("0JLQsNGIINCx0LXRgdC/0LvQsNGC0L3Ri9C5INC/0LXRgNC40L7QtCDQvdCwIDcg0LTQvdC10Lkg0LDQutGC0LjQstC40YDQvtCy0LDQvQ==") in trial_page
    assert _u("0KHQtdC50YfQsNGBINGB0L7Qt9C00LDQtNC40Lwg0LLQsNGI0Lgg0L/QtdGA0LLRi9C1INC/0YPQsdC70LjQutCw0YbQuNC4INGBINC40LfQvtCx0YDQsNC20LXQvdC40Y/QvNC4Lg==") in trial_page
    assert "trial_days_left" not in trial_page
    assert 'data-link="/dashboard?onboarding=1"' in trial_page
    assert _u("0KHQvtC30LTQsNGC0Ywg0L/QtdGA0LLRi9C1INC/0YPQsdC70LjQutCw0YbQuNC4") in trial_page

    assert "Math.min(2" in onboarding
    assert _u("0JLQsNGI0LAg0L3QuNGI0LA=") in onboarding
    assert _u("0KfRgtC+INC00L7Qu9C20LXQvSDRgdC00LXQu9Cw0YLRjCDQstCw0Ygg0L/QtdGA0LLRi9C5INC/0L7RgdGCPw==") in onboarding
    assert _u("0J/QtdGA0LXQudGC0Lgg0Log0YHQvtC30LTQsNC90LjRjg==") in onboarding
    for forbidden in (
        "First setup",
        "Get your first content plan",
        ">Later<",
        ">Next<",
        ">Back<",
        "Create my first 7-day plan",
        "Preparing your strategy",
    ):
        assert forbidden not in onboarding
    assert "api('/api/onboarding/complete'" in onboarding_handler
    assert "api('/api/onboarding/start'" not in onboarding_handler
    assert "nav('/create/post?first=1'" in onboarding_handler


def test_first_user_dashboard_and_studio_prioritize_first_post_and_image():
    dashboard = _section(APP_JS, "function pageDashboard()", "function pageConnections()")
    studio = _section(APP_JS, "function pageCreateDirector()", "function pageCreatePlanner")

    assert "const isFirstUserDashboard = !hasGeneratedContent && !hasAnalyticsData" in dashboard
    assert 'data-link="/create/post?first=1"' in dashboard
    assert _u("0KHQvtC30LTQsNC50YLQtSDQv9C10YDQstGL0LUg0L/Rg9Cx0LvQuNC60LDRhtC40Lgg0LfQsCDQvNC40L3Rg9GC0YM=") in dashboard
    assert _u("0J/QvtC00LrQu9GO0YfQuNGC0LUg0YHQvtGG0YHQtdGC0LgsINC60L7Qs9C00LAg0LHRg9C00LXRgtC1INCz0L7RgtC+0LLRiyDQv9GD0LHQu9C40LrQvtCy0LDRgtGMLg==") in dashboard

    assert "const isFirstRun" in studio
    assert _u("0KHQvtC30LTQsNGC0Ywg0L/QtdGA0LLRi9C1INC/0YPQsdC70LjQutCw0YbQuNC4") in studio
    assert _u("0J/QtdGA0LLRi9C1IDcg0L/Rg9Cx0LvQuNC60LDRhtC40Lkg0LPQvtGC0L7QstGLIPCfjok=") in studio
    assert _u("0J3QuNC20LUg0L/QvtC60LDQt9Cw0L3QsCDQv9GD0LHQu9C40LrQsNGG0LjRjyDihJYxINC40LcgNy4g0J7RgdGC0LDQu9GM0L3Ri9C1INC00L7RgdGC0YPQv9C90Ysg0LIg0L/QsNC90LXQu9C4Lg==") in studio
    assert _u("0J/Rg9Cx0LvQuNC60LDRhtC40Y8g4oSWMSDQuNC3IDc=") in studio
    assert _u("0JLQsNGIINC/0LXRgNCy0YvQuSDQv9C+0YHRgiDQs9C+0YLQvtCy") not in studio
    assert 'data-link="/dashboard?first_content=ready"' in studio
    assert _u("QUkg0LDQstGC0L7QvNCw0YLQuNGH0LXRgdC60Lgg0L/QvtC00L7QsdGA0LDQuyDQuNC30L7QsdGA0LDQttC10L3QuNC1INC00LvRjyDRjdGC0L7QuSDQv9GD0LHQu9C40LrQsNGG0LjQuC4=") in studio
    assert 'data-image-action="replace"' in studio
    assert _u("4oa7INCX0LDQvNC10L3QuNGC0Ywg0LjQt9C+0LHRgNCw0LbQtdC90LjQtQ==") in studio
    assert 'data-image-action="generate-ai"' in studio
    assert _u("8J+OqCDQodCz0LXQvdC10YDQuNGA0L7QstCw0YLRjCBBSS3QuNC30L7QsdGA0LDQttC10L3QuNC1") in studio
    assert _u("0JjQt9C+0LHRgNCw0LbQtdC90LjQtSDQv9C+0LTQvtCx0YDQsNC90L4g0LjQtyDRhNC+0YLQvtCx0LDQvdC60LAgUGV4ZWxz") not in studio
    assert "GPT" not in _section(studio, "function pageCreateDirector()", "if (isPlanFlow)") if "function pageCreateDirector()" in studio else True


def test_first_user_result_actions_and_dashboard_banner_are_clear():
    dashboard = _section(APP_JS, "function pageDashboard()", "function pageConnections()")
    studio = _section(APP_JS, "function pageCreateDirector()", "function pageCreatePlanner")
    bind_studio = _section(APP_JS, "const genPostStudioPlanBtn", "const postStudioDays7Btn")

    assert _u("0KjQsNCzIDEg0LjQtyAzOiDQkNC90LDQu9C40LfQuNGA0YPQtdC8INC90LjRiNGD") in studio
    assert _u("0KjQsNCzIDIg0LjQtyAzOiDQn9C+0LTQsdC40YDQsNC10Lwg0YLQtdC80Ysg0L/Rg9Cx0LvQuNC60LDRhtC40Lk=") in studio
    assert _u("0KjQsNCzIDMg0LjQtyAzOiDQodC+0LfQtNCw0ZHQvCDQv9GD0LHQu9C40LrQsNGG0LjQuCDQuCDQuNC30L7QsdGA0LDQttC10L3QuNGP") in studio
    assert "const prefix = isFirstRun" in studio
    assert 'data-link="/dashboard?first_content=ready"' in studio
    assert "cdPostStudioGenerate30FirstRun" in studio
    assert _u("0KHQvtC30LTQsNGC0Ywg0LXRidGRIDMwINC/0YPQsdC70LjQutCw0YbQuNC5") in studio
    assert "new URLSearchParams(location.search).get('first') === '1' ? 7" in bind_studio
    assert "cdPostStudioGenerate30FirstRun" in bind_studio
    assert "firstContentReady" in dashboard
    assert _u("0JLQsNGI0Lgg0L/QtdGA0LLRi9C1INC/0YPQsdC70LjQutCw0YbQuNC4INCz0L7RgtC+0LLRiyDwn46J") in dashboard



def test_dashboard_new_user_hides_empty_analytics_and_keeps_one_primary_action():
    dashboard = _section(APP_JS, "function pageDashboard()", "function pageCreate()")
    new_user = _section(dashboard, "if (isFirstUserDashboard)", "const isFirstContentDashboard")

    assert _u("0KHQvtC30LTQsNC50YLQtSDQv9C10YDQstGL0LUg0L/Rg9Cx0LvQuNC60LDRhtC40Lgg0LfQsCDQvNC40L3Rg9GC0YM=") in new_user
    assert _u("0JLRi9Cx0LXRgNC40YLQtSDQvdC40YjRgyDQuCDRhtC10LvRjCDigJQgQXV0b1NvY2lhbCDQv9C+0LTQs9C+0YLQvtCy0LjRgiDRgtC10LrRgdGC0YssINC40LfQvtCx0YDQsNC20LXQvdC40Y8sINGF0LXRiNGC0LXQs9C4INC4INCy0YDQtdC80Y8g0L/Rg9Cx0LvQuNC60LDRhtC40Lgu") in new_user
    assert 'data-link="/create/post?first=1"' in new_user
    assert "recommendationSection" not in new_user
    assert "upcomingSection" not in new_user
    assert "performanceSection" not in new_user
    assert "dashboard_growth_30" not in new_user
    assert "published_posts" not in new_user


def test_dashboard_first_content_success_hero_and_connections_cta():
    dashboard = _section(APP_JS, "function pageDashboard()", "function pageCreate()")
    first_content = _section(dashboard, "if (isFirstContentDashboard)", "const resolveSeries")

    assert _u("0JLQsNGI0Lgg0L/QtdGA0LLRi9C1INC/0YPQsdC70LjQutCw0YbQuNC4INCz0L7RgtC+0LLRiyDwn46J") in first_content
    assert _u("0JLRiyDRg9C20LUg0L/QvtC70YPRh9C40LvQuCDQutC+0L3RgtC10L3RgiDQtNC70Y8g0YHRgtCw0YDRgtCwLiDQotC10L/QtdGA0Ywg0LzQvtC20L3QviDQvtGC0YDQtdC00LDQutGC0LjRgNC+0LLQsNGC0Ywg0L/Rg9Cx0LvQuNC60LDRhtC40LgsINC/0L7QtNC60LvRjtGH0LjRgtGMINGB0L7RhtGB0LXRgtC4INC40LvQuCDRgdC+0LfQtNCw0YLRjCDQtdGJ0ZEu") in first_content
    assert _u("0J7RgtC60YDRi9GC0Ywg0L/Rg9Cx0LvQuNC60LDRhtC40Lg=") in first_content
    assert _u("0J/QvtC00LrQu9GO0YfQuNGC0YwgRmFjZWJvb2s=") in dashboard
    assert _u("0J/QvtC00LrQu9GO0YfQuNGC0YwgSW5zdGFncmFt") in dashboard
    assert _u("0J/QvtC00LrQu9GO0YfQuNGC0YwgWW91VHViZQ==") in dashboard
    assert "upcomingSection" not in first_content
    assert "performanceSection" not in first_content


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
    assert "await buildPostStudioPlan(daysCount)" in bind_studio
    assert "setPostStudioPendingAction('generate')" in bind_studio
    assert "data-link=\"/create/post?mode=plan&days=30\"" in APP_JS
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


def test_auth_challenge_smtp_failure_shows_honest_error_message():
    auth_handler = _section(APP_JS, "const authSubmitBtn", "const authCodeInput")
    assert "email_delivery_failed" in auth_handler
    assert "Не удалось отправить код подтверждения. Попробуйте позже или обратитесь в поддержку." in auth_handler
    assert "let text = raw" in auth_handler
