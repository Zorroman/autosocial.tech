#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FRONTEND_BASE = "https://autosocial.tech"
API_CANDIDATES = (
    "https://autosocial.tech/api",
    "https://api.autosocial.tech/api",
)
TIMEOUT_SECONDS = 20

REQUIRED_FRONTEND_MARKERS = [
    "AUTOSOCIAL_RELEASE_MARKER_2026",
    "AUTOSOCIAL_DASHBOARD_QUICKACTIONS_V1",
    "AUTOSOCIAL_CREATE_FLOW_V1",
]

REQUIRED_NICHE_MARKERS = [
    "AUTOSOCIAL_NICHES_CONFIG_V1",
]

FORBIDDEN_FRONTEND_MARKERS = [
    "Upgrade to Pro",
    "Перейти на Pro",
    "Перейти на Light",
    "Pro plan",
]

REQUIRED_PLAN_NAMES = {"free", "starter", "growth", "agency"}
FORBIDDEN_PLAN_NAMES = {"light", "pro", "premium"}

REQUIRED_NICHE_IDS = [
    "smm_marketing",
    "cosmetology",
    "barbershop",
    "autoservice",
    "detailing",
    "apartment_renovation",
    "psychology",
    "consulting",
    "online_courses",
    "fitness",
    "esoterica",
]


@dataclass
class CheckResult:
    ok: bool
    message: str


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "AutoSocialReleaseVerifier/1.0",
            "Accept": "text/plain,application/json,text/html,*/*",
        },
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str) -> object:
    return json.loads(fetch_text(url))


def check_markers(body: str, required: Iterable[str], forbidden: Iterable[str]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for marker in required:
        results.append(CheckResult(marker in body, f"required marker: {marker}"))
    for marker in forbidden:
        results.append(CheckResult(marker not in body, f"legacy marker absent: {marker}"))
    return results


def find_api_base() -> tuple[str | None, str | None]:
    last_error = None
    for candidate in API_CANDIDATES:
        try:
            payload = fetch_json(f"{candidate}/plans")
            if isinstance(payload, list):
                return candidate, None
            last_error = f"{candidate}/plans did not return a list"
        except Exception as exc:  # pragma: no cover - defensive in smoke script
            last_error = f"{candidate}/plans -> {exc}"
    return None, last_error


def extract_plan_names(payload: object) -> set[str]:
    names = set()
    if not isinstance(payload, list):
        return names
    for item in payload:
        if not isinstance(item, dict):
            continue
        value = str(item.get("name") or item.get("code") or "").strip().lower()
        if value:
            names.add(value)
    return names


def print_result(result: CheckResult) -> None:
    use_ascii = os.name == "nt" and "utf" not in str(getattr(sys.stdout, "encoding", "")).lower()
    icon = ("OK" if result.ok else "FAIL") if use_ascii else ("✔" if result.ok else "✘")
    print(f"{icon} {result.message}")


def main() -> int:
    failures = 0

    try:
        app_js = fetch_text(f"{FRONTEND_BASE}/app.js")
    except (HTTPError, URLError) as exc:
        print(f"✘ frontend bundle fetch failed: {exc}")
        return 1

    frontend_results = check_markers(app_js, REQUIRED_FRONTEND_MARKERS, FORBIDDEN_FRONTEND_MARKERS)
    if all(item.ok for item in frontend_results):
        print_result(CheckResult(True, "frontend bundle updated"))
    else:
        print_result(CheckResult(False, "frontend bundle markers mismatch"))
        for item in frontend_results:
            if not item.ok:
                print_result(item)
        failures += 1

    quick_action_markers = ["AUTOSOCIAL_DASHBOARD_QUICKACTIONS_V1", "AUTOSOCIAL_CREATE_FLOW_V1"]
    if all(marker in app_js for marker in quick_action_markers):
        print_result(CheckResult(True, "quick actions detected"))
    else:
        missing = [marker for marker in quick_action_markers if marker not in app_js]
        print_result(CheckResult(False, f"dashboard quick actions missing: {', '.join(missing)}"))
        failures += 1

    try:
        niche_js = fetch_text(f"{FRONTEND_BASE}/data/nicheTemplates.js")
    except (HTTPError, URLError) as exc:
        print(f"✘ nicheTemplates fetch failed: {exc}")
        return 1

    niche_marker_results = check_markers(niche_js, REQUIRED_NICHE_MARKERS, [])
    missing_niches = [niche_id for niche_id in REQUIRED_NICHE_IDS if niche_id not in niche_js]
    if any(not item.ok for item in niche_marker_results):
        print_result(CheckResult(False, "niches config marker missing"))
        for item in niche_marker_results:
            if not item.ok:
                print_result(item)
        failures += 1
    elif missing_niches:
        print_result(CheckResult(False, f"niches missing: {', '.join(missing_niches)}"))
        failures += 1
    else:
        print_result(CheckResult(True, "niches loaded"))
        print_result(CheckResult(True, "esoterica present"))

    try:
        create_html = fetch_text(f"{FRONTEND_BASE}/create/")
    except (HTTPError, URLError) as exc:
        print(f"✘ create flow fetch failed: {exc}")
        return 1

    create_ok = '<div id="app"></div>' in create_html and '/data/nicheTemplates.js' in create_html and '/app.js' in create_html
    if create_ok:
        print_result(CheckResult(True, "create flow shell loaded"))
    else:
        print_result(CheckResult(False, "create flow shell is broken or missing required scripts"))
        failures += 1

    api_base, api_error = find_api_base()
    if not api_base:
        print_result(CheckResult(False, f"plans api unavailable: {api_error}"))
        return 1

    try:
        plans_payload = fetch_json(f"{api_base}/plans")
    except Exception as exc:  # pragma: no cover - defensive in smoke script
        print_result(CheckResult(False, f"plans api fetch failed: {exc}"))
        return 1

    plan_names = extract_plan_names(plans_payload)
    missing_required_plans = sorted(REQUIRED_PLAN_NAMES - plan_names)
    found_forbidden_plans = sorted(plan_names & FORBIDDEN_PLAN_NAMES)
    if missing_required_plans or found_forbidden_plans:
        details = []
        if missing_required_plans:
            details.append(f"missing: {', '.join(missing_required_plans)}")
        if found_forbidden_plans:
            details.append(f"legacy detected: {', '.join(found_forbidden_plans)}")
        print_result(CheckResult(False, f"pricing plans incorrect ({'; '.join(details)})"))
        failures += 1
    else:
        print_result(CheckResult(True, "pricing plans correct"))

    plans_dump = json.dumps(plans_payload, ensure_ascii=False)
    legacy_api_hits = [name for name in FORBIDDEN_PLAN_NAMES if f'"{name}"' in plans_dump.lower()]
    if legacy_api_hits:
        print_result(CheckResult(False, f"legacy plan detected in api: {', '.join(sorted(set(legacy_api_hits)))}"))
        failures += 1
    else:
        print_result(CheckResult(True, "no legacy plans found"))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
