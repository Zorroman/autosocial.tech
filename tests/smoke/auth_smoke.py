from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
import sys

from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT / "frontend"
REPORT_PATH = ROOT / "tests" / "reports" / "auth-smoke.txt"
sys.path.insert(0, str(ROOT))

from migrations import run_migrations
from saas_api import saas_api
from saas_models import AppUser
from saas_services import seed_niche_hooks, seed_plans, seed_platform_rules
from database import SessionLocal


def check_frontend_root() -> tuple[bool, str]:
    handler = partial(SimpleHTTPRequestHandler, directory=str(FRONTEND_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        req = Request(f"http://127.0.0.1:{port}/", method="GET")
        with urlopen(req, timeout=5) as resp:
            body = resp.read(2048).decode("utf-8", errors="ignore")
            ok = resp.status == 200 and "AutoSocial GPT" in body
            return ok, f"GET / => {resp.status}"
    finally:
        server.shutdown()
        t.join(timeout=1)


def build_test_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(saas_api)
    return app


def run_api_smoke() -> list[str]:
    lines: list[str] = []

    run_migrations()
    seed_plans()
    seed_platform_rules()
    seed_niche_hooks()

    app = build_test_app()
    client = app.test_client()

    ts = int(time.time())
    email = f"smoke_{ts}@autosocial.local"
    password = "smokePass123"

    # register
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    lines.append(f"POST /api/auth/register => {r.status_code}")
    assert r.status_code == 200, r.get_data(as_text=True)
    payload = r.get_json() or {}
    assert payload.get("token"), "register token missing"

    db = SessionLocal()
    try:
        created = db.query(AppUser).filter_by(email=email).first()
        assert created is not None, "user not created in DB"
        lines.append("DB create user => OK")
    finally:
        db.close()

    # duplicate email
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    lines.append(f"POST /api/auth/register duplicate => {r.status_code}")
    assert r.status_code == 409, r.get_data(as_text=True)

    # short password
    r = client.post("/api/auth/register", json={"email": f"short_{ts}@autosocial.local", "password": "123"})
    lines.append(f"POST /api/auth/register short password => {r.status_code}")
    assert r.status_code == 400, r.get_data(as_text=True)

    # login ok
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    lines.append(f"POST /api/auth/login => {r.status_code}")
    assert r.status_code == 200, r.get_data(as_text=True)
    payload = r.get_json() or {}
    assert payload.get("token"), "login token missing"

    # wrong password
    r = client.post("/api/auth/login", json={"email": email, "password": "wrong-pass"})
    lines.append(f"POST /api/auth/login wrong password => {r.status_code}")
    assert r.status_code == 401, r.get_data(as_text=True)

    return lines


def main() -> int:
    report_lines = [f"[{datetime.now().isoformat(timespec='seconds')}] Auth smoke"]

    try:
        ok_front, msg_front = check_frontend_root()
        report_lines.append(f"Frontend {msg_front} => {'OK' if ok_front else 'FAIL'}")
        assert ok_front, msg_front

        api_lines = run_api_smoke()
        report_lines.extend(api_lines)
        report_lines.append("RESULT: PASS")
        code = 0
    except Exception as exc:  # noqa: BLE001
        report_lines.append(f"RESULT: FAIL: {exc}")
        code = 1

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print("\n".join(report_lines))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
