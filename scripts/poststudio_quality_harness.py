import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from urllib.parse import urlparse

# Repo root, not scripts/, so sibling top-level modules import cleanly
# regardless of how this script is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from content_pipeline import director_generate_drafts, director_suggest
from openai_client import generate_json_with_retry, is_openai_enabled


try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


ROOT = Path(r"c:\Users\saxgr\Desktop\AutoSocial GPT")
DEFAULT_RULES = ROOT / "tmp_poststudio_quality_rules.json"
DEFAULT_JSON = ROOT / "tmp_poststudio_quality_report.json"
DEFAULT_MD = ROOT / "tmp_poststudio_quality_report.md"
PROFILE_SRC = ROOT / ".chrome-qa-profile"
PROFILE = ROOT / ".chrome-qa-profile-run-quality-harness"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", default=str(DEFAULT_RULES))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    parser.add_argument("--llm-judge", action="store_true")
    return parser.parse_args()


def normalize(text):
    return " ".join(str(text or "").strip().lower().split())


def split_sentences(text):
    raw = str(text or "").replace("\r", "\n").strip()
    if not raw:
        return []
    parts = []
    for chunk in raw.split("\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for part in __import__("re").split(r"(?<=[.!?])\s+", chunk):
            part = " ".join(str(part or "").strip().split())
            if part:
                parts.append(part)
    return parts


def first_sentence(text):
    parts = split_sentences(text)
    return parts[0] if parts else ""


def lexical_overlap(a, b):
    wa = {w for w in __import__("re").findall(r"[\w#]+", normalize(a)) if len(w) >= 4}
    wb = {w for w in __import__("re").findall(r"[\w#]+", normalize(b)) if len(w) >= 4}
    if not wa or not wb:
      return 0.0
    return len(wa & wb) / max(1, len(wa | wb))


def repeated_map(values):
    out = defaultdict(list)
    for idx, value in enumerate(values, start=1):
        key = normalize(value)
        if not key:
            continue
        out[key].append(idx)
    return {k: v for k, v in out.items() if len(v) > 1}


def find_pattern_hits(values, patterns):
    hits = []
    for idx, value in enumerate(values, start=1):
        low = normalize(value)
        matched = [pat for pat in patterns if pat in low]
        if matched:
            hits.append({"index": idx, "text": value, "patterns": matched})
    return hits


def persona_keyword_hits(text_blob, expected_keywords):
    low = normalize(text_blob)
    return [kw for kw in expected_keywords if kw in low]


def forbidden_hits(text_blob, forbidden_phrases):
    low = normalize(text_blob)
    return [kw for kw in forbidden_phrases if kw in low]


def avg_pairwise_overlap(values):
    clean = [v for v in values if normalize(v)]
    if len(clean) < 2:
        return 0.0
    scores = []
    for i in range(len(clean)):
        for j in range(i + 1, len(clean)):
            scores.append(lexical_overlap(clean[i], clean[j]))
    return mean(scores) if scores else 0.0


def distinctness_score(sublines, opening_sentences):
    unique_subline_ratio = len({normalize(x) for x in sublines if normalize(x)}) / max(1, len(sublines))
    unique_opening_ratio = len({normalize(x) for x in opening_sentences if normalize(x)}) / max(1, len(opening_sentences))
    overlap = avg_pairwise_overlap(sublines)
    score = 100 * (0.45 * unique_subline_ratio + 0.35 * unique_opening_ratio + 0.20 * max(0.0, 1.0 - overlap))
    return round(score, 1)


def genericness_score(generic_hits, service_hits, repeated_sublines, repeated_openings):
    penalty = (
        len(generic_hits) * 10
        + len(service_hits) * 16
        + len(repeated_sublines) * 18
        + len(repeated_openings) * 12
    )
    return max(0.0, round(100 - penalty, 1))


def persona_specificity_score(text_blob, expected_keywords, forbidden_phrases):
    hits = persona_keyword_hits(text_blob, expected_keywords)
    forb = forbidden_hits(text_blob, forbidden_phrases)
    hit_ratio = min(1.0, len(hits) / max(3, min(len(expected_keywords), 6)))
    score = (hit_ratio * 100) - (len(forb) * 15)
    return max(0.0, round(score, 1)), hits, forb


def judge_stage(case_payload):
    suggest = case_payload.get("suggest_payload") or {}
    drafts = case_payload.get("draft_payload") or {}
    final_cards = case_payload.get("rendered_day_cards") or []
    final_sublines = [row.get("subline", "") for row in final_cards]
    repeated_final = repeated_map(final_sublines)

    suggest_angles = list((suggest.get("data") or {}).get("angles") or [])
    draft_rows = list((drafts.get("data") or {}).get("drafts") or [])
    draft_openings = [first_sentence(row.get("body_text") or row.get("post_text") or "") for row in draft_rows]
    repeated_draft_openings = repeated_map(draft_openings)

    if repeated_final and len({normalize(x) for x in suggest_angles if normalize(x)}) < len(final_cards):
        return "suggest/angles"
    if repeated_final and repeated_draft_openings:
        return "drafts"
    if repeated_final:
        return "frontend assembly or render extraction"
    return "no visible collapse detected"


def build_markdown(report):
    lines = []
    lines.append("# Post Studio Quality Harness Report")
    lines.append("")
    lines.append(f"- Route: `{report['route']}`")
    lines.append(f"- Cases: `{len(report['cases'])}`")
    lines.append(f"- Overall Verdict: `{report['overall_verdict']}`")
    lines.append("")
    for case in report["cases"]:
        lines.append(f"## {case['case_id']}")
        lines.append(f"- Niche: `{case['label']}`")
        lines.append(f"- Mode: `{case['mode']}`")
        lines.append(f"- Verdict: `{case['verdict']}`")
        lines.append(f"- Distinctness Score: `{case['scores']['distinctness_score']}`")
        lines.append(f"- Genericness Score: `{case['scores']['genericness_score']}`")
        lines.append(f"- Persona Specificity Score: `{case['scores']['persona_specificity_score']}`")
        lines.append(f"- Offer Policy Pass: `{case['scores']['offer_policy_pass']}`")
        if case["repetition"]["repeated_visible_sublines"]:
            lines.append("- Repeated visible sublines:")
            for key, days in case["repetition"]["repeated_visible_sublines"].items():
                lines.append(f"  - `{key}` -> days `{days}`")
        lines.append("- Day cards:")
        for row in case["rendered_day_cards"]:
            lines.append(f"  - Day {row['day']}: {row['topic']} -> {row['subline']}")
        lines.append("")
    return "\n".join(lines)


def llm_judge(case_result):
    if not is_openai_enabled():
        return {"status": "skipped", "reason": "openai_disabled"}
    schema = {
        "distinctness": {"score": 0, "verdict": "string", "reason": "string"},
        "niche_specificity": {"score": 0, "verdict": "string", "reason": "string"},
        "genericness": {"score": 0, "verdict": "string", "reason": "string"},
        "service_leakage": {"verdict": "string", "reason": "string"},
        "overall": {"verdict": "string", "reason": "string"}
    }
    summary = {
        "topics": [x["topic"] for x in case_result["rendered_day_cards"]],
        "sublines": [x["subline"] for x in case_result["rendered_day_cards"]],
        "preview_text": case_result["preview"]["text"],
        "cta": case_result["preview"]["cta"],
        "hashtags": case_result["preview"]["hashtags"],
        "mode": case_result["mode"],
        "expected_keywords": case_result["expected_keywords"],
        "forbidden_phrases": case_result["forbidden_phrases"],
    }
    try:
        out = generate_json_with_retry(
            system_prompt="You are a strict QA judge for Russian niche social content quality. Return JSON only.",
            user_prompt=(
                "Evaluate distinctness across days, niche specificity, genericness, and service leakage. "
                "Be strict and concise.\n"
                f"schema: {json.dumps(schema, ensure_ascii=False)}\n"
                f"case: {json.dumps(summary, ensure_ascii=False)}"
            ),
            validator=lambda payload: None if isinstance(payload, dict) else (_ for _ in ()).throw(ValueError("bad")),
            max_output_tokens=800,
            temperature=0.2,
        )
        return {"status": "ok", "result": out.payload}
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


def valid_stub_response(url):
    if "/api/auth/providers" in url:
        return {"google": {"configured": False}, "facebook": {"configured": False}}
    if "/api/me" in url:
        return {"id": 1, "email": "qa@local.test", "plan": "growth", "billing": {"plan": "growth"}, "role": "user"}
    if "/api/projects" in url:
        return [{"id": 1, "name": "QA Project"}]
    if "/api/connections" in url:
        return []
    if "/api/integrations/youtube/status" in url:
        return {"connected": False}
    if "/api/campaigns?limit=10" in url:
        return {"items": []}
    if "/api/video/style-packs" in url:
        return {"items": [], "default_style_pack": "default_pro"}
    if "/api/create/templates" in url:
        return {"items": []}
    if "/api/ai/best-posting-times" in url:
        slots = [(datetime(2026, 3, 30) + timedelta(days=i)).isoformat() for i in range(30)]
        return {"next_slots": slots, "best_hours": [10, 12, 14, 16, 18, 11, 13]}
    return {}


def build_case_result(case, render_data, suggest_payload, draft_payload, global_rules, console_errors, failed_requests):
    card_topics = [row["topic"] for row in render_data["day_cards"]]
    card_sublines = [row["subline"] for row in render_data["day_cards"]]
    card_texts = [row.get("text", "") for row in render_data["day_cards"]]
    card_ctas = [row.get("cta", "") for row in render_data["day_cards"]]
    opening_sentences = [first_sentence(x) for x in card_texts]

    repeated_sublines = repeated_map(card_sublines)
    repeated_openings = repeated_map(opening_sentences)
    repeated_ctas = repeated_map(card_ctas)
    generic_hits = find_pattern_hits(card_sublines + opening_sentences + [render_data["preview"]["text"]], global_rules["generic_patterns"])
    text_blob = "\n".join(card_topics + card_sublines + card_texts + [render_data["preview"]["text"], render_data["preview"]["cta"]] + render_data["preview"]["hashtags"])
    service_hits = forbidden_hits(text_blob, global_rules["service_leak_terms"] if case["mode"] == "no-offer" else [])
    persona_score, keyword_hits, persona_forbidden = persona_specificity_score(text_blob, case["expected_keywords"], case["forbidden_phrases"])
    distinct_score = distinctness_score(card_sublines, opening_sentences)
    generic_score = genericness_score(generic_hits, service_hits, repeated_sublines, repeated_openings)
    offer_policy_pass = not service_hits if case["mode"] == "no-offer" else True

    if console_errors or failed_requests:
        verdict = "FAIL"
    elif repeated_sublines or len(repeated_openings) >= 2 or not offer_policy_pass:
        verdict = "FAIL"
    elif distinct_score < 75 or generic_score < 70 or persona_score < 45:
        verdict = "PARTIAL PASS"
    else:
        verdict = "PASS"

    out = {
        "case_id": case["case_id"],
        "label": case["label"],
        "mode": case["mode"],
        "offer": case["offer"],
        "expected_keywords": case["expected_keywords"],
        "forbidden_phrases": case["forbidden_phrases"],
        "suggest_payload": suggest_payload,
        "draft_payload": draft_payload,
        "rendered_day_cards": render_data["day_cards"],
        "preview": render_data["preview"],
        "console_errors": console_errors,
        "failed_requests": failed_requests,
        "repetition": {
            "repeated_visible_sublines": repeated_sublines,
            "repeated_opening_sentences": repeated_openings,
            "repeated_cta": repeated_ctas
        },
        "generic_flags": generic_hits,
        "persona": {
            "keyword_hits": keyword_hits,
            "forbidden_hits": persona_forbidden
        },
        "scores": {
            "distinctness_score": distinct_score,
            "genericness_score": generic_score,
            "persona_specificity_score": persona_score,
            "offer_policy_pass": offer_policy_pass
        },
        "degradation_stage": judge_stage({
            "suggest_payload": suggest_payload,
            "draft_payload": draft_payload,
            "rendered_day_cards": render_data["day_cards"]
        }),
        "verdict": verdict
    }
    return out


def main():
    args = parse_args()
    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    route = rules["route"]
    json_out = Path(args.json_out)
    md_out = Path(args.md_out)

    if PROFILE.exists():
        shutil.rmtree(PROFILE)
    shutil.copytree(PROFILE_SRC, PROFILE)

    report = {
        "route": route,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "verification_type": "local browser/runtime with real frontend flow and local backend-function interception",
        "cases": [],
        "overall_verdict": "FAIL"
    }

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(PROFILE), headless=True, viewport={"width": 1440, "height": 1000})
        context.add_init_script("window.localStorage.setItem('token', 'qa-local-token');")
        page = context.new_page()

        current_case = {"case_id": "", "suggest_payload": None, "draft_payload": None}

        def route_handler(route_obj):
            req = route_obj.request
            url = req.url
            if "/api/ai/director/suggest" in url:
                payload = json.loads(req.post_data or "{}")
                out = director_suggest(
                    topic=str(payload.get("topic") or payload.get("niche") or "").strip(),
                    offer=(payload.get("offer") or "").strip() or None,
                    language=str(payload.get("language") or "ru").strip().lower() or "ru",
                    tone=str(payload.get("tone") or "friendly").strip().lower() or "friendly",
                    goal=str(payload.get("goal") or "engagement").strip().lower() or "engagement",
                    platforms=payload.get("platforms") if isinstance(payload.get("platforms"), list) else [],
                    niche_label=str(payload.get("niche_label") or "").strip() or None,
                    niche_context=payload.get("niche_context") if isinstance(payload.get("niche_context"), dict) else None,
                    variation_seed=int(payload.get("variation_seed") or 0),
                )
                body = {
                    "status": out.get("status") or "ok",
                    "data": out.get("data") or {},
                    "warnings": out.get("warnings") or [],
                    "debug_code": out.get("debug_code") or ""
                }
                current_case["suggest_payload"] = body
                return route_obj.fulfill(status=200, content_type="application/json", body=json.dumps(body, ensure_ascii=False))
            if "/api/ai/director/generate-drafts" in url:
                payload = json.loads(req.post_data or "{}")
                out = director_generate_drafts(
                    topic=str(payload.get("topic") or "").strip(),
                    offer=(payload.get("offer") or "").strip() or None,
                    angle=str(payload.get("angle") or "").strip(),
                    goal=str(payload.get("goal") or "engagement").strip().lower() or "engagement",
                    platforms=payload.get("platforms") if isinstance(payload.get("platforms"), list) else [],
                    tone=str(payload.get("tone") or "friendly").strip().lower() or "friendly",
                    language=str(payload.get("language") or "ru").strip().lower() or "ru",
                    niche_label=str(payload.get("niche_label") or "").strip() or None,
                    niche_context=payload.get("niche_context") if isinstance(payload.get("niche_context"), dict) else None,
                    variants=int(payload.get("variants") or 1),
                )
                body = {
                    "status": out.get("status") or "ok",
                    "data": out.get("data") or {},
                    "warnings": out.get("warnings") or [],
                    "debug_code": out.get("debug_code") or ""
                }
                current_case["draft_payload"] = body
                return route_obj.fulfill(status=200, content_type="application/json", body=json.dumps(body, ensure_ascii=False))
            if "/api/" in url:
                return route_obj.fulfill(status=200, content_type="application/json", body=json.dumps(valid_stub_response(url), ensure_ascii=False))
            return route_obj.continue_()

        page.route("**/*", route_handler)

        for case in rules["cases"]:
            console_errors = []
            failed_requests = []

            def on_console(msg):
                if msg.type == "error":
                    console_errors.append(msg.text)

            def on_failed(req):
                failed_requests.append({"url": req.url, "error": req.failure})

            page.on("console", on_console)
            page.on("requestfailed", on_failed)

            current_case["case_id"] = case["case_id"]
            current_case["suggest_payload"] = None
            current_case["draft_payload"] = None

            try:
                page.goto(route, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(2500)
                page.evaluate("() => render()")
                page.wait_for_timeout(700)

                if "/login" in page.url:
                    raise RuntimeError("local route is not authenticated")

                page.locator("#cdTopicPreset").select_option(case["preset"])
                page.locator("#cdOffer").fill(case["offer"])
                page.locator("#cdGoal").select_option(case["goal"])
                page.locator("#cdLang").select_option("ru")
                page.locator("#cdPostStudioDays7").click()
                page.wait_for_timeout(250)
                page.locator("#cdGeneratePostStudioPlan").click(force=True)
                page.wait_for_function("() => document.querySelectorAll('[data-cd-poststudio-day]').length >= 7", timeout=180000)
                page.wait_for_timeout(2500)

                day_cards = page.evaluate(
                    """() => Array.from(document.querySelectorAll('[data-cd-poststudio-day]')).map((btn) => {
                      const lines = (btn.innerText || '').split(/\\n+/).map((x) => x.trim()).filter(Boolean);
                      const decode = (v) => { try { return decodeURIComponent(String(v || '')); } catch { return String(v || ''); } };
                      return {
                        day: Number(btn.getAttribute('data-cd-poststudio-day') || 0) || 0,
                        topic: lines[1] || '',
                        subline: lines[2] || '',
                        text: decode(btn.getAttribute('data-cd-poststudio-text')),
                        cta: decode(btn.getAttribute('data-cd-poststudio-cta')),
                        hashtags: decode(btn.getAttribute('data-cd-poststudio-tags'))
                      };
                    })"""
                )
                preview = {
                    "title": page.locator("#cdPostStudioPreviewTitle").inner_text(timeout=5000).strip(),
                    "text": page.locator("#cdPostStudioPreviewText").inner_text(timeout=5000).strip(),
                    "cta": page.locator("#cdPostStudioPreviewCtaText").inner_text(timeout=5000).strip(),
                    "hashtags": [t.strip() for t in page.locator("#cdPostStudioPreviewTags .pill").all_inner_texts() if t.strip()],
                }
                screenshot_name = f"tmp_poststudio_quality_{case['case_id']}.png"
                page.screenshot(path=str(ROOT / screenshot_name), full_page=True)
                render_data = {
                    "day_cards": day_cards,
                    "preview": preview,
                    "screenshot": screenshot_name,
                }
                case_result = build_case_result(
                    case,
                    render_data,
                    current_case["suggest_payload"] or {},
                    current_case["draft_payload"] or {},
                    rules,
                    console_errors,
                    failed_requests,
                )
                case_result["screenshot"] = screenshot_name
                case_result["llm_judge"] = llm_judge(case_result) if args.llm_judge else {"status": "not_run"}
                report["cases"].append(case_result)
            except PlaywrightTimeoutError as exc:
                report["cases"].append({
                    "case_id": case["case_id"],
                    "label": case["label"],
                    "mode": case["mode"],
                    "offer": case["offer"],
                    "suggest_payload": current_case["suggest_payload"] or {},
                    "draft_payload": current_case["draft_payload"] or {},
                    "rendered_day_cards": [],
                    "preview": {},
                    "console_errors": console_errors,
                    "failed_requests": failed_requests,
                    "repetition": {"repeated_visible_sublines": {}, "repeated_opening_sentences": {}, "repeated_cta": {}},
                    "generic_flags": [],
                    "persona": {"keyword_hits": [], "forbidden_hits": []},
                    "scores": {
                        "distinctness_score": 0.0,
                        "genericness_score": 0.0,
                        "persona_specificity_score": 0.0,
                        "offer_policy_pass": False
                    },
                    "degradation_stage": "harness timeout",
                    "verdict": "FAIL",
                    "error": str(exc),
                    "llm_judge": {"status": "not_run"}
                })
            finally:
                try:
                    page.remove_listener("console", on_console)
                except Exception:
                    pass
                try:
                    page.remove_listener("requestfailed", on_failed)
                except Exception:
                    pass

        context.close()

    verdicts = Counter(case["verdict"] for case in report["cases"])
    if verdicts.get("FAIL"):
        report["overall_verdict"] = "FAIL"
    elif verdicts.get("PARTIAL PASS"):
        report["overall_verdict"] = "PARTIAL PASS"
    else:
        report["overall_verdict"] = "PASS"

    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_out.write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps({
        "json_report": str(json_out),
        "md_report": str(md_out),
        "overall_verdict": report["overall_verdict"],
        "case_verdicts": {case["case_id"]: case["verdict"] for case in report["cases"]}
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
