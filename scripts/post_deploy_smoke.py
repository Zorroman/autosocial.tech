"""Post-deploy smoke: real HTTP checks against a deployed instance.

Usage:
    python scripts/post_deploy_smoke.py --api https://api-dev.autosocial.tech \
        --front https://dev.autosocial.tech

Auth: set SMOKE_EMAIL + SMOKE_PASSWORD (allowlisted admin; requires
ALLOW_ADMIN_DIRECT_LOGIN=true on the target) or SMOKE_TOKEN with a valid
session token. Without credentials only unauthenticated checks run and the
script exits non-zero, честно reporting what was skipped.
Exit code 0 = all executed checks passed.
"""
import argparse
import os
import sys

import requests

TIMEOUT = 20


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.getenv("SMOKE_API", "http://localhost:5000"))
    parser.add_argument("--front", default=os.getenv("SMOKE_FRONT", "http://localhost:3000"))
    args = parser.parse_args()
    api, front = args.api.rstrip("/"), args.front.rstrip("/")

    failures: list[str] = []
    passed: list[str] = []

    def check(name, fn):
        try:
            fn()
            passed.append(name)
            print(f"  OK   {name}")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"  FAIL {name}: {str(exc)[:160]}")

    def expect(resp, code=200):
        if resp.status_code != code:
            raise AssertionError(f"HTTP {resp.status_code} (expected {code})")
        return resp

    print("== unauthenticated ==")
    check("health", lambda: expect(requests.get(f"{api}/api/health", timeout=TIMEOUT)))
    check("register blocked (403)", lambda: expect(
        requests.post(f"{api}/api/auth/register",
                      json={"email": "smoke@invalid.local", "password": "password123"}, timeout=TIMEOUT), 403))
    check("protected api anonymous (401)", lambda: expect(
        requests.get(f"{api}/api/channels", timeout=TIMEOUT), 401))
    for page in ("/login/", "/dashboard/", "/channels/", "/projects/",
                 "/publications/", "/factory-analytics/", "/factory-settings/"):
        check(f"front {page}", lambda p=page: expect(requests.get(f"{front}{p}", timeout=TIMEOUT)))

    token = (os.getenv("SMOKE_TOKEN") or "").strip()
    email = (os.getenv("SMOKE_EMAIL") or "").strip()
    password = os.getenv("SMOKE_PASSWORD") or ""
    if not token and email and password:
        def _login():
            nonlocal token
            r = expect(requests.post(f"{api}/api/auth/login",
                                     json={"email": email, "password": password}, timeout=TIMEOUT))
            token = (r.json() or {}).get("token") or ""
            if not token:
                raise AssertionError("login returned no token (direct login disabled?)")
        print("== login ==")
        check("admin login", _login)

    if token:
        h = {"Authorization": f"Bearer {token}"}
        print("== authenticated ==")
        check("dashboard api", lambda: expect(requests.get(f"{api}/api/factory-dashboard", headers=h, timeout=TIMEOUT)))
        check("channels api", lambda: expect(requests.get(f"{api}/api/channels", headers=h, timeout=TIMEOUT)))
        check("projects api", lambda: expect(requests.get(f"{api}/api/video-projects", headers=h, timeout=TIMEOUT)))
        check("render queue api", lambda: expect(requests.get(f"{api}/api/render-jobs", headers=h, timeout=TIMEOUT)))
        check("publications api", lambda: expect(requests.get(f"{api}/api/publications", headers=h, timeout=TIMEOUT)))
        check("analytics api", lambda: expect(requests.get(f"{api}/api/analytics/channels?period=30", headers=h, timeout=TIMEOUT)))
        check("costs api", lambda: expect(requests.get(f"{api}/api/analytics/costs", headers=h, timeout=TIMEOUT)))

        def _readiness():
            r = requests.get(f"{api}/api/readiness", headers=h, timeout=TIMEOUT)
            if r.status_code not in (200, 503):
                raise AssertionError(f"HTTP {r.status_code}")
            status = (r.json() or {}).get("status")
            if status == "not_ready":
                raise AssertionError("readiness=not_ready")
            print(f"       readiness status: {status}")
        check("readiness (settings)", _readiness)
    else:
        failures.append("authenticated checks skipped: no SMOKE_TOKEN / SMOKE_EMAIL+SMOKE_PASSWORD")
        print("SKIPPED authenticated checks: no credentials provided")

    print(f"\n{len(passed)} passed, {len(failures)} failed")
    for f in failures:
        print(f"  - {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
