import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FRONT_DIR = ROOT / "frontend"
ART_DIR = ROOT / "tests" / "artifacts"
REPORT_DIR = ROOT / "tests" / "reports" / "playwright"
ART_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:3000")
EXPECTED_REDIRECT = os.getenv("E2E_EXPECTED_META_REDIRECT", "https://api-dev.autosocial.tech/api/integrations/meta/callback")


@contextmanager
def local_front_server():
    cmd = [sys.executable, "-m", "http.server", "3000", "--directory", str(FRONT_DIR)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


def make_mocks(page, status: str = "not_connected"):
    page.route("**/api/me", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"id": 1, "email": "qa@autosocial.tech", "role": "admin", "plan": "growth"})))
    page.route("**/api/billing/summary", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({
        "plan": "growth",
        "usage": {"posts_per_month": 0, "videos_per_month": 0, "projects": 1, "daily_posts": 0},
        "limits": {"posts_per_month": 600, "videos_per_month": 40, "projects": 5, "daily_posts": 60, "can_schedule": True, "can_autopublish": True, "monthly_credits": 1800000, "analytics_level": "advanced"},
        "credits_left": 1800000,
        "approx_posts_left": 600,
    })))

    conn = {
        "id": 123,
        "provider": "meta",
        "status": status,
        "status_reason_code": "no_pages" if status == "connected_need_page" else None,
        "status_help_text": "Выберите рабочую Facebook Page для публикаций." if status == "connected_need_page" else "Подключите аккаунт.",
        "primary_action": {"action": "pick_page", "label": "Выбрать страницу"} if status == "connected_need_page" else {"action": "connect", "label": "Подключить Facebook"},
        "facebook_page_id": None,
        "facebook_page_name": None,
        "instagram_business_id": None,
        "instagram_username": None,
        "meta_redirect_uri": EXPECTED_REDIRECT,
        "tech_log": json.dumps({"status": status, "meta_redirect_uri": EXPECTED_REDIRECT}, ensure_ascii=False),
    }

    page.route("**/api/connections", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps([conn], ensure_ascii=False)))
    page.route("**/api/projects", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps([{"id": 1, "name": "QA Project", "created_at": "2026-02-16T00:00:00", "posts_count": 0}])))
    page.route("**/api/posts", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
    page.route("**/api/plans", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))

    oauth_url = f"https://www.facebook.com/v20.0/dialog/oauth?client_id=9696886733725672&redirect_uri={quote(EXPECTED_REDIRECT, safe='')}&scope=pages_show_list%2Cpages_read_engagement%2Cinstagram_basic%2Cbusiness_management&state=user_1"
    page.route("**/api/integrations/meta/connect", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"oauth_url": oauth_url, "redirect_uri": EXPECTED_REDIRECT})))
    page.route("**/api/integrations/meta/pages**", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"pages": [
        {"page_id": "111", "page_name": "QA Page 1", "page_picture_url": None, "ig_user_id": "ig-111", "ig_username": "qa_ig_1", "has_ig": True, "already_connected": False},
        {"page_id": "222", "page_name": "QA Page 2", "page_picture_url": None, "ig_user_id": None, "ig_username": None, "has_ig": False, "already_connected": False},
    ]})))


def run():
    results = []

    with local_front_server():
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # A
            page = browser.new_page()
            page.add_init_script("localStorage.setItem('token','qa-token')")
            make_mocks(page, "not_connected")
            page.goto(f"{BASE_URL}/connections", wait_until="domcontentloaded")
            page.wait_for_timeout(900)
            ok = page.locator("button.btn.btn-primary").count() > 0
            page.screenshot(path=str(ART_DIR / "connections-a-open.png"), full_page=True)
            results.append(("A: кнопка Подключить Facebook", ok, page.url))
            page.close()

            # B
            page = browser.new_page()
            page.add_init_script("localStorage.setItem('token','qa-token')")
            make_mocks(page, "not_connected")
            page.goto(f"{BASE_URL}/connections", wait_until="domcontentloaded")
            page.click("#connectMetaBtn")
            page.wait_for_timeout(1500)
            enc1 = quote(EXPECTED_REDIRECT, safe="")
            enc2 = quote(enc1, safe="")
            ok = (
                ("facebook.com/v20.0/dialog/oauth" in page.url or "facebook.com/login.php" in page.url)
                and (EXPECTED_REDIRECT in page.url or enc1 in page.url or enc2 in page.url)
            )
            page.screenshot(path=str(ART_DIR / "connections-b-oauth.png"), full_page=True)
            results.append(("B: OAuth URL содержит redirect_uri api-dev", ok, page.url))
            page.close()

            # C
            page = browser.new_page()
            page.add_init_script("localStorage.setItem('token','qa-token')")
            make_mocks(page, "connected_need_page")
            page.goto(f"{BASE_URL}/connections", wait_until="domcontentloaded")
            page.click('button:has-text("Выбрать страницу")')
            page.wait_for_timeout(600)
            ok = page.locator('text=Выбор Facebook Page').is_visible() and page.locator('text=QA Page 1').is_visible()
            page.screenshot(path=str(ART_DIR / "connections-c-picker.png"), full_page=True)
            results.append(("C: модалка выбора страниц", ok, page.url))
            page.close()

            # D
            page = browser.new_page()
            page.add_init_script("localStorage.setItem('token','qa-token')")
            make_mocks(page, "connected_need_page")
            page.goto(f"{BASE_URL}/connections", wait_until="domcontentloaded")
            page.click('summary:has-text("Детали")')
            page.wait_for_timeout(400)
            txt = page.locator('[data-testid="meta-redirect-uri"]').inner_text()
            ok = EXPECTED_REDIRECT in txt
            page.screenshot(path=str(ART_DIR / "connections-d-details.png"), full_page=True)
            results.append(("D: в Деталях есть META_REDIRECT_URI", ok, txt))
            page.close()

            browser.close()

    report_path = REPORT_DIR / "index.html"
    rows = []
    for name, ok, info in results:
        rows.append(f"<tr><td>{name}</td><td>{'PASS' if ok else 'FAIL'}</td><td><code>{info}</code></td></tr>")
    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>AutoSocial E2E Report</title>
<style>body{{font-family:Arial,sans-serif;padding:20px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:8px;text-align:left}}.ok{{color:green}}.bad{{color:red}}</style></head>
<body>
<h1>AutoSocial E2E Report</h1>
<p>Base URL: <code>{BASE_URL}</code></p>
<p>Expected META redirect: <code>{EXPECTED_REDIRECT}</code></p>
<table>
<thead><tr><th>Scenario</th><th>Result</th><th>Details</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<p>Artifacts: <code>{ART_DIR}</code></p>
</body></html>"""
    report_path.write_text(html, encoding="utf-8")

    failed = [r for r in results if not r[1]]
    print(f"Report: {report_path}")
    if failed:
        for r in failed:
            print("FAILED:", r[0], r[2])
        raise SystemExit(1)


if __name__ == "__main__":
    run()
