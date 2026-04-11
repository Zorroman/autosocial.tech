import json
import logging
import os
import random
import re
import subprocess
import smtplib
import ssl
import hashlib
import hmac
import base64
from pathlib import Path
from urllib.parse import quote
from urllib.parse import urlsplit
import secrets
import time
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from email.message import EmailMessage

import requests
from flask import Blueprint, current_app, g, jsonify, redirect, request, send_from_directory
from sqlalchemy import text

from dashboard_metrics import (
    dashboard_ai_score,
    dashboard_forecast,
    dashboard_insights,
    dashboard_recent,
    dashboard_summary,
    dashboard_timeseries,
    sync_dashboard_metrics_for_user,
)
from database import SessionLocal
from facebook_api import (
    exchange_code_for_token,
    get_page_and_ig_id,
    list_pages,
    publish_to_facebook,
    publish_to_instagram,
)
from backend.services.media.pexels_service import (
    PexelsConfigError,
    PexelsEmptyResultError,
    PexelsRateLimitError,
    PexelsRequestError,
    fetch_post_image,
)
from gpt_generator import build_semantic_fallback_image_url, generate_structured_text_with_usage
from plans_catalog import all_public_plan_specs, get_plan_spec, normalize_plan_code, to_plan_payload
from content_pipeline import (
    OpenAIClientError,
    director_generate_drafts,
    director_suggest,
    generate_quick_suggestions,
    generate_strategy_and_drafts,
    rewrite_caption_safe,
)
from saas_auth import create_token, hash_password, require_auth, require_role, verify_password
from saas_models import (
    AuthEmailChallenge,
    AppUser,
    BlogPost,
    ContentPlan,
    CreditLedger,
    NicheHook,
    PaymentEvent,
    Plan,
    PlatformRule,
    Post,
    Campaign,
    CampaignAsset,
    CampaignDelivery,
    ContentBrief,
    ContentItem,
    ContentMetricDaily,
    ContentDraft,
    ContentStrategy,
    Niche,
    Project,
    GenerationJob,
    Subscription,
    Template,
    UsageCounter,
    UsageEvent,
    UserTemplate,
    UserStylePref,
    SocialAccount,
    SystemLog,
    TopicSuggestion,
)
from services.entitlements import (
    ACTION_ANALYTICS_ADVANCED,
    ACTION_ACCOUNT_CONNECT,
    ACTION_POST_GENERATE,
    ACTION_POST_PUBLISH,
    ACTION_PROJECT_CREATE,
    ACTION_SCHEDULE_CREATE,
    ACTION_VIDEO_GENERATE,
    ACTION_VIDEO_PUBLISH,
    authorizeAction,
    getEntitlementsPayload,
    recordUsageEvent,
    sync_subscription_state,
)
from saas_services import (
    CREDIT_PACKS,
    can_access_project,
    check_project_limit,
    create_post_and_charge,
    generate_post_preview_text,
    create_daily_blog_post,
    create_monthly_content_plan,
    materialize_content_plan,
    decrypt_meta_token,
    encrypt_meta_token,
    ensure_user_plan_and_credits,
    get_billing_summary,
    get_or_create_default_project,
    get_revenue_metrics,
    get_topic_suggestions,
    list_blog_posts,
    log_event,
    run_due_content_plan,
    seed_plans,
)
from saas_settings import settings
from style_packs import DEFAULT_STYLE_PACK_ID, get_style_pack, list_style_packs
from stripe_service import (
    create_credit_pack_checkout,
    create_portal_link,
    create_subscription_checkout,
    process_stripe_event,
    verify_and_construct_event,
)
from video_pipeline import generate_video_job_payload
from video_script_generator import generate as generate_video_structure

saas_api = Blueprint("saas_api", __name__, url_prefix="/api")
OAUTH_STATES = {}
OAUTH_STATE_TTL_SECONDS = 600
MEDIA_DIR = Path(__file__).resolve().with_name("generated_media")
MEDIA_DIR.mkdir(exist_ok=True)
LEGACY_MEDIA_DIR = MEDIA_DIR
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
AUTH_CODE_TTL_SECONDS = max(120, int(os.getenv("AUTH_CODE_TTL_SECONDS", "600")))
AUTH_CODE_COOLDOWN_SECONDS = max(10, int(os.getenv("AUTH_CODE_COOLDOWN_SECONDS", "45")))
AUTH_MAX_VERIFY_ATTEMPTS = max(3, int(os.getenv("AUTH_MAX_VERIFY_ATTEMPTS", "5")))
AUTH_RATE_WINDOW_SECONDS = max(60, int(os.getenv("AUTH_RATE_WINDOW_SECONDS", "900")))
AUTH_RATE_MAX_PER_IP = max(5, int(os.getenv("AUTH_RATE_MAX_PER_IP", "25")))
AUTH_RATE_MAX_PER_EMAIL = max(3, int(os.getenv("AUTH_RATE_MAX_PER_EMAIL", "8")))
AUTH_CODE_PEPPER = os.getenv("AUTH_CODE_PEPPER", "autosocial-auth-code")
YOUTUBE_SHORT_MIN_SECONDS = 15
YOUTUBE_SHORT_MAX_SECONDS = 70
YOUTUBE_LONG_MIN_SECONDS = 120
YOUTUBE_LONG_MAX_SECONDS = 480


def _ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "")


def _auth_code_hash(challenge_token: str, code: str) -> str:
    payload = f"{challenge_token}:{code}:{AUTH_CODE_PEPPER}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _summarize_director_warnings(raw_warnings) -> list[str]:
    if not isinstance(raw_warnings, list):
        return []
    # Technical fallback details are useful in logs/debug_code, but noisy in UX.
    hidden_codes = {
        "structured_json_failed",
        "simplified_failed",
        "hard_fallback_default",
        "simplified_schema_used",
        "free_text_parsed",
    }
    mapping = {
        "network_fallback": "Сеть нестабильна: показаны локальные варианты для редактирования.",
        "openai_quota_exceeded": "Лимит GPT исчерпан: пополните OpenAI billing, чтобы получать новые AI-варианты.",
    }
    out: list[str] = []
    seen = set()
    for item in raw_warnings:
        key = str(item or "").strip()
        if not key:
            continue
        if key in hidden_codes:
            continue
        msg = mapping.get(key)
        if not msg:
            low = key.lower()
            if ("full-schema" in low) or ("simplified" in low and "режим" not in low) or ("fallback" in low):
                continue
            if len(key) > 160:
                continue
            msg = key
        if msg not in seen:
            seen.add(msg)
            out.append(msg)
    return out[:2]


def _send_auth_email_code(email: str, code: str, flow: str, ip_addr: str, challenge_token: str) -> bool:
    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    smtp_from = (os.getenv("SMTP_FROM") or "").strip()
    if not smtp_host or not smtp_from:
        return False

    smtp_port = int((os.getenv("SMTP_PORT") or "587").strip())
    smtp_user = (os.getenv("SMTP_USER") or "").strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or "").strip()
    smtp_use_ssl = (os.getenv("SMTP_USE_SSL") or "false").strip().lower() in {"1", "true", "yes"}
    smtp_use_starttls = (os.getenv("SMTP_USE_STARTTLS") or "true").strip().lower() in {"1", "true", "yes"}
    app_name = (os.getenv("APP_NAME") or "AutoSocial GPT").strip()
    action_text = "входа" if flow == "login" else "регистрации"
    ttl_min = max(1, AUTH_CODE_TTL_SECONDS // 60)

    message = EmailMessage()
    message["Subject"] = f"{app_name}: код подтверждения"
    message["From"] = smtp_from
    message["To"] = email
    message.set_content(
        f"Код для {action_text}: {code}\n"
        f"Срок действия: {ttl_min} минут.\n"
        "Если это были не вы, просто проигнорируйте письмо."
    )

    context = ssl.create_default_context()
    if smtp_use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=10) as smtp:
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            if smtp_use_starttls:
                smtp.starttls(context=context)
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)

    log_event("auth_code_email_sent", context=f"flow={flow};email={email};ip={ip_addr}")
    return True


def _current_user_refetched() -> AppUser:
    db = SessionLocal()
    try:
        return db.query(AppUser).filter_by(id=g.current_user.id).first()
    finally:
        db.close()


def _paywall_response_if_needed(authz: dict | None):
    if not authz:
        return None
    if authz.get("allowed", False):
        return None
    payload = authz.get("error_payload") or {"error": "PAYWALL_LIMIT", "message": "Требуется апгрейд тарифа."}
    return jsonify(payload), int(authz.get("http_status") or 402)


def _get_user_style_pref(db, user_id: int) -> str:
    row = db.query(UserStylePref).filter_by(user_id=user_id).first()
    if not row:
        return DEFAULT_STYLE_PACK_ID
    return str(row.default_style_pack or DEFAULT_STYLE_PACK_ID).strip().lower() or DEFAULT_STYLE_PACK_ID


def _set_user_style_pref(db, user_id: int, style_pack_id: str) -> str:
    normalized = get_style_pack(style_pack_id).get("id") or DEFAULT_STYLE_PACK_ID
    row = db.query(UserStylePref).filter_by(user_id=user_id).first()
    if not row:
        row = UserStylePref(
            user_id=user_id,
            default_style_pack=normalized,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
    else:
        row.default_style_pack = normalized
        row.updated_at = datetime.utcnow()
    db.commit()
    return normalized


def _frontend_base_url() -> str:
    return (settings.FRONTEND_BASE_URL or os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")).rstrip("/")


def _api_base_url() -> str:
    return (settings.API_BASE_URL or os.getenv("API_BASE_URL", "http://localhost:5000")).rstrip("/")


def _frontend_connections_url(query: str = "") -> str:
    base = f"{_frontend_base_url()}/connections/"
    return f"{base}?{query}" if query else base

def _public_api_base_url() -> str:
    """
    Public base URL for OAuth callbacks when Meta/Google require HTTPS.
    Example: https://abcd-1234.ngrok-free.app
    """
    raw = (os.getenv("PUBLIC_API_BASE_URL") or "").strip()
    if not raw:
        return ""
    raw = raw.rstrip("/")
    # If someone accidentally pastes a full callback URL, keep only scheme://host[:port].
    if raw.startswith("http://") or raw.startswith("https://"):
        parts = urlsplit(raw)
        if parts.scheme and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}"
    return raw


@saas_api.route('/media/<path:filename>', methods=['GET'])
def serve_generated_media(filename: str):
    rel = str(filename or "").strip().lstrip("/")
    if not rel:
        return jsonify({'error': 'file_not_found'}), 404
    candidates = []
    rel_path = Path(rel)
    candidates.append((settings.BASE_DIR / rel_path).resolve())
    candidates.append((LEGACY_MEDIA_DIR / os.path.basename(rel)).resolve())
    for full_path in candidates:
        if not full_path.exists():
            continue
        in_base = settings.BASE_DIR == full_path or settings.BASE_DIR in full_path.parents
        in_legacy = LEGACY_MEDIA_DIR == full_path or LEGACY_MEDIA_DIR in full_path.parents
        if not in_base and not in_legacy:
            continue
        return send_from_directory(str(full_path.parent), full_path.name)
    return jsonify({'error': 'file_not_found'}), 404


def _youtube_length_bounds(video_type: str) -> tuple[int, int]:
    if video_type == "short":
        return (YOUTUBE_SHORT_MIN_SECONDS, YOUTUBE_SHORT_MAX_SECONDS)
    return (YOUTUBE_LONG_MIN_SECONDS, YOUTUBE_LONG_MAX_SECONDS)


def _youtube_eta_seconds(video_type: str, duration_seconds: int) -> int:
    if video_type == "short":
        return max(8, min(45, 8 + int(duration_seconds * 0.35)))
    return max(20, min(120, 20 + int(duration_seconds * 0.22)))

def _google_client_id() -> str:
    return (os.getenv("GOOGLE_CLIENT_ID") or "").strip()


def _google_client_secret() -> str:
    return (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()


def _google_redirect_uri() -> str:
    env = (settings.GOOGLE_REDIRECT_URI or os.getenv("GOOGLE_REDIRECT_URI") or "").strip()
    if env:
        return env
    base = _public_api_base_url()
    if base:
        return f"{base}/api/auth/oauth/google/callback"
    return "http://localhost:5000/api/auth/oauth/google/callback"


def _youtube_redirect_uri() -> str:
    env = (
        os.getenv("YOUTUBE_REDIRECT_URI")
        or settings.YOUTUBE_REDIRECT_URI
        or ""
    ).strip()
    if env:
        return env
    base = _public_api_base_url()
    if base:
        return f"{base}/api/integrations/youtube/callback"
    return "http://localhost:5000/api/integrations/youtube/callback"


def _facebook_client_id() -> str:
    return (
        os.getenv("FB_LOGIN_APP_ID")
        or os.getenv("FACEBOOK_APP_ID")
        or os.getenv("FACEBOOK_CLIENT_ID")
        or os.getenv("FB_APP_ID")
        or ""
    ).strip()


def _facebook_client_secret() -> str:
    login_id = (os.getenv("FB_LOGIN_APP_ID") or "").strip()
    if login_id:
        # Prefer dedicated login secret, but fall back to the main app secret if both flows use one app.
        return (
            os.getenv("FB_LOGIN_APP_SECRET")
            or os.getenv("FACEBOOK_APP_SECRET")
            or os.getenv("FACEBOOK_CLIENT_SECRET")
            or os.getenv("FB_APP_SECRET")
            or ""
        ).strip()
    return (
        os.getenv("FB_LOGIN_APP_SECRET")
        or os.getenv("FACEBOOK_APP_SECRET")
        or os.getenv("FACEBOOK_CLIENT_SECRET")
        or os.getenv("FB_APP_SECRET")
        or ""
    ).strip()


def _facebook_redirect_uri() -> str:
    env = (settings.FB_LOGIN_REDIRECT_URI or os.getenv("FB_LOGIN_REDIRECT_URI") or "").strip()
    if env:
        return env
    base = _public_api_base_url()
    if base:
        return f"{base}/api/auth/oauth/facebook/callback"
    return "http://localhost:5000/api/auth/oauth/facebook/callback"


def _facebook_login_scope() -> str:
    # Default login scope for Facebook Login is public profile + email.
    # Some apps can disable email explicitly with FB_LOGIN_ALLOW_EMAIL=0.
    allow_email_raw = (os.getenv("FB_LOGIN_ALLOW_EMAIL") or "1").strip().lower()
    include_email = allow_email_raw not in {"0", "false", "no"}
    return "public_profile,email" if include_email else "public_profile"


def _meta_redirect_uri() -> str:
    env = (settings.META_REDIRECT_URI or os.getenv("META_REDIRECT_URI") or os.getenv("REDIRECT_URI") or "").strip()
    if env:
        return env
    base = _public_api_base_url()
    if base:
        return f"{base}/api/integrations/meta/callback"
    return "http://localhost:5000/api/integrations/meta/callback"


def _oauth_redirect(params: dict):
    return redirect(f"{_frontend_base_url()}/login/?{urlencode(params)}")


def _parse_iso_datetime(raw_value: str) -> datetime:
    raw = (raw_value or "").strip()
    if not raw:
        raise ValueError("empty datetime")
    normalized = raw.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _normalize_requested_platforms(raw_platforms, raw_platform: str | None = None, *, default: list[str] | None = None) -> list[str]:
    out = []
    if isinstance(raw_platforms, list):
        for item in raw_platforms:
            key = str(item or "").strip().lower()
            if key in {"facebook", "instagram", "youtube"} and key not in out:
                out.append(key)
    single = str(raw_platform or "").strip().lower()
    if single in {"facebook", "instagram", "youtube"} and single not in out:
        out.append(single)
    if out:
        return out
    fallback = default or []
    return [p for p in fallback if p in {"facebook", "instagram", "youtube"}]



def _json_loads_safe(raw_value, fallback):
    try:
        if not raw_value:
            return fallback
        return json.loads(raw_value)
    except Exception:
        return fallback


def _campaign_payload(campaign: Campaign) -> dict:
    return {
        "id": campaign.id,
        "user_id": campaign.user_id,
        "project_id": campaign.project_id,
        "mode": campaign.mode,
        "topic": campaign.topic,
        "offer": campaign.offer,
        "objective": campaign.objective,
        "caption_master": campaign.caption_master,
        "cta": campaign.cta,
        "hashtags_master": _json_loads_safe(campaign.hashtags_master, []),
        "language": campaign.language,
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }


def _asset_payload(asset: CampaignAsset) -> dict:
    return {
        "id": asset.id,
        "campaign_id": asset.campaign_id,
        "type": asset.type,
        "storage_url": asset.storage_url,
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
        "duration_sec": asset.duration_sec,
        "size_bytes": int(asset.size_bytes or 0),
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


def _delivery_payload(delivery: CampaignDelivery) -> dict:
    return {
        "id": delivery.id,
        "campaign_id": delivery.campaign_id,
        "platform": delivery.platform,
        "kind": delivery.kind,
        "account_ref": delivery.account_ref,
        "caption_rendered": delivery.caption_rendered,
        "hashtags_rendered": _json_loads_safe(delivery.hashtags_rendered, []),
        "scheduled_at": delivery.scheduled_at.isoformat() if delivery.scheduled_at else None,
        "status": delivery.status,
        "remote_id": delivery.remote_id,
        "error_message": delivery.error_message,
        "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
        "updated_at": delivery.updated_at.isoformat() if delivery.updated_at else None,
    }


def _job_payload(job: GenerationJob) -> dict:
    return {
        "id": job.id,
        "campaign_id": job.campaign_id,
        "job_type": job.job_type,
        "status": job.status,
        "progress": int(job.progress or 0),
        "result": _json_loads_safe(job.result_json, {}),
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _job_result_dict(job: GenerationJob) -> dict:
    data = _json_loads_safe(job.result_json, {})
    return data if isinstance(data, dict) else {}


def _merge_job_result(job: GenerationJob, patch: dict) -> None:
    base = _job_result_dict(job)
    base.update(patch or {})
    job.result_json = json.dumps(base, ensure_ascii=False)


def _set_video_job_progress(
    db,
    job: GenerationJob,
    *,
    status: str | None = None,
    progress: int | None = None,
    step: str | None = None,
    message: str | None = None,
) -> None:
    if status:
        job.status = status
    if progress is not None:
        job.progress = max(0, min(100, int(progress)))
    if step or message:
        payload = _job_result_dict(job)
        progress_payload = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
        if step:
            progress_payload["step"] = str(step)
        if message:
            progress_payload["message"] = str(message)
        payload["progress"] = progress_payload
        job.result_json = json.dumps(payload, ensure_ascii=False)
    job.updated_at = datetime.utcnow()
    db.commit()


def _extract_hashtags(raw_text: str, limit: int = 8) -> list[str]:
    found = re.findall(r"#([\wа-яА-Я0-9_]+)", raw_text or "", flags=re.U)
    uniq = []
    for token in found:
        val = f"#{token.lower()}"
        if val not in uniq:
            uniq.append(val)
        if len(uniq) >= limit:
            break
    if not uniq:
        uniq = ["#контент", "#маркетинг", "#бизнес"][:limit]
    return uniq


def _normalize_create_goal(value: str) -> str:
    key = str(value or "").strip().lower()
    mapping = {
        "sales": "sales",
        "продажи": "sales",
        "lead": "lead",
        "leads": "lead",
        "лиды": "lead",
        "awareness": "awareness",
        "expertise": "awareness",
        "экспертность": "awareness",
        "announcement": "engagement",
        "анонс": "engagement",
        "warmup": "engagement",
        "прогрев": "engagement",
        "engagement": "engagement",
    }
    return mapping.get(key, "engagement")


def _normalize_create_tone(value: str) -> str:
    key = str(value or "").strip().lower()
    mapping = {
        "friendly": "friendly",
        "дружелюбный": "friendly",
        "expert": "expert",
        "экспертный": "expert",
        "sales": "sales",
        "продающий": "sales",
        "neutral": "neutral",
        "нейтральный": "neutral",
    }
    return mapping.get(key, "friendly")


def _quality_check_payload(caption: str, cta: str, hashtags: list[str], goal: str) -> dict:
    text = str(caption or "").strip()
    cta_text = str(cta or "").strip()
    tags = [str(x).strip() for x in (hashtags or []) if str(x).strip()]
    first_line = text.split("\n", 1)[0].strip() if text else ""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    long_paragraphs = sum(1 for p in paragraphs if len(p) >= 40)
    sentence_count = len(re.findall(r"[.!?](?:\s|$)", text))

    has_hook = len(text) > 40 and (
        bool(re.search(r"[!?]", text[:220])) or len(first_line) >= 24 or bool(re.search(r"\d", first_line))
    )
    has_structure = (
        long_paragraphs >= 2
        or bool(re.search(r"(^|\n)\s*(?:[•\-]|\d+[.)])\s+", text))
        or (len(text) >= 180 and sentence_count >= 3)
    )
    has_cta = bool(cta_text) or bool(re.search(r"(напишите|оставьте|перейдите|запишитесь|купите|позвоните)", text.lower()))
    hashtags_ok = 3 <= len(tags) <= 15

    goal_norm = _normalize_create_goal(goal)
    text_low = text.lower()
    if goal_norm == "sales":
        goal_match = bool(re.search(r"(скидк|цена|выгод|куп|закаж|оффер|предложени)", text_low)) or has_cta
    elif goal_norm == "lead":
        goal_match = bool(re.search(r"(заявк|форм|оставьте|контакт|напишите)", text_low)) or has_cta
    elif goal_norm == "awareness":
        goal_match = len(text) >= 160
    else:
        goal_match = bool("?" in text) or bool(re.search(r"(как вы|а вы|что думаете|поделитесь|ваше мнение|обсудим)", text_low)) or has_cta

    score = 0
    score += 20 if has_hook else 0
    score += 20 if has_structure else 0
    score += 20 if has_cta else 0
    score += 10 if hashtags_ok else 0
    score += 30 if goal_match else 0

    checks = [
        {"key": "hook", "label": "Хук", "state": "green" if has_hook else "yellow"},
        {"key": "structure", "label": "Структура", "state": "green" if has_structure else "yellow"},
        {"key": "cta", "label": "Призыв к действию", "state": "green" if has_cta else "red"},
        {"key": "hashtags", "label": "Хештеги", "state": "green" if hashtags_ok else "yellow"},
        {"key": "goal_match", "label": "Соответствие цели", "state": "green" if goal_match else "yellow"},
    ]

    warnings = []
    if len(text) < 120:
        warnings.append("Текст выглядит коротким, можно усилить деталями.")
    if not has_cta:
        warnings.append("Добавьте призыв к действию: что клиент должен сделать после прочтения.")
    if not hashtags_ok:
        warnings.append("Рекомендуется 3-15 хештегов.")
    return {"score": int(score), "checks": checks, "warnings": warnings}


def _preview_default_payload() -> dict:
    return {
        "platform": "facebook",
        "content_type": "image_post",
        "caption": "",
        "cta": None,
        "hashtags": [],
        "media": {
            "type": "image",
            "url": "",
            "thumbnail_url": None,
            "width": None,
            "height": None,
            "duration_s": None,
        },
        "meta": {
            "page_name": None,
            "account_name": None,
            "scheduled_at": None,
            "goal": "engagement",
            "format_hint": None,
            "title": None,
            "description": None,
            "tags": [],
        },
    }


def _normalize_preview_payload(raw: dict | None) -> dict:
    payload = _preview_default_payload()
    if isinstance(raw, dict):
        for key in ("platform", "content_type", "caption", "cta", "hashtags"):
            if key in raw:
                payload[key] = raw[key]
        if isinstance(raw.get("media"), dict):
            payload["media"].update(raw.get("media") or {})
        if isinstance(raw.get("meta"), dict):
            payload["meta"].update(raw.get("meta") or {})
    platform = str(payload.get("platform") or "facebook").strip().lower()
    if platform not in {"facebook", "instagram", "youtube"}:
        platform = "facebook"
    content_type = str(payload.get("content_type") or "image_post").strip().lower()
    if content_type not in {"image_post", "video_post"}:
        content_type = "image_post"
    media = payload.get("media") if isinstance(payload.get("media"), dict) else {}
    media_type = str(media.get("type") or ("video" if content_type == "video_post" else "image")).strip().lower()
    if media_type not in {"image", "video"}:
        media_type = "image"
    hashtags_raw = payload.get("hashtags")
    hashtags = []
    if isinstance(hashtags_raw, str):
        hashtags = [x.strip() for x in hashtags_raw.split() if x.strip()]
    elif isinstance(hashtags_raw, list):
        hashtags = [str(x).strip() for x in hashtags_raw if str(x).strip()]
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    tags_raw = meta.get("tags")
    tags = []
    if isinstance(tags_raw, list):
        tags = [str(x).strip() for x in tags_raw if str(x).strip()]
    payload["platform"] = platform
    payload["content_type"] = content_type
    payload["caption"] = str(payload.get("caption") or "").strip()
    payload["cta"] = str(payload.get("cta") or "").strip() or None
    payload["hashtags"] = hashtags[:30]
    payload["media"] = {
        "type": media_type,
        "url": str(media.get("url") or "").strip(),
        "thumbnail_url": str(media.get("thumbnail_url") or "").strip() or None,
        "width": int(media.get("width")) if str(media.get("width", "")).isdigit() else None,
        "height": int(media.get("height")) if str(media.get("height", "")).isdigit() else None,
        "duration_s": float(media.get("duration_s")) if str(media.get("duration_s", "")).replace(".", "", 1).isdigit() else None,
    }
    payload["meta"] = {
        "page_name": str(meta.get("page_name") or "").strip() or None,
        "account_name": str(meta.get("account_name") or "").strip() or None,
        "scheduled_at": str(meta.get("scheduled_at") or "").strip() or None,
        "goal": _normalize_create_goal(meta.get("goal") or "engagement"),
        "format_hint": str(meta.get("format_hint") or "").strip().lower() or None,
        "title": str(meta.get("title") or "").strip() or None,
        "description": str(meta.get("description") or "").strip() or None,
        "tags": tags[:30],
    }
    return payload


def _validate_preview_payload(payload: dict) -> dict:
    p = _normalize_preview_payload(payload)
    warnings = []
    errors = []
    suggestions = []

    platform = p["platform"]
    content_type = p["content_type"]
    caption = p["caption"]
    cta = p["cta"] or ""
    hashtags = p["hashtags"] or []
    media = p["media"] or {}
    meta = p["meta"] or {}
    goal = _normalize_create_goal(meta.get("goal") or "engagement")
    media_url = str(media.get("url") or "").strip()
    media_type = str(media.get("type") or "image").strip().lower()
    duration_s = media.get("duration_s")
    width = media.get("width")
    height = media.get("height")
    ratio = (float(width) / float(height)) if width and height and float(height) > 0 else None
    format_hint = str(meta.get("format_hint") or "").strip().lower()

    if not media_url:
        errors.append({"level": "error", "code": "media_missing", "message": "Отсутствует медиа-файл для публикации."})
    if not caption:
        warnings.append({"level": "warning", "code": "caption_empty", "message": "Текст публикации пустой."})
    if goal in {"sales", "lead"} and not cta:
        warnings.append({"level": "warning", "code": "cta_missing", "message": "Для цели продажи/лиды лучше добавить призыв к действию."})
        suggestions.append("Сгенерируйте призыв к действию автоматически.")

    if platform == "instagram" and (len(hashtags) < 5 or len(hashtags) > 20):
        warnings.append({"level": "warning", "code": "ig_hashtags_range", "message": "Для Instagram рекомендуется 5-20 хештегов."})
        suggestions.append("Добавьте/сократите хештеги до диапазона 5-20.")
    if platform == "facebook" and len(hashtags) > 8:
        warnings.append({"level": "warning", "code": "fb_hashtags_max", "message": "Для Facebook рекомендуется не более 8 хештегов."})
        suggestions.append("Сократите количество хештегов.")
    if platform == "youtube":
        yt_tags = meta.get("tags") or hashtags
        if len(yt_tags) < 5:
            warnings.append({"level": "warning", "code": "yt_tags_min", "message": "Для YouTube желательно минимум 5 тегов."})
            suggestions.append("Добавьте теги для YouTube.")

    if platform == "instagram" and len(caption) > 2200:
        warnings.append({"level": "warning", "code": "ig_caption_too_long", "message": "Текст Instagram длиннее 2200 символов."})
        suggestions.append("Сократите текст для Instagram.")
    if platform == "facebook" and len(caption) > 5000:
        warnings.append({"level": "warning", "code": "fb_caption_too_long", "message": "Текст Facebook длиннее 5000 символов."})
    if platform == "youtube":
        desc = str(meta.get("description") or caption or "").strip()
        if len(desc) < 200:
            warnings.append({"level": "warning", "code": "yt_desc_short", "message": "Описание YouTube короткое (<200 символов)."})
            suggestions.append("Расширьте описание YouTube.")

    is_short_form = format_hint in {"reel", "shorts"} or (platform == "instagram" and content_type == "video_post")
    if content_type == "video_post":
        if platform == "youtube" and media_type != "video":
            errors.append({"level": "error", "code": "yt_requires_video", "message": "Для YouTube публикации требуется видео."})
        if is_short_form:
            if duration_s and duration_s > 60:
                warnings.append({"level": "warning", "code": "short_duration_gt_60", "message": "Для Shorts/Reels рекомендуется длительность до 60 секунд."})
            if ratio is not None and abs(ratio - (9.0 / 16.0)) > 0.22:
                warnings.append({"level": "warning", "code": "short_ratio_mismatch", "message": "Для Shorts/Reels лучше вертикальный формат 9:16."})
        if duration_s and duration_s > 480:
            warnings.append({"level": "warning", "code": "duration_gt_480", "message": "Видео превышает лимит 480 секунд."})
    if platform == "youtube" and content_type == "image_post":
        errors.append({"level": "error", "code": "platform_mismatch", "message": "Для YouTube требуется video_post."})

    score = 100
    score -= min(60, 25 * len(errors))
    score -= min(40, 8 * len(warnings))
    score = max(0, int(score))
    return {"score": score, "warnings": warnings + errors, "suggestions": suggestions, "has_error": bool(errors), "payload": p}


def _resolve_media_url_to_local_path(url: str) -> Path | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    base = settings.API_BASE_URL.rstrip("/")
    marker = "/api/media/"
    rel = None
    if raw.startswith(base + marker):
        rel = raw.split(marker, 1)[1]
    elif raw.startswith(marker):
        rel = raw.split(marker, 1)[1]
    if rel:
        candidate = (settings.BASE_DIR / rel.lstrip("/")).resolve()
        if candidate.exists() and (settings.BASE_DIR == candidate or settings.BASE_DIR in candidate.parents):
            return candidate
    candidate = Path(raw)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    return None


def _build_video_thumbnail(video_url: str, second: float = 0.8) -> str | None:
    src_local = _resolve_media_url_to_local_path(video_url)
    thumbs_dir = (settings.OUTPUT_DIR / "thumbs").resolve()
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha1(f"{video_url}|{second}".encode("utf-8")).hexdigest()[:24]
    thumb_path = thumbs_dir / f"{cache_key}.jpg"
    if thumb_path.exists():
        rel = thumb_path.resolve().relative_to(settings.BASE_DIR).as_posix()
        return f"{settings.API_BASE_URL}/api/media/{rel}"
    src = str(src_local) if src_local else str(video_url or "").strip()
    if not src:
        return None
    cmd = [
        settings.FFMPEG_BIN,
        "-y",
        "-ss",
        str(max(0.0, float(second))),
        "-i",
        src,
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(thumb_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=35)
    except Exception:
        return None
    if not thumb_path.exists():
        return None
    rel = thumb_path.resolve().relative_to(settings.BASE_DIR).as_posix()
    return f"{settings.API_BASE_URL}/api/media/{rel}"


def _template_payload(row: UserTemplate) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "preset": _json_loads_safe(row.preset_json, {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _catalog_template_payload(row: Template) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "title": row.title,
        "description": row.description,
        "type": row.type,
        "platform": row.platform,
        "goal": row.goal,
        "tone": row.tone,
        "hook_line": row.hook_line,
        "cta": row.cta,
        "prompt_system": row.prompt_system,
        "prompt_user": row.prompt_user,
        "variables_schema_json": _json_loads_safe(row.variables_schema_json, {}),
        "preview_text": row.preview_text,
        "sort_order": row.sort_order,
    }


def _catalog_niche_payload(row: Niche, templates: list[Template]) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "title": row.title,
        "description": row.description,
        "icon": row.icon,
        "sort_order": row.sort_order,
        "templates": [_catalog_template_payload(item) for item in templates],
    }


def _guess_mime(url_value: str, fallback: str = "application/octet-stream") -> str:
    raw = str(url_value or "").lower()
    if raw.endswith(".jpg") or raw.endswith(".jpeg"):
        return "image/jpeg"
    if raw.endswith(".png"):
        return "image/png"
    if raw.endswith(".webp"):
        return "image/webp"
    if raw.endswith(".mp4"):
        return "video/mp4"
    return fallback


def _download_and_store_binary(url: str, suffix: str, max_bytes: int = 120 * 1024 * 1024) -> tuple[str, int] | None:
    try:
        res = requests.get(url, timeout=90, stream=True)
        if res.status_code != 200:
            return None
        filename = f"asset_{secrets.token_hex(10)}{suffix}"
        full_path = MEDIA_DIR / filename
        total = 0
        with open(full_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    f.close()
                    full_path.unlink(missing_ok=True)
                    return None
                f.write(chunk)
        return (f"{settings.API_BASE_URL}/api/media/{filename}", total)
    except Exception:
        return None


def _ensure_video_asset_url(topic: str, duration_sec: int, aspect_ratio: str) -> tuple[str, int]:
    external = (os.getenv("VIDEO_GENERATOR_URL") or "").strip()
    if external:
        try:
            resp = requests.post(
                external,
                json={
                    "topic": topic,
                    "duration_sec": duration_sec,
                    "aspect_ratio": aspect_ratio,
                    "realism": True,
                    "prompt_guards": {"no_fantasy": True},
                },
                timeout=180,
            )
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            video_url = str((data or {}).get("video_url") or "").strip()
            if video_url:
                mirrored = _download_and_store_binary(video_url, ".mp4")
                if mirrored:
                    return mirrored
                return (video_url, int((data or {}).get("size_bytes") or 0))
        except Exception:
            pass
    fallback = _download_and_store_binary("https://samplelib.com/lib/preview/mp4/sample-5s.mp4", ".mp4")
    if fallback:
        return fallback
    tiny_b64 = (
        "AAAAHGZ0eXBpc29tAAACAGlzb21pc28yYXZjMQAAAAhmcmVlAAABW21kYXQhEAUgpYxkAAAD6G1vb3YAAABsbXZoZAAAAAAAAAAAAAAAAAAAA+gAAAPoAAEAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAIVdHJhawAAAFx0a2hkAAAAAwAAAAAAAAAAAAAAAQAAAAAAAAAD6AAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAQAAAAAAAAAAAAAAAAAAACRlZHRzAAAAHGVsc3QAAAAAAAAAAQAAA+gAAAAAAAEAAAAAAbxtZGlhAAAAIG1kaGQAAAAAAAAAAAAAAAAAAAyAAAAFAABVxAAAAAAAKGhk bHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABvW1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAYVzdGJsAAAA3XN0c2QAAAAAAAAAAQAAAMVhdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAIAASAAAAEgAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABj//wAAAC9hdmNDAfQAHv/hABln2QAHpZCgPaEAQAAAwABAAADADxI8UKZAAAB5GJ0cnQAAAABAAAB9AAAABhzdHRzAAAAAAAAAAEAAAABAAAEAAAAABRzdHNzAAAAAAAAAAEAAAABAAAAHGN0dHMAAAAAAAAAAQAAAAEAAAAAAAAAHHN0c2MAAAAAAAAAAQAAAAEAAAABAAAAAQAAABRzdHN6AAAAAAAAAAAAAAABAAAB+AAAABJzdGNvAAAAAAAAAAEAAAA4"
    ).replace(" ", "")
    try:
        raw = base64.b64decode(tiny_b64)
        filename = f"asset_{secrets.token_hex(10)}.mp4"
        full_path = MEDIA_DIR / filename
        full_path.write_bytes(raw)
        return (f"{settings.API_BASE_URL}/api/media/{filename}", len(raw))
    except Exception:
        raise RuntimeError("Не удалось создать видео-ассет")


def _publish_instagram_reel(ig_user_id: str, access_token: str, video_url: str, caption: str) -> dict:
    create_url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media"
    create_payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption or "",
        "share_to_feed": "true",
        "access_token": access_token,
    }
    create_res = requests.post(create_url, data=create_payload, timeout=45).json()
    creation_id = str(create_res.get("id") or "").strip()
    if not creation_id:
        return {"error": create_res.get("error") or create_res}

    status_url = f"https://graph.facebook.com/v20.0/{creation_id}"
    for _ in range(15):
        st = requests.get(
            status_url,
            params={"fields": "status_code,status", "access_token": access_token},
            timeout=25,
        ).json()
        status_code = str(st.get("status_code") or st.get("status") or "").upper()
        if status_code in {"FINISHED", "PUBLISHED"}:
            break
        if status_code in {"ERROR", "EXPIRED"}:
            return {"error": st.get("error") or st}
        time.sleep(2)

    publish_url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media_publish"
    out = requests.post(
        publish_url,
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=45,
    ).json()
    return out


def _publish_facebook_video(page_id: str, page_access_token: str, video_url: str, caption: str) -> dict:
    url = f"https://graph.facebook.com/v20.0/{page_id}/videos"
    payload = {
        "file_url": video_url,
        "description": caption or "",
        "access_token": page_access_token,
    }
    return requests.post(url, data=payload, timeout=60).json()


def _publish_youtube_video_from_url(access_token: str, video_url: str, title: str, description: str, tags: list[str], is_shorts: bool) -> dict:
    media_res = requests.get(video_url, timeout=120)
    if media_res.status_code != 200:
        return {"error": {"message": f"Не удалось загрузить видео для YouTube ({media_res.status_code})"}}
    filename = f"upload_{secrets.token_hex(6)}.mp4"
    upload_url = "https://www.googleapis.com/upload/youtube/v3/videos"
    params = {"part": "snippet,status", "uploadType": "multipart"}
    snippet = {
        "title": (title or "Новый ролик").strip()[:90],
        "description": (description or "").strip(),
        "tags": tags[:15],
        "categoryId": "22",
    }
    if is_shorts and "#shorts" not in snippet["description"].lower():
        snippet["description"] = f"{snippet['description']}\n\n#shorts".strip()
    status_payload = {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    metadata = {"snippet": snippet, "status": status_payload}
    files = {
        "metadata": ("metadata.json", json.dumps(metadata, ensure_ascii=False), "application/json; charset=UTF-8"),
        "file": (filename, media_res.content, "video/mp4"),
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.post(upload_url, params=params, headers=headers, files=files, timeout=240)
    try:
        return res.json()
    except Exception:
        return {"error": {"message": (res.text or "")[:1200], "status": res.status_code}}


def _start_delivery_worker(delivery_id: int) -> None:
    def _runner():
        db = SessionLocal()
        try:
            delivery = db.query(CampaignDelivery).filter_by(id=delivery_id).first()
            if not delivery:
                return
            if delivery.status in {"published", "failed", "processing", "uploading"}:
                return
            if delivery.scheduled_at and delivery.scheduled_at > datetime.utcnow():
                return
            delivery.status = "uploading"
            delivery.updated_at = datetime.utcnow()
            db.commit()

            campaign = db.query(Campaign).filter_by(id=delivery.campaign_id).first()
            if not campaign:
                delivery.status = "failed"
                delivery.error_message = "Campaign not found"
                delivery.updated_at = datetime.utcnow()
                db.commit()
                return
            assets = db.query(CampaignAsset).filter_by(campaign_id=campaign.id).all()
            image_asset = next((a for a in reversed(assets) if a.type == "image"), None)
            video_asset = next((a for a in reversed(assets) if a.type == "video"), None)
            hashtags = _json_loads_safe(delivery.hashtags_rendered, [])
            tags_text = " ".join(str(x) for x in hashtags if str(x).strip())
            caption = (delivery.caption_rendered or campaign.caption_master or campaign.topic or "").strip()
            if tags_text:
                caption = f"{caption}\n\n{tags_text}".strip()

            remote_id = ""
            delivery.status = "processing"
            delivery.updated_at = datetime.utcnow()
            db.commit()

            if delivery.platform in {"facebook", "instagram"}:
                conn_query = db.query(SocialAccount).filter(
                    SocialAccount.user_id == campaign.user_id,
                    SocialAccount.provider == "meta",
                )
                if delivery.account_ref:
                    if delivery.platform == "facebook":
                        conn_query = conn_query.filter(SocialAccount.page_id == delivery.account_ref)
                    else:
                        conn_query = conn_query.filter(SocialAccount.ig_user_id == delivery.account_ref)
                conn = conn_query.order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc()).first()
                if not conn or not conn.token_encrypted:
                    raise RuntimeError("Meta не подключен")
                access_token = decrypt_meta_token(conn.token_encrypted)
                if delivery.platform == "facebook":
                    if not conn.page_id:
                        raise RuntimeError("Не выбрана Facebook Page")
                    page_token = _resolve_page_access_token(access_token, conn.page_id)
                    if not page_token:
                        raise RuntimeError("Не удалось получить page token")
                    if delivery.kind == "video":
                        if not video_asset:
                            raise RuntimeError("Видео не сгенерировано")
                        result = _publish_facebook_video(conn.page_id, page_token, video_asset.storage_url, caption)
                        remote_id = str(result.get("id") or result.get("video_id") or "")
                    else:
                        image_url = image_asset.storage_url if image_asset else None
                        result = publish_to_facebook(conn.page_id, page_token, image_url, caption)
                        remote_id = str(result.get("post_id") or result.get("id") or "")
                else:
                    if not conn.ig_user_id:
                        raise RuntimeError("Instagram Business не найден")
                    if delivery.kind == "reel":
                        if not video_asset:
                            raise RuntimeError("Видео не сгенерировано")
                        result = _publish_instagram_reel(conn.ig_user_id, access_token, video_asset.storage_url, caption)
                        remote_id = str(result.get("id") or "")
                    else:
                        image_url = image_asset.storage_url if image_asset else None
                        result = publish_to_instagram(conn.ig_user_id, access_token, image_url, caption)
                        remote_id = str(result.get("id") or "")
                if not remote_id:
                    raise RuntimeError(f"Meta API error: {result}")
            elif delivery.platform == "youtube":
                conn_query = db.query(SocialAccount).filter(
                    SocialAccount.user_id == campaign.user_id,
                    SocialAccount.provider == "youtube",
                )
                if delivery.account_ref:
                    conn_query = conn_query.filter(SocialAccount.channel_id == delivery.account_ref)
                conn = conn_query.order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc()).first()
                if not conn or not conn.token_encrypted:
                    raise RuntimeError("YouTube не подключен")
                if not video_asset:
                    raise RuntimeError("Видео не сгенерировано")
                yt_token = decrypt_meta_token(conn.token_encrypted)
                yt = _publish_youtube_video_from_url(
                    access_token=yt_token,
                    video_url=video_asset.storage_url,
                    title=campaign.topic,
                    description=caption,
                    tags=hashtags,
                    is_shorts=(delivery.kind == "shorts"),
                )
                remote_id = str(yt.get("id") or "")
                if not remote_id:
                    raise RuntimeError(f"YouTube API error: {yt}")
            else:
                raise RuntimeError("Неподдерживаемая платформа")

            delivery.status = "published"
            delivery.remote_id = remote_id
            delivery.error_message = None
            delivery.updated_at = datetime.utcnow()
            db.commit()
            _refresh_campaign_status(db, campaign.id)
        except Exception as exc:
            db.rollback()
            row = db.query(CampaignDelivery).filter_by(id=delivery_id).first()
            if row:
                row.status = "failed"
                row.error_message = str(exc)[:2000]
                row.updated_at = datetime.utcnow()
                db.commit()
                try:
                    _refresh_campaign_status(db, row.campaign_id)
                except Exception:
                    pass
        finally:
            db.close()

    thread = threading.Thread(target=_runner, daemon=True, name=f"delivery-{delivery_id}")
    thread.start()


def _store_oauth_state(provider: str, extra: dict | None = None) -> str:
    now = time.time()
    expired = [k for k, v in OAUTH_STATES.items() if v["exp"] < now]
    for key in expired:
        OAUTH_STATES.pop(key, None)

    state = secrets.token_urlsafe(24)
    payload = {"provider": provider, "exp": now + OAUTH_STATE_TTL_SECONDS}
    if extra:
        payload.update(extra)
    OAUTH_STATES[state] = payload
    return state


def _consume_oauth_state_meta(state: str, provider: str | None = None) -> dict | None:
    if not state:
        return None
    meta = OAUTH_STATES.get(state)
    if not meta:
        return None
    if provider and meta["provider"] != provider:
        return None
    if meta["exp"] < time.time():
        OAUTH_STATES.pop(state, None)
        return None
    OAUTH_STATES.pop(state, None)
    return meta


def _consume_oauth_state(state: str, provider: str) -> bool:
    return _consume_oauth_state_meta(state, provider) is not None


def _finalize_oauth_login(email: str, provider: str, provider_user_id: str):
    email = (email or "").strip().lower()
    provider_user_id = (provider_user_id or "").strip()
    if not email or not provider_user_id:
        return _oauth_redirect({"oauth_error": "oauth_profile_incomplete"})

    db = SessionLocal()
    try:
        user = None
        if provider == "google":
            user = db.query(AppUser).filter_by(google_sub=provider_user_id).first()
        elif provider == "facebook":
            user = db.query(AppUser).filter_by(facebook_user_id=provider_user_id).first()

        if not user:
            user = db.query(AppUser).filter_by(email=email).first()

        if not user:
            user = AppUser(
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(24)),
                role="user",
                plan="free",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        if provider == "google" and user.google_sub != provider_user_id:
            user.google_sub = provider_user_id
        if provider == "facebook" and user.facebook_user_id != provider_user_id:
            user.facebook_user_id = provider_user_id

        user.last_login = datetime.utcnow()
        db.commit()
        user_id = user.id
    finally:
        db.close()

    seed_plans()
    ensure_user_plan_and_credits(user_id)
    get_or_create_default_project(user_id)
    token = create_token(user_id)
    log_event(f"user_login_oauth_{provider}", actor_user_id=user_id, context=f"email={email};ip={_ip()}")
    return _oauth_redirect({"oauth_token": token})


@saas_api.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "status": "ok", "env": settings.ENV, "time": datetime.utcnow().isoformat()})


def _start_auth_challenge(flow: str, email: str, password: str, honeypot: str, ip_addr: str, user_agent: str):
    if honeypot:
        return {"error": "Запрос отклонен"}, 400
    if flow not in {"login", "register"}:
        return {"error": "Некорректный тип авторизации"}, 400
    if not email or not EMAIL_RE.match(email):
        return {"error": "Введите корректный email"}, 400
    if not password:
        return {"error": "Введите email и пароль"}, 400
    if len(password) < 8:
        return {"error": "Пароль должен быть не короче 8 символов"}, 400

    now = datetime.utcnow()
    db = SessionLocal()
    try:
        since = now - timedelta(seconds=AUTH_RATE_WINDOW_SECONDS)
        by_ip_recent = (
            db.query(AuthEmailChallenge)
            .filter(AuthEmailChallenge.created_at >= since, AuthEmailChallenge.requested_ip == ip_addr)
            .count()
        )
        if by_ip_recent >= AUTH_RATE_MAX_PER_IP:
            return {"error": "Слишком много попыток. Попробуйте позже."}, 429

        by_email_recent = (
            db.query(AuthEmailChallenge)
            .filter(AuthEmailChallenge.created_at >= since, AuthEmailChallenge.email == email)
            .count()
        )
        if by_email_recent >= AUTH_RATE_MAX_PER_EMAIL:
            return {"error": "Слишком много попыток для этого email. Попробуйте позже."}, 429

        latest = (
            db.query(AuthEmailChallenge)
            .filter(
                AuthEmailChallenge.email == email,
                AuthEmailChallenge.flow == flow,
                AuthEmailChallenge.verified_at.is_(None),
            )
            .order_by(AuthEmailChallenge.created_at.desc())
            .first()
        )
        if latest and (now - latest.created_at).total_seconds() < AUTH_CODE_COOLDOWN_SECONDS:
            return {
                "error": f"Код уже отправлен. Повторите через {AUTH_CODE_COOLDOWN_SECONDS} сек."
            }, 429

        existing_user = db.query(AppUser).filter_by(email=email).first()
        login_user_id = None
        pending_password_hash = None
        if flow == "register":
            if existing_user:
                return {"error": "Пользователь с таким email уже существует"}, 409
            pending_password_hash = hash_password(password)
        else:
            if not existing_user or not verify_password(password, existing_user.password_hash):
                return {"error": "Неверный email или пароль"}, 401
            login_user_id = existing_user.id

        challenge_token = secrets.token_urlsafe(24)
        code = f"{random.randint(0, 9999):04d}"
        challenge = AuthEmailChallenge(
            challenge_token=challenge_token,
            flow=flow,
            email=email,
            user_id=login_user_id,
            pending_password_hash=pending_password_hash,
            code_hash=_auth_code_hash(challenge_token, code),
            attempts_left=AUTH_MAX_VERIFY_ATTEMPTS,
            requested_ip=ip_addr,
            user_agent=(user_agent or "")[:255],
            expires_at=now + timedelta(seconds=AUTH_CODE_TTL_SECONDS),
        )
        db.add(challenge)
        db.commit()
    finally:
        db.close()

    delivered = False
    try:
        delivered = _send_auth_email_code(
            email=email,
            code=code,
            flow=flow,
            ip_addr=ip_addr,
            challenge_token=challenge_token,
        )
    except Exception as exc:
        current_app.logger.warning("auth code email failed: %s", exc)

    is_dev = (settings.ENV or "").lower() in {"dev", "development", "local"}
    if not delivered and not is_dev:
        current_app.logger.warning(
            "auth email delivery unavailable; fallback to on-screen code flow=%s email=%s ip=%s",
            flow,
            email,
            ip_addr,
        )

    payload = {
        "challenge_token": challenge_token,
        "expires_in": AUTH_CODE_TTL_SECONDS,
        "cooldown_seconds": AUTH_CODE_COOLDOWN_SECONDS,
        "delivery": "email" if delivered else "dev",
        "message": "Проверьте email и подтвердите действие",
        "flow": flow,
    }
    payload["message"] = "Код отправлен на email"
    if not delivered:
        payload["message"] = "Почта временно недоступна. Используйте код подтверждения ниже."
    if not delivered:
        payload["dev_code"] = code
        payload["dev_verify_url"] = f"{_api_base_url()}/api/auth/verify-email?challenge_token={quote(challenge_token)}"
    log_event("auth_code_created", context=f"flow={flow};email={email};ip={ip_addr};delivered={delivered}")
    return payload, 200


def _complete_auth_challenge(challenge_token: str, code: str, ip_addr: str, allow_register_without_code: bool = False):
    if not challenge_token:
        return {"error": "Отсутствует challenge_token"}, 400
    if not allow_register_without_code and not re.fullmatch(r"\d{4}", code or ""):
        return {"error": "Введите 4-значный код"}, 400

    now = datetime.utcnow()
    db = SessionLocal()
    try:
        challenge = db.query(AuthEmailChallenge).filter_by(challenge_token=challenge_token).first()
        if not challenge:
            return {"error": "Код не найден или устарел"}, 404
        if challenge.verified_at is not None:
            return {"error": "Код уже использован"}, 409
        if challenge.expires_at < now:
            return {"error": "Срок действия кода истёк"}, 400
        if challenge.attempts_left <= 0:
            return {"error": "Слишком много попыток. Запросите новый код."}, 429

        needs_code = not (allow_register_without_code and challenge.flow == "register")
        if needs_code:
            expected = _auth_code_hash(challenge.challenge_token, code)
            if not hmac.compare_digest(expected, challenge.code_hash):
                challenge.attempts_left = max(0, challenge.attempts_left - 1)
                db.commit()
                if challenge.attempts_left <= 0:
                    return {"error": "Слишком много попыток. Запросите новый код."}, 429
                return {"error": f"Неверный код. Осталось попыток: {challenge.attempts_left}"}, 400

        challenge.verified_at = now
        flow = challenge.flow
        email = challenge.email
        user = None
        if flow == "register":
            existing = db.query(AppUser).filter_by(email=email).first()
            if existing:
                return {"error": "Пользователь с таким email уже существует"}, 409
            user = AppUser(
                email=email,
                password_hash=challenge.pending_password_hash or hash_password(secrets.token_urlsafe(24)),
                role="user",
                plan="free",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        elif flow == "login":
            user = db.query(AppUser).filter_by(id=challenge.user_id, email=email).first()
            if not user:
                return {"error": "Неверный email или пароль"}, 401
            user.last_login = now
            db.commit()
        else:
            return {"error": "Некорректный тип challenge"}, 400

        user_id = user.id
        user_email = user.email
        user_role = user.role
        user_plan = user.plan
    finally:
        db.close()

    seed_plans()
    ensure_user_plan_and_credits(user_id)
    get_or_create_default_project(user_id)

    token = create_token(user_id)
    event_name = "user_registered" if flow == "register" else "user_login"
    log_event(event_name, actor_user_id=user_id, context=f"email={user_email};ip={ip_addr};via=email_code")
    return {"token": token, "user": {"id": user_id, "email": user_email, "role": user_role, "plan": normalize_plan_code(user_plan)}}, 200


@saas_api.route("/auth/challenge", methods=["POST"])
def auth_challenge():
    data = request.get_json(silent=True) or {}
    flow = (data.get("flow") or "").strip().lower()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    honeypot = (data.get("website") or "").strip()
    payload, status = _start_auth_challenge(flow=flow, email=email, password=password, honeypot=honeypot, ip_addr=_ip(), user_agent=request.headers.get("User-Agent", ""))
    return jsonify(payload), status


@saas_api.route("/auth/verify-code", methods=["POST"])
def auth_verify_code():
    data = request.get_json(silent=True) or {}
    challenge_token = (data.get("challenge_token") or "").strip()
    code = (data.get("code") or "").strip()
    payload, status = _complete_auth_challenge(challenge_token=challenge_token, code=code, ip_addr=_ip())
    return jsonify(payload), status


@saas_api.route("/auth/verify-email", methods=["GET"])
def auth_verify_email():
    challenge_token = (request.args.get("challenge_token") or "").strip()
    payload, status = _complete_auth_challenge(
        challenge_token=challenge_token,
        code="",
        ip_addr=_ip(),
        allow_register_without_code=True,
    )
    if status != 200:
        return _oauth_redirect({"oauth_error": "email_verify_failed"})
    token = payload.get("token")
    if not token:
        return _oauth_redirect({"oauth_error": "email_verify_failed"})
    return _oauth_redirect({"oauth_token": token})


@saas_api.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    honeypot = (data.get("website") or "").strip()
    payload, status = _start_auth_challenge(flow="register", email=email, password=password, honeypot=honeypot, ip_addr=_ip(), user_agent=request.headers.get("User-Agent", ""))
    return jsonify(payload), status


@saas_api.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    honeypot = (data.get("website") or "").strip()

    # Admin emergency path: allow direct password login without email code challenge.
    # Keep OTP challenge flow in tests.
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(email=email).first()
        if (
            user
            and user.role == "admin"
            and verify_password(password, user.password_hash)
            and bool(settings.ALLOW_ADMIN_DIRECT_LOGIN)
            and not bool(getattr(current_app, "testing", False))
        ):
            seed_plans()
            ensure_user_plan_and_credits(user.id)
            get_or_create_default_project(user.id)
            token = create_token(user.id)
            log_event("admin_login", actor_user_id=user.id, context=f"email={user.email};ip={_ip()};via=password_direct")
            return jsonify({"token": token, "user": {"id": user.id, "email": user.email, "role": user.role, "plan": normalize_plan_code(user.plan)}}), 200
    finally:
        db.close()

    payload, status = _start_auth_challenge(flow="login", email=email, password=password, honeypot=honeypot, ip_addr=_ip(), user_agent=request.headers.get("User-Agent", ""))
    return jsonify(payload), status


@saas_api.route("/auth/providers", methods=["GET"])
def auth_providers():
    google_configured = bool(_google_client_id() and _google_client_secret())
    facebook_configured = bool(_facebook_client_id() and _facebook_client_secret())
    return jsonify(
        {
            "show_social_login": bool(settings.SHOW_SOCIAL_LOGIN),
            "google": {
                "configured": google_configured,
                "start_url": "/api/auth/oauth/google/start",
                "callback_url": _google_redirect_uri(),
            },
            "facebook": {
                "configured": facebook_configured,
                "start_url": "/api/auth/oauth/facebook/start",
                "callback_url": _facebook_redirect_uri(),
                "scope": _facebook_login_scope(),
            },
        }
    )


@saas_api.route("/auth/oauth/google/start", methods=["GET"])
def oauth_google_start():
    client_id = _google_client_id()
    client_secret = _google_client_secret()
    redirect_uri = _google_redirect_uri()
    if not client_id or not client_secret:
        return _oauth_redirect({"oauth_error": "google_not_configured"})

    state = _store_oauth_state("google")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


def _finalize_youtube_oauth_connect(user_id: int, code: str, redirect_uri: str):
    client_id = _google_client_id()
    client_secret = _google_client_secret()
    if not client_id or not client_secret:
        return redirect(_frontend_connections_url("youtube_error=google_not_configured"))

    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if not token_resp.ok:
        return redirect(_frontend_connections_url("youtube_error=token_exchange_failed"))

    token_data = token_resp.json() or {}
    access_token = str(token_data.get("access_token") or "").strip()
    expires_in = int(token_data.get("expires_in") or 0)
    if not access_token:
        return redirect(_frontend_connections_url("youtube_error=token_missing"))

    yt_resp = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "snippet", "mine": "true", "maxResults": 1},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if not yt_resp.ok:
        details = ""
        try:
            payload = yt_resp.json() if yt_resp.content else {}
            if isinstance(payload, dict):
                err = payload.get("error")
                if isinstance(err, dict):
                    msg = str(err.get("message") or "").strip()
                    code = str(err.get("code") or "").strip()
                    if code and msg:
                        details = f"[{code}] {msg}"
                    elif msg:
                        details = msg
        except Exception:
            details = ""
        current_app.logger.warning(
            "youtube channel read failed user_id=%s status=%s details=%s",
            user_id,
            yt_resp.status_code,
            details[:500],
        )
        if "has not been used in project" in details or "is disabled" in details:
            return redirect(_frontend_connections_url(f"youtube_error=youtube_api_not_enabled&message={quote(details[:220])}"))
        return redirect(_frontend_connections_url(f"youtube_error=youtube_api_failed&message={quote(details[:220])}"))

    yt_data = yt_resp.json() if yt_resp.content else {}
    items = yt_data.get("items") if isinstance(yt_data, dict) else None
    if not isinstance(items, list) or not items:
        return redirect(_frontend_connections_url("youtube_error=no_channel&message=В%20этом%20Google-аккаунте%20нет%20YouTube-канала.%20Создайте%20канал%20и%20повторите."))

    first = items[0] if isinstance(items[0], dict) else {}
    snippet = first.get("snippet") if isinstance(first.get("snippet"), dict) else {}
    thumbs = snippet.get("thumbnails") if isinstance(snippet.get("thumbnails"), dict) else {}
    thumb_default = thumbs.get("default") if isinstance(thumbs.get("default"), dict) else {}
    channel_id = str(first.get("id") or "").strip()
    channel_name = str(snippet.get("title") or "").strip() or "YouTube канал"
    channel_picture = str(thumb_default.get("url") or "").strip() or None

    db = SessionLocal()
    try:
        row = (
            db.query(SocialAccount)
            .filter(SocialAccount.user_id == user_id, SocialAccount.provider == "youtube")
            .order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc())
            .first()
        )
        if not row:
            row = SocialAccount(user_id=user_id, provider="youtube")
            db.add(row)
            db.flush()

        row.page_id = channel_id or row.page_id or f"yt-{user_id}"
        row.page_name = channel_name
        row.page_picture_url = channel_picture
        row.ig_user_id = None
        row.ig_username = None
        row.token_encrypted = encrypt_meta_token(access_token)
        row.token_expires_at = datetime.utcnow() + timedelta(seconds=max(0, expires_in))
        row.status = "connected_ready"
        row.status_reason_code = None
        row.updated_at = datetime.utcnow()
        row.last_success_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    return redirect(_frontend_connections_url("youtube_connected=1"))


@saas_api.route("/auth/oauth/google/callback", methods=["GET"])
def oauth_google_callback():
    state_token = (request.args.get("state") or "").strip()
    state_meta = _consume_oauth_state_meta(state_token)
    if not state_meta:
        return _oauth_redirect({"oauth_error": "state_invalid"})

    provider = str(state_meta.get("provider") or "").strip().lower()
    if provider == "youtube_connect":
        if request.args.get("error"):
            return redirect(_frontend_connections_url("youtube_error=oauth_denied"))
        user_id = int(state_meta.get("user_id") or 0)
        if not user_id:
            return redirect(_frontend_connections_url("youtube_error=state_invalid"))
        code = (request.args.get("code") or "").strip()
        if not code:
            return redirect(_frontend_connections_url("youtube_error=missing_code"))
        return _finalize_youtube_oauth_connect(user_id, code, _youtube_redirect_uri())

    if provider != "google":
        return _oauth_redirect({"oauth_error": "state_invalid"})
    if request.args.get("error"):
        return _oauth_redirect({"oauth_error": "google_denied"})

    code = (request.args.get("code") or "").strip()
    if not code:
        return _oauth_redirect({"oauth_error": "google_missing_code"})

    client_id = _google_client_id()
    client_secret = _google_client_secret()
    redirect_uri = _google_redirect_uri()
    if not client_id or not client_secret:
        return _oauth_redirect({"oauth_error": "google_not_configured"})

    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=12,
    )
    if not token_resp.ok:
        return _oauth_redirect({"oauth_error": "google_token_exchange_failed"})

    token_data = token_resp.json()
    access_token = (token_data.get("access_token") or "").strip()
    if not access_token:
        return _oauth_redirect({"oauth_error": "google_token_missing"})

    profile_resp = requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=12,
    )
    if not profile_resp.ok:
        return _oauth_redirect({"oauth_error": "google_profile_failed"})

    profile = profile_resp.json()
    email = (profile.get("email") or "").strip().lower()
    sub = (profile.get("sub") or "").strip()
    return _finalize_oauth_login(email, "google", sub)


@saas_api.route("/auth/oauth/facebook/start", methods=["GET"])
def oauth_facebook_start():
    client_id = _facebook_client_id()
    client_secret = _facebook_client_secret()
    redirect_uri = _facebook_redirect_uri()
    scope = _facebook_login_scope()
    if not client_id or not client_secret:
        return _oauth_redirect({"oauth_error": "facebook_not_configured"})

    state = _store_oauth_state("facebook")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "state": state,
    }
    return redirect(f"https://www.facebook.com/v20.0/dialog/oauth?{urlencode(params)}")


@saas_api.route("/auth/oauth/facebook/callback", methods=["GET"])
def oauth_facebook_callback():
    if request.args.get("error"):
        return _oauth_redirect({"oauth_error": "facebook_denied"})

    state_token = (request.args.get("state") or "").strip()
    if not _consume_oauth_state(state_token, "facebook"):
        return _oauth_redirect({"oauth_error": "state_invalid"})

    code = (request.args.get("code") or "").strip()
    if not code:
        return _oauth_redirect({"oauth_error": "facebook_missing_code"})

    client_id = _facebook_client_id()
    client_secret = _facebook_client_secret()
    redirect_uri = _facebook_redirect_uri()
    if not client_id or not client_secret:
        return _oauth_redirect({"oauth_error": "facebook_not_configured"})

    token_resp = requests.get(
        "https://graph.facebook.com/v20.0/oauth/access_token",
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=12,
    )
    if not token_resp.ok:
        return _oauth_redirect({"oauth_error": "facebook_token_exchange_failed"})

    token_data = token_resp.json()
    access_token = (token_data.get("access_token") or "").strip()
    if not access_token:
        return _oauth_redirect({"oauth_error": "facebook_token_missing"})

    profile_resp = requests.get(
        "https://graph.facebook.com/v20.0/me",
        params={"fields": "id,name,email", "access_token": access_token},
        timeout=12,
    )
    if not profile_resp.ok:
        return _oauth_redirect({"oauth_error": "facebook_profile_failed"})

    profile = profile_resp.json()
    email = (profile.get("email") or "").strip().lower()
    facebook_id = (profile.get("id") or "").strip()
    if not facebook_id:
        return _oauth_redirect({"oauth_error": "facebook_profile_failed"})
    if not email:
        # Some app modes do not allow requesting email permission.
        email = f"facebook_{facebook_id}@users.autosocial.local"
    return _finalize_oauth_login(email, "facebook", facebook_id)


@saas_api.route("/me", methods=["GET"])
@require_auth
def me():
    seed_plans()
    ensure_user_plan_and_credits(g.current_user.id)
    user = _current_user_refetched()
    normalized_plan = normalize_plan_code(user.plan)
    return jsonify(
        {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "plan": normalized_plan,
            "billing": get_billing_summary(user),
        }
    )


@saas_api.route("/plans", methods=["GET"])
def plans():
    seed_plans()
    return jsonify([to_plan_payload(spec) for spec in all_public_plan_specs()])


@saas_api.route("/platform-rules", methods=["GET"])
def platform_rules():
    db = SessionLocal()
    try:
        rows = db.query(PlatformRule).order_by(PlatformRule.platform.asc()).all()
        return jsonify(
            [
                {
                    "platform": r.platform,
                    "max_chars": r.max_chars,
                    "recommended_chars_min": r.recommended_chars_min,
                    "recommended_chars_max": r.recommended_chars_max,
                    "max_hashtags": r.max_hashtags,
                    "max_output_tokens_default": r.max_output_tokens_default,
                }
                for r in rows
            ]
        )
    finally:
        db.close()


@saas_api.route("/projects", methods=["GET"])
@require_auth
def list_projects():
    user = g.current_user
    db = SessionLocal()
    try:
        query = db.query(Project)
        if user.role != "admin":
            query = query.filter(Project.user_id == user.id)
        projects = query.order_by(Project.created_at.desc()).all()

        result = []
        for p in projects:
            posts_count = db.query(Post).filter(Post.project_id == p.id).count()
            result.append(
                {
                    "id": p.id,
                    "user_id": p.user_id,
                    "name": p.name,
                    "posts_count": posts_count,
                    "created_at": p.created_at.isoformat(),
                }
            )
        return jsonify(result)
    finally:
        db.close()


@saas_api.route("/projects", methods=["POST"])
@require_auth
def create_project():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"error": "Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ РїСЂРѕРµРєС‚Р°"}), 400
    if len(name) < 3:
        return jsonify({"error": "РќР°Р·РІР°РЅРёРµ РїСЂРѕРµРєС‚Р° СЃР»РёС€РєРѕРј РєРѕСЂРѕС‚РєРѕРµ"}), 400

    authz = authorizeAction(user, ACTION_PROJECT_CREATE, {})
    pw = _paywall_response_if_needed(authz)
    if pw:
        return pw

    db = SessionLocal()
    try:
        project = Project(user_id=user.id, name=name)
        db.add(project)
        db.commit()
        db.refresh(project)
        return jsonify({"id": project.id, "user_id": project.user_id, "name": project.name, "created_at": project.created_at.isoformat()})
    finally:
        db.close()


@saas_api.route("/projects/<int:project_id>", methods=["PATCH"])
@require_auth
def update_project(project_id: int):
    user = g.current_user
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"error": "Введите название проекта"}), 400
    if len(name) < 3:
        return jsonify({"error": "Название проекта слишком короткое"}), 400

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({"error": "Проект не найден"}), 404
        if user.role != "admin" and project.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403

        project.name = name
        db.commit()
        db.refresh(project)
        return jsonify(
            {
                "id": project.id,
                "user_id": project.user_id,
                "name": project.name,
                "created_at": project.created_at.isoformat(),
            }
        )
    finally:
        db.close()


@saas_api.route("/projects/<int:project_id>", methods=["DELETE"])
@require_auth
def delete_project(project_id: int):
    user = g.current_user
    data = request.get_json(silent=True) or {}
    confirm_name = (request.args.get("confirm_name") or data.get("confirm_name") or "").strip()
    return _delete_project_impl(user=user, project_id=project_id, confirm_name=confirm_name)


@saas_api.route("/projects/<int:project_id>/delete", methods=["POST"])
@require_auth
def delete_project_post(project_id: int):
    user = g.current_user
    data = request.get_json(silent=True) or {}
    confirm_name = (request.args.get("confirm_name") or data.get("confirm_name") or "").strip()
    return _delete_project_impl(user=user, project_id=project_id, confirm_name=confirm_name)


def _delete_project_impl(user, project_id: int, confirm_name: str):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({"error": "Проект не найден"}), 404
        if user.role != "admin" and project.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403

        if not confirm_name:
            return jsonify({"error": "Подтвердите удаление названием проекта"}), 400
        if confirm_name != project.name:
            return jsonify({"error": "Название проекта не совпадает. Удаление отменено."}), 400

        owner_user_id = project.user_id

        post_ids = [row[0] for row in db.query(Post.id).filter(Post.project_id == project.id).all()]
        db.query(ContentPlan).filter(ContentPlan.project_id == project.id).delete(synchronize_session=False)
        db.query(TopicSuggestion).filter(TopicSuggestion.project_id == project.id).delete(synchronize_session=False)
        if post_ids:
            db.query(CreditLedger).filter(CreditLedger.post_id.in_(post_ids)).delete(synchronize_session=False)
        db.query(Post).filter(Post.project_id == project.id).delete(synchronize_session=False)
        db.delete(project)
        db.commit()

        return jsonify({"ok": True, "deleted_project_id": project_id, "deleted_posts": len(post_ids)})
    finally:
        db.close()


@saas_api.route("/topics/suggestions", methods=["GET"])
@require_auth
def topics_suggestions():
    user = g.current_user
    project_id = request.args.get("project_id", type=int)
    category = request.args.get("category", type=str)

    if not project_id:
        return jsonify({"error": "РќСѓР¶РЅРѕ РїРµСЂРµРґР°С‚СЊ project_id"}), 400
    if not can_access_project(user, project_id):
        return jsonify({"error": "РЈ РІР°СЃ РЅРµС‚ РґРѕСЃС‚СѓРїР° Рє СЌС‚РѕРјСѓ РїСЂРѕРµРєС‚Сѓ"}), 403

    payload = get_topic_suggestions(user, project_id, category)
    return jsonify(payload)


@saas_api.route("/generate", methods=["POST"])
@require_auth
def generate():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}

    topic = (data.get("topic") or "").strip()
    category = (data.get("category") or "").strip() or None
    platform = (data.get("platform") or "instagram").strip().lower()
    if platform not in {"facebook", "instagram", "youtube"}:
        platform = "instagram"
    language = (data.get("language") or "ru").strip()
    tone = (data.get("tone") or "friendly").strip()
    prompt_text = (data.get("prompt_text") or "").strip()
    media_url = (data.get("media_url") or "").strip() or None
    generated_text_override = (data.get("generated_text") or "").strip() or None
    save_as_draft = bool(data.get("save_as_draft") or False)

    schedule_at_raw = (data.get("schedule_at") or "").strip()
    schedule_at = None
    if schedule_at_raw:
        try:
            schedule_at = datetime.fromisoformat(schedule_at_raw)
        except Exception:
            return jsonify({"error": "schedule_at должен быть в ISO формате"}), 400

    project_id_raw = data.get("project_id")
    try:
        project_id = int(project_id_raw) if project_id_raw is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "project_id РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ С‡РёСЃР»РѕРј"}), 400

    variant_count = int(data.get("variant_count") or 1)
    translation = bool(data.get("translation") or False)
    long_post_mode = bool(data.get("long_post_mode") or False)

    if not topic:
        return jsonify({"error": "РЈРєР°Р¶РёС‚Рµ С‚РµРјСѓ РїРѕСЃС‚Р°"}), 400

    if not project_id:
        project_id = get_or_create_default_project(user.id).id

    if not can_access_project(user, project_id):
        return jsonify({"error": "РЈ РІР°СЃ РЅРµС‚ РґРѕСЃС‚СѓРїР° Рє РїСЂРѕРµРєС‚Сѓ"}), 403

    # Enforce plan scheduling capability before doing any generation/cost.
    if schedule_at is not None:
        pw = _paywall_response_if_needed(authorizeAction(user, ACTION_SCHEDULE_CREATE, {"source": "/api/generate"}))
        if pw:
            return pw

    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_GENERATE, {"platform": platform}))
    if pw:
        return pw

    try:
        post = create_post_and_charge(
            user_id=user.id,
            project_id=project_id,
            platform=platform,
            topic=topic,
            category=category,
            tone=tone,
            language=language,
            prompt_text=prompt_text,
            media_url=media_url,
            schedule_at=schedule_at,
            variant_count=variant_count,
            translation=translation,
            long_post_mode=long_post_mode,
            generated_text_override=generated_text_override,
            save_as_draft=save_as_draft,
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 429
    except Exception as exc:
        msg = str(exc)
        # Normalize common OpenAI failures into user-facing errors and correct HTTP codes.
        if "insufficient_quota" in msg or "You exceeded your current quota" in msg:
            return (
                jsonify(
                    {
                        "error": "OpenAI: недостаточно квоты. Пополните баланс/лимит в OpenAI или включите USE_MOCK_PROVIDERS=true для локального теста.",
                    }
                ),
                402,
            )
        if "Error code: 429" in msg:
            return jsonify({"error": "OpenAI: rate limit/429. Попробуйте позже."}), 429
        return jsonify({"error": f"Ошибка генерации: {msg}"}), 500

    recordUsageEvent(user, "POSTS_GENERATED", 1, {"endpoint": "/api/generate", "platform": platform, "post_id": post.id})

    billing = get_billing_summary(_current_user_refetched())
    return (
        jsonify(
            {
                "id": post.id,
                "status": post.status,
                "platform": post.platform,
                "media_url": post.media_url,
                "billing": billing,
            }
        ),
        202,
    )


@saas_api.route("/generate-preview", methods=["POST"])
@require_auth
def generate_preview():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}

    topic = (data.get("topic") or "").strip()
    category = (data.get("category") or "").strip() or None
    language = (data.get("language") or "ru").strip()
    tone = (data.get("tone") or "friendly").strip()
    platforms_raw = data.get("platforms")
    platforms = []
    if isinstance(platforms_raw, list):
        for item in platforms_raw:
            key = str(item or "").strip().lower()
            if key in {"facebook", "instagram", "youtube"} and key not in platforms:
                platforms.append(key)

    project_id_raw = data.get("project_id")
    if project_id_raw is not None:
        try:
            project_id = int(project_id_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "project_id должен быть числом"}), 400
        if not can_access_project(user, project_id):
            return jsonify({"error": "У вас нет доступа к проекту"}), 403

    if not topic:
        return jsonify({"error": "Укажите тему поста"}), 400

    try:
        payload = generate_post_preview_text(
            topic=topic,
            category=category,
            tone=tone,
            language=language,
            platforms=platforms,
        )
    except Exception as exc:
        msg = str(exc)
        if "insufficient_quota" in msg or "You exceeded your current quota" in msg:
            return jsonify({"error": "OpenAI: недостаточно квоты для генерации предпросмотра."}), 402
        if "Error code: 429" in msg:
            return jsonify({"error": "OpenAI: rate limit/429. Повторите через минуту."}), 429
        return jsonify({"error": f"Ошибка генерации предпросмотра: {msg}"}), 500

    return jsonify(payload)


def _json_loads_list(raw: str) -> list:
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except Exception:
        return []


def _json_loads_dict(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _content_brief_payload(row: ContentBrief) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "topic": row.topic,
        "offer": row.offer,
        "language": row.language,
        "tone": row.tone,
        "goal": row.goal,
        "platforms": _json_loads_list(row.platforms_json),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _content_draft_payload(row: ContentDraft) -> dict:
    return {
        "id": row.id,
        "brief_id": row.brief_id,
        "platform": row.platform,
        "variant": row.variant_index,
        "post_text": row.post_text,
        "title": row.title,
        "description": row.description,
        "hashtags": _json_loads_list(row.hashtags_json),
        "cta": row.cta,
        "asset_ideas": _json_loads_list(row.asset_ideas_json),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _create_post_from_content_draft(
    *,
    user: AppUser,
    draft: ContentDraft,
    brief: ContentBrief,
    project_id: int,
    schedule_at: datetime | None,
):
    if not can_access_project(user, project_id):
        return None, (jsonify({"error": "У вас нет доступа к проекту"}), 403)

    generated_text = (draft.post_text or "").strip()
    if draft.platform == "youtube":
        title = (draft.title or "").strip()
        description = (draft.description or "").strip()
        if title or description:
            generated_text = f"Title: {title}\n\n{description or generated_text}".strip()

    try:
        post = create_post_and_charge(
            user_id=user.id,
            project_id=project_id,
            platform=draft.platform,
            topic=(brief.topic or "").strip()[:500] or "Контент-идея",
            category="content_brief",
            tone=brief.tone or "neutral",
            language=brief.language or "ru",
            prompt_text=(brief.offer or "").strip(),
            media_url=None,
            schedule_at=schedule_at,
            variant_count=1,
            translation=False,
            long_post_mode=(draft.platform in {"facebook", "instagram"}),
            generated_text_override=generated_text,
            save_as_draft=(schedule_at is None),
        )
        return post, None
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 429)
    except Exception as exc:
        msg = str(exc)
        if "insufficient_quota" in msg or "You exceeded your current quota" in msg:
            return None, (jsonify({"error": "OpenAI: недостаточно квоты для сохранения черновика."}), 402)
        if "Error code: 429" in msg:
            return None, (jsonify({"error": "OpenAI: rate limit/429. Повторите позже."}), 429)
        return None, (jsonify({"error": f"Ошибка сохранения черновика: {msg}"}), 500)


@saas_api.route("/content/generate", methods=["POST"])
@require_auth
def content_generate():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}

    topic = (data.get("topic") or "").strip()
    offer_raw = data.get("offer")
    offer = (offer_raw or "").strip() if offer_raw is not None else None
    offer = offer if offer else None
    language = (data.get("language") or "ru").strip().lower()
    tone = (data.get("tone") or "neutral").strip().lower()
    goal = (data.get("goal") or "engagement").strip().lower()
    try:
        variants = int(data.get("variants") or 1)
    except (TypeError, ValueError):
        return jsonify({"error": "variants должен быть числом 1..3"}), 400
    platforms_raw = data.get("platforms") if isinstance(data.get("platforms"), list) else []
    platforms = []
    for item in platforms_raw:
        key = str(item or "").strip().lower()
        if key in {"facebook", "instagram", "youtube"} and key not in platforms:
            platforms.append(key)

    if not topic:
        return jsonify({"error": "Поле 'Тема/идея' обязательно"}), 400
    if not platforms:
        return jsonify({"error": "Выберите хотя бы одну платформу"}), 400
    if variants not in {1, 2, 3}:
        return jsonify({"error": "variants должен быть 1..3"}), 400

    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_GENERATE, {"endpoint": "/api/content/generate"}))
    if pw:
        return pw

    try:
        generated = generate_strategy_and_drafts(
            topic=topic,
            offer=offer,
            language=language,
            tone=tone,
            goal=goal,
            platforms=platforms,
            variants=variants,
        )
    except OpenAIClientError as exc:
        msg = str(exc)
        if "429" in msg.lower():
            return jsonify({"error": "GPT временно перегружен. Нажмите Retry через 20-30 секунд."}), 429
        return jsonify({"error": f"GPT error: {msg}"}), 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Ошибка генерации контента: {exc}"}), 500

    db = SessionLocal()
    try:
        brief = ContentBrief(
            user_id=user.id,
            topic=topic,
            offer=offer,
            language=language,
            tone=tone,
            goal=goal,
            platforms_json=json.dumps(platforms, ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
        db.add(brief)
        db.flush()

        strategy_row = ContentStrategy(
            brief_id=brief.id,
            strategy_json=json.dumps(generated.strategy, ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
        db.add(strategy_row)

        draft_rows = []
        for row in generated.drafts:
            draft = ContentDraft(
                brief_id=brief.id,
                platform=str(row.get("platform") or "").strip().lower(),
                variant_index=int(row.get("variant_index") or 1),
                post_text=(row.get("post_text") or "").strip(),
                title=(row.get("title") or None),
                description=(row.get("description") or None),
                hashtags_json=json.dumps(row.get("hashtags") or [], ensure_ascii=False),
                cta=(row.get("cta") or None),
                asset_ideas_json=json.dumps(row.get("asset_ideas") or [], ensure_ascii=False),
                created_at=datetime.utcnow(),
            )
            db.add(draft)
            draft_rows.append(draft)

        db.commit()
        for row in draft_rows:
            db.refresh(row)
        db.refresh(brief)
    finally:
        db.close()

    return jsonify(
        {
            "status": generated.status,
            "brief_id": brief.id,
            "strategy": generated.strategy,
            "drafts": [_content_draft_payload(d) for d in draft_rows],
            "warnings": generated.warnings or [],
            "debug_code": generated.debug_code or "",
            "usage": {"input_tokens": generated.token_input, "output_tokens": generated.token_output},
        }
    )


@saas_api.route("/create/suggest", methods=["POST"])
@require_auth
def create_suggest():
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"status": "error", "drafts": [], "warnings": ["topic is required"], "debug_code": "missing_topic"}), 400
    try:
        suggestions = generate_quick_suggestions(
            topic=topic,
            offer=(data.get("offer") or "").strip() or None,
            goal=_normalize_create_goal(data.get("goal") or "engagement"),
            tone=_normalize_create_tone(data.get("tone") or "friendly"),
            language=str(data.get("language") or "ru").strip().lower() or "ru",
        )
        return jsonify(
            {
                "status": suggestions.get("status", "ok"),
                "suggestions": {
                    "hook": suggestions.get("hook") or "",
                    "angles": suggestions.get("angles") or [],
                    "cta_variants": suggestions.get("cta_variants") or [],
                },
                "drafts": [],
                "warnings": suggestions.get("warnings") or [],
                "debug_code": suggestions.get("debug_code") or "",
            }
        )
    except Exception as exc:
        return jsonify({"status": "error", "drafts": [], "warnings": [str(exc)], "debug_code": "suggest_error"}), 500


@saas_api.route("/create/rewrite", methods=["POST"])
@require_auth
def create_rewrite():
    data = request.get_json(silent=True) or {}
    caption = (data.get("caption") or "").strip()
    if not caption:
        return jsonify({"status": "error", "drafts": [], "warnings": ["caption is required"], "debug_code": "missing_caption"}), 400
    try:
        rewritten = rewrite_caption_safe(
            caption=caption,
            instruction=(data.get("instruction") or "короче").strip(),
            goal=_normalize_create_goal(data.get("goal") or "engagement"),
            tone=_normalize_create_tone(data.get("tone") or "friendly"),
            language=str(data.get("language") or "ru").strip().lower() or "ru",
        )
        return jsonify(
            {
                "status": rewritten.get("status") or "ok",
                "drafts": [
                    {
                        "caption": rewritten.get("caption") or "",
                        "cta": rewritten.get("cta") or "",
                        "hashtags": rewritten.get("hashtags") or [],
                    }
                ],
                "warnings": rewritten.get("warnings") or [],
                "debug_code": rewritten.get("debug_code") or "",
            }
        )
    except Exception as exc:
        return jsonify({"status": "error", "drafts": [], "warnings": [str(exc)], "debug_code": "rewrite_error"}), 500


@saas_api.route("/create/quality-check", methods=["POST"])
@require_auth
def create_quality_check():
    data = request.get_json(silent=True) or {}
    caption = (data.get("caption") or "").strip()
    cta = (data.get("cta") or "").strip()
    tags_raw = data.get("hashtags")
    tags = []
    if isinstance(tags_raw, str):
        tags = [t for t in tags_raw.split() if t.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(t).strip() for t in tags_raw if str(t).strip()]
    result = _quality_check_payload(caption=caption, cta=cta, hashtags=tags, goal=str(data.get("goal") or "engagement"))
    return jsonify({"status": "ok", "drafts": [], "quality": result, "warnings": result.get("warnings") or [], "debug_code": ""})


@saas_api.route("/create/generate", methods=["POST"])
@require_auth
def create_generate():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}

    topic = (data.get("topic") or "").strip()
    offer_raw = data.get("offer")
    offer = (offer_raw or "").strip() if offer_raw is not None else None
    offer = offer if offer else None
    language = (data.get("language") or "ru").strip().lower()
    tone = _normalize_create_tone(data.get("tone") or "friendly")
    goal = _normalize_create_goal(data.get("goal") or "engagement")
    mode = str(data.get("mode") or "pro").strip().lower()
    try:
        variants = int(data.get("variants") or (1 if mode == "quick" else 3))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "drafts": [], "warnings": ["variants должен быть числом 1..3"], "debug_code": "bad_variants"}), 400
    variants = max(1, min(variants, 3))
    platforms_raw = data.get("platforms") if isinstance(data.get("platforms"), list) else []
    platforms = []
    for item in platforms_raw:
        key = str(item or "").strip().lower()
        if key in {"facebook", "instagram", "youtube"} and key not in platforms:
            platforms.append(key)
    if not topic:
        return jsonify({"status": "error", "drafts": [], "warnings": ["Поле 'Тема/идея' обязательно"], "debug_code": "missing_topic"}), 400
    if not platforms:
        return jsonify({"status": "error", "drafts": [], "warnings": ["Выберите хотя бы одну платформу"], "debug_code": "missing_platforms"}), 400

    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_GENERATE, {"endpoint": "/api/create/generate"}))
    if pw:
        return pw

    try:
        generated = generate_strategy_and_drafts(
            topic=topic,
            offer=offer,
            language=language,
            tone=tone,
            goal=goal,
            platforms=platforms,
            variants=variants,
        )
    except OpenAIClientError as exc:
        msg = str(exc)
        if "429" in msg.lower():
            return jsonify({"status": "error", "drafts": [], "warnings": ["GPT временно перегружен. Повторите позже."], "debug_code": "openai_429"}), 429
        return jsonify({"status": "error", "drafts": [], "warnings": [f"GPT error: {msg}"], "debug_code": "openai_error"}), 502
    except ValueError as exc:
        return jsonify({"status": "error", "drafts": [], "warnings": [str(exc)], "debug_code": "validation_error"}), 400
    except Exception as exc:
        return jsonify({"status": "error", "drafts": [], "warnings": [f"Ошибка генерации: {exc}"], "debug_code": "unknown_error"}), 500

    db = SessionLocal()
    try:
        brief = ContentBrief(
            user_id=user.id,
            topic=topic,
            offer=offer,
            language=language,
            tone=tone,
            goal=goal,
            platforms_json=json.dumps(platforms, ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
        db.add(brief)
        db.flush()

        strategy_row = ContentStrategy(
            brief_id=brief.id,
            strategy_json=json.dumps(generated.strategy, ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
        db.add(strategy_row)

        draft_rows = []
        for row in generated.drafts:
            draft = ContentDraft(
                brief_id=brief.id,
                platform=str(row.get("platform") or "").strip().lower(),
                variant_index=int(row.get("variant_index") or 1),
                post_text=(row.get("post_text") or "").strip(),
                title=(row.get("title") or None),
                description=(row.get("description") or None),
                hashtags_json=json.dumps(row.get("hashtags") or [], ensure_ascii=False),
                cta=(row.get("cta") or None),
                asset_ideas_json=json.dumps(row.get("asset_ideas") or [], ensure_ascii=False),
                created_at=datetime.utcnow(),
            )
            db.add(draft)
            draft_rows.append(draft)
        db.commit()
        for row in draft_rows:
            db.refresh(row)
        db.refresh(brief)
        recordUsageEvent(
            user,
            "POSTS_GENERATED",
            1,
            {"endpoint": "/api/create/generate", "brief_id": brief.id, "platforms": platforms, "variants": variants},
        )
    finally:
        db.close()

    safe_drafts = [_content_draft_payload(d) for d in draft_rows]
    quality = _quality_check_payload(
        caption=(safe_drafts[0]["post_text"] if safe_drafts else ""),
        cta=(safe_drafts[0]["cta"] if safe_drafts else ""),
        hashtags=(safe_drafts[0]["hashtags"] if safe_drafts else []),
        goal=goal,
    )
    return jsonify(
        {
            "status": generated.status or "ok",
            "brief_id": brief.id,
            "strategy": generated.strategy,
            "drafts": safe_drafts,
            "quality": quality,
            "warnings": (generated.warnings or []) + (quality.get("warnings") or []),
            "debug_code": generated.debug_code or "",
            "usage": {"input_tokens": generated.token_input, "output_tokens": generated.token_output},
        }
    )


@saas_api.route("/create/templates", methods=["GET"])
@require_auth
def create_templates_list():
    user = g.current_user
    db = SessionLocal()
    try:
        rows = (
            db.query(UserTemplate)
            .filter(UserTemplate.user_id == user.id)
            .order_by(UserTemplate.updated_at.desc(), UserTemplate.id.desc())
            .limit(100)
            .all()
        )
        return jsonify({"status": "ok", "items": [_template_payload(r) for r in rows], "warnings": [], "debug_code": ""})
    finally:
        db.close()


@saas_api.route("/create/niche-catalog", methods=["GET"])
@require_auth
def create_niche_catalog():
    db = SessionLocal()
    try:
        niches = db.query(Niche).order_by(Niche.sort_order.asc(), Niche.id.asc()).all()
        items = []
        for niche in niches:
            templates = (
                db.query(Template)
                .filter(Template.niche_id == niche.id)
                .order_by(Template.sort_order.asc(), Template.id.asc())
                .all()
            )
            items.append(_catalog_niche_payload(niche, templates))
        return jsonify({"status": "ok", "items": items, "warnings": [], "debug_code": ""})
    finally:
        db.close()


@saas_api.route("/create/templates/import-catalog", methods=["POST"])
@require_auth
def create_templates_import_catalog():
    user = g.current_user
    data = request.get_json(silent=True) or {}
    niche_slug = str(data.get("niche_slug") or "").strip().lower()
    template_slug = str(data.get("template_slug") or "").strip().lower()
    if not niche_slug or not template_slug:
        return jsonify({"status": "error", "warnings": ["niche_slug and template_slug are required"], "debug_code": "missing_catalog_keys"}), 400
    db = SessionLocal()
    try:
        niche = db.query(Niche).filter(Niche.slug == niche_slug).first()
        if not niche:
            return jsonify({"status": "error", "warnings": ["niche not found"], "debug_code": "catalog_niche_not_found"}), 404
        template = (
            db.query(Template)
            .filter(Template.niche_id == niche.id, Template.slug == template_slug)
            .first()
        )
        if not template:
            return jsonify({"status": "error", "warnings": ["template not found"], "debug_code": "catalog_template_not_found"}), 404
        preset = {
            "source": "catalog",
            "niche_slug": niche.slug,
            "niche_title": niche.title,
            "template_slug": template.slug,
            "template_type": template.type,
            "platform": template.platform,
            "goal": template.goal,
            "tone": template.tone,
            "hook_line": template.hook_line,
            "cta": template.cta,
            "prompt_system": template.prompt_system,
            "prompt_user": template.prompt_user,
            "variables_schema_json": _json_loads_safe(template.variables_schema_json, {}),
            "preview_text": template.preview_text,
        }
        row = UserTemplate(
            user_id=user.id,
            name=f"{niche.title} · {template.title}"[:160],
            preset_json=json.dumps(preset, ensure_ascii=False),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify({"status": "ok", "item": _template_payload(row), "warnings": [], "debug_code": ""}), 201
    finally:
        db.close()


@saas_api.route("/ai/director/suggest", methods=["POST"])
@require_auth
def ai_director_suggest():
    data = request.get_json(silent=True) or {}
    topic = str(data.get("topic") or data.get("niche") or "").strip()
    niche_label = str(data.get("niche_label") or "").strip() or None
    niche_context = data.get("niche_context") if isinstance(data.get("niche_context"), dict) else None
    if not topic:
        return jsonify({"status": "error", "data": {}, "warnings": ["topic is required"], "debug_code": "missing_topic"}), 400
    platforms = data.get("platforms") if isinstance(data.get("platforms"), list) else []
    variation_seed = int(data.get("variation_seed") or 0)
    if variation_seed < 0:
        variation_seed = 0
    try:
        out = director_suggest(
            topic=topic,
            offer=(data.get("offer") or "").strip() or None,
            language=str(data.get("language") or "ru").strip().lower() or "ru",
            tone=_normalize_create_tone(data.get("tone") or "friendly"),
            goal=_normalize_create_goal(data.get("goal") or "engagement"),
            platforms=platforms,
            niche_label=niche_label,
            niche_context=niche_context,
            variation_seed=variation_seed,
        )
        return jsonify(
            {
                "status": out.get("status") or "ok",
                "data": out.get("data") or {},
                "warnings": _summarize_director_warnings(out.get("warnings") or []),
                "debug_code": out.get("debug_code") or "",
            }
        )
    except Exception as exc:
        return jsonify({"status": "error", "data": {}, "warnings": [str(exc)], "debug_code": "director_suggest_error"}), 500


@saas_api.route("/ai/director/generate-drafts", methods=["POST"])
@require_auth
def ai_director_generate_drafts():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    topic = str(data.get("topic") or "").strip()
    angle = str(data.get("angle") or "").strip()
    niche_label = str(data.get("niche_label") or "").strip() or None
    niche_context = data.get("niche_context") if isinstance(data.get("niche_context"), dict) else None
    if not topic:
        return jsonify({"status": "error", "data": {}, "warnings": ["topic is required"], "debug_code": "missing_topic"}), 400
    if not angle:
        return jsonify({"status": "error", "data": {}, "warnings": ["angle is required"], "debug_code": "missing_angle"}), 400
    platforms_raw = data.get("platforms") if isinstance(data.get("platforms"), list) else []
    platforms = []
    for item in platforms_raw:
        key = str(item or "").strip().lower()
        if key in {"facebook", "instagram", "youtube"} and key not in platforms:
            platforms.append(key)
    if not platforms:
        platforms = ["facebook", "instagram"]

    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_GENERATE, {"endpoint": "/api/ai/director/generate-drafts"}))
    if pw:
        return pw

    try:
        out = director_generate_drafts(
            topic=topic,
            offer=(data.get("offer") or "").strip() or None,
            angle=angle,
            goal=_normalize_create_goal(data.get("goal") or "engagement"),
            platforms=platforms,
            tone=_normalize_create_tone(data.get("tone") or "friendly"),
            language=str(data.get("language") or "ru").strip().lower() or "ru",
            niche_label=niche_label,
            niche_context=niche_context,
            variants=max(1, min(int(data.get("variants") or 3), 3)),
        )
    except OpenAIClientError as exc:
        return jsonify({"status": "error", "data": {}, "warnings": [str(exc)], "debug_code": "openai_error"}), 502
    except Exception as exc:
        return jsonify({"status": "error", "data": {}, "warnings": [str(exc)], "debug_code": "director_drafts_error"}), 500

    drafts = list((out.get("data") or {}).get("drafts") or [])
    db = SessionLocal()
    draft_rows = []
    brief = None
    brief_id = None
    try:
        brief = ContentBrief(
            user_id=user.id,
            topic=topic,
            offer=(data.get("offer") or "").strip() or None,
            language=str(data.get("language") or "ru").strip().lower() or "ru",
            tone=_normalize_create_tone(data.get("tone") or "friendly"),
            goal=_normalize_create_goal(data.get("goal") or "engagement"),
            platforms_json=json.dumps(platforms, ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
        db.add(brief)
        db.flush()
        brief_id = int(brief.id)
        strategy_payload = (out.get("data") or {}).get("strategy")
        if not isinstance(strategy_payload, dict):
            strategy_payload = {}
        db.add(
            ContentStrategy(
                brief_id=brief.id,
                strategy_json=json.dumps(strategy_payload, ensure_ascii=False),
                created_at=datetime.utcnow(),
            )
        )
        for row in drafts:
            d = ContentDraft(
                brief_id=brief.id,
                platform=str(row.get("platform") or "facebook").strip().lower(),
                variant_index=int(row.get("variant") or 1),
                post_text=str(row.get("body_text") or "").strip(),
                title=None,
                description=None,
                hashtags_json=json.dumps(row.get("hashtags") or [], ensure_ascii=False),
                cta=str(row.get("cta") or "").strip() or None,
                asset_ideas_json=json.dumps([], ensure_ascii=False),
                created_at=datetime.utcnow(),
            )
            db.add(d)
            draft_rows.append(d)
        db.commit()
        for d in draft_rows:
            db.refresh(d)
        recordUsageEvent(
            user,
            "POSTS_GENERATED",
            1,
            {
                "endpoint": "/api/ai/director/generate-drafts",
                "brief_id": brief_id,
                "platforms": platforms,
                "variants": max(1, min(int(data.get("variants") or 3), 3)),
            },
        )
    finally:
        db.close()

    return jsonify(
        {
            "status": out.get("status") or "ok",
            "data": {
                "brief_id": brief_id,
                "drafts": [_content_draft_payload(d) for d in draft_rows],
                "strategy": (out.get("data") or {}).get("strategy") or {},
            },
            "warnings": _summarize_director_warnings(out.get("warnings") or []),
            "debug_code": out.get("debug_code") or "",
        }
    )


@saas_api.route("/ai/director/rewrite", methods=["POST"])
@require_auth
def ai_director_rewrite():
    data = request.get_json(silent=True) or {}
    caption = str(data.get("caption") or "").strip()
    if not caption:
        return jsonify({"status": "error", "data": {}, "warnings": ["caption is required"], "debug_code": "missing_caption"}), 400
    try:
        rewritten = rewrite_caption_safe(
            caption=caption,
            instruction=(data.get("instruction") or "короче").strip(),
            goal=_normalize_create_goal(data.get("goal") or "engagement"),
            tone=_normalize_create_tone(data.get("tone") or "friendly"),
            language=str(data.get("language") or "ru").strip().lower() or "ru",
        )
        return jsonify(
            {
                "status": rewritten.get("status") or "ok",
                "data": {
                    "caption": rewritten.get("caption") or "",
                    "cta": rewritten.get("cta") or "",
                    "hashtags": rewritten.get("hashtags") or [],
                },
                "warnings": rewritten.get("warnings") or [],
                "debug_code": rewritten.get("debug_code") or "",
            }
        )
    except Exception as exc:
        return jsonify({"status": "error", "data": {}, "warnings": [str(exc)], "debug_code": "rewrite_error"}), 500


@saas_api.route("/ai/director/generate-image", methods=["POST"])
@require_auth
def ai_director_generate_image():
    data = request.get_json(silent=True) or {}
    topic = str(data.get("topic") or "").strip()
    if not topic:
        return jsonify({"status": "error", "data": {}, "warnings": ["topic is required"], "debug_code": "missing_topic"}), 400
    caption = str(data.get("caption") or "").strip()
    niche_label = str(data.get("niche_label") or "").strip()
    niche_context_raw = data.get("niche_context")
    niche_context = ""
    niche_hint_parts: list[str] = []
    if isinstance(niche_context_raw, dict):
        niche_context = str(niche_context_raw.get("id") or niche_context_raw.get("label") or "").strip()
        keyword_values = niche_context_raw.get("keywords") if isinstance(niche_context_raw.get("keywords"), list) else []
        niche_hint_parts.extend([str(item or "").strip() for item in keyword_values if str(item or "").strip()][:6])
        image_guidelines = niche_context_raw.get("imageGuidelines") if isinstance(niche_context_raw.get("imageGuidelines"), dict) else {}
        for field in ("focus", "mood"):
            value = str(image_guidelines.get(field) or "").strip()
            if value:
                niche_hint_parts.append(value)
    else:
        niche_context = str(niche_context_raw or "").strip()
    asset_ideas_raw = data.get("asset_ideas") if isinstance(data.get("asset_ideas"), list) else []
    asset_ideas = [str(item or "").strip() for item in asset_ideas_raw if str(item or "").strip()][:6]
    language = str(data.get("language") or "ru").strip().lower() or "ru"
    tone = _normalize_create_tone(data.get("tone") or "friendly")
    style = str(data.get("style") or "???????????").strip()
    no_text_on_image = bool(data.get("no_text_on_image") is not False)
    realism = bool(data.get("realism") is not False)

    prompt_topic = f"{topic}. ?????: {style}."
    if realism:
        prompt_topic += " ???????????? ?????."
    if no_text_on_image:
        prompt_topic += " ??? ??????, ????????, ????????? ? ??????? ??????."
    prompt_topic += " ????? ??????????? ?????? ?????????? ???? ?????."

    project_id_raw = data.get("project_id")
    try:
        project_id = int(project_id_raw) if project_id_raw not in (None, "") else None
    except (TypeError, ValueError):
        project_id = None
    used_external_ids = {
        str(item or "").strip()
        for item in (data.get("used_external_ids") if isinstance(data.get("used_external_ids"), list) else [])
        if str(item or "").strip()
    }
    used_urls = {
        str(item or "").strip()
        for item in (data.get("used_urls") if isinstance(data.get("used_urls"), list) else [])
        if str(item or "").strip()
    }

    warnings = []
    source = "pexels"
    search_context = "\n".join(part for part in [caption, *asset_ideas, *niche_hint_parts] if part).strip() or None
    image_url = None
    media = None
    try:
        db = SessionLocal()
        try:
            media = _fetch_post_media_or_error(
                niche=niche_context or niche_label or topic,
                topic=topic,
                platform="instagram",
                post_text=search_context,
                db=db,
                project_id=project_id,
                used_external_ids=used_external_ids,
                used_urls=used_urls,
            )
        finally:
            db.close()
        image_url = str(media.local_url or "").strip() or None
    except (PexelsConfigError, PexelsRateLimitError, PexelsRequestError, PexelsEmptyResultError):
        image_url = None

    if not image_url:
        source = "fallback"
        warnings.append("image_fallback_used")
        image_url = build_semantic_fallback_image_url(
            topic=prompt_topic,
            category=niche_context or niche_label or "business",
            tone=tone,
            language=language,
            caption=caption or None,
            asset_ideas=asset_ideas,
        )

    mirrored = None
    if not str(image_url or "").strip().lower().endswith(".svg"):
        mirrored = _download_and_store_binary(image_url, ".jpg")
    final_url = mirrored[0] if mirrored else image_url
    return jsonify(
        {
            "status": "ok",
            "data": {
                "image_url": final_url,
                "source": source,
                "external_id": str(getattr(media, "external_id", "") or "").strip() or None,
            },
            "warnings": warnings,
            "debug_code": "director_image_ok" if source == "pexels" else "director_image_fallback",
        }
    )


@saas_api.route("/ai/quality-check", methods=["POST"])
@require_auth
def ai_quality_check():
    data = request.get_json(silent=True) or {}
    caption = str(data.get("caption") or "").strip()
    cta = str(data.get("cta") or "").strip()
    tags_raw = data.get("hashtags")
    tags = []
    if isinstance(tags_raw, str):
        tags = [t for t in tags_raw.split() if t.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(t).strip() for t in tags_raw if str(t).strip()]
    quality = _quality_check_payload(caption=caption, cta=cta, hashtags=tags, goal=str(data.get("goal") or "engagement"))
    return jsonify({"status": "ok", "data": {"quality": quality}, "warnings": quality.get("warnings") or [], "debug_code": ""})


@saas_api.route("/preview/thumbnail", methods=["POST"])
@require_auth
def preview_thumbnail():
    data = request.get_json(silent=True) or {}
    video_url = str(data.get("video_url") or "").strip()
    if not video_url:
        return jsonify({"status": "error", "data": {}, "warnings": ["video_url is required"], "debug_code": "missing_video_url"}), 400
    thumb_url = _build_video_thumbnail(video_url=video_url, second=float(data.get("second") or 0.8))
    if not thumb_url:
        return jsonify({"status": "partial", "data": {"thumbnail_url": None}, "warnings": ["thumbnail_generation_failed"], "debug_code": "thumb_failed"})
    return jsonify({"status": "ok", "data": {"thumbnail_url": thumb_url}, "warnings": [], "debug_code": ""})


@saas_api.route("/preview/validate", methods=["POST"])
@require_auth
def preview_validate():
    data = request.get_json(silent=True) or {}
    payload = _normalize_preview_payload(data.get("payload") if isinstance(data.get("payload"), dict) else data)
    out = _validate_preview_payload(payload)
    status = "error" if out.get("has_error") else ("partial" if out.get("warnings") else "ok")
    return jsonify(
        {
            "status": status,
            "data": {
                "preview": out.get("payload"),
                "score": int(out.get("score") or 0),
                "warnings": out.get("warnings") or [],
                "suggestions": out.get("suggestions") or [],
            },
            "warnings": [w.get("message") for w in (out.get("warnings") or []) if isinstance(w, dict)],
            "debug_code": "",
        }
    )


@saas_api.route("/create/templates", methods=["POST"])
@require_auth
def create_templates_save():
    user = g.current_user
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    preset = data.get("preset") if isinstance(data.get("preset"), dict) else {}
    if not name:
        return jsonify({"status": "error", "warnings": ["name is required"], "debug_code": "missing_name"}), 400
    db = SessionLocal()
    try:
        row = UserTemplate(
            user_id=user.id,
            name=name[:160],
            preset_json=json.dumps(preset, ensure_ascii=False),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify({"status": "ok", "item": _template_payload(row), "warnings": [], "debug_code": ""}), 201
    finally:
        db.close()


@saas_api.route("/create/templates/<int:template_id>", methods=["DELETE"])
@require_auth
def create_templates_delete(template_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        row = db.query(UserTemplate).filter(UserTemplate.id == template_id).first()
        if not row:
            return jsonify({"status": "error", "warnings": ["template not found"], "debug_code": "not_found"}), 404
        if row.user_id != user.id and user.role != "admin":
            return jsonify({"status": "error", "warnings": ["Недостаточно прав"], "debug_code": "forbidden"}), 403
        db.delete(row)
        db.commit()
        return jsonify({"status": "ok", "deleted_id": template_id, "warnings": [], "debug_code": ""})
    finally:
        db.close()


@saas_api.route("/content/briefs", methods=["GET"])
@require_auth
def content_briefs_list():
    user = g.current_user
    limit = max(1, min(int(request.args.get("limit") or 20), 100))
    db = SessionLocal()
    try:
        query = db.query(ContentBrief)
        if user.role != "admin":
            query = query.filter(ContentBrief.user_id == user.id)
        rows = query.order_by(ContentBrief.created_at.desc()).limit(limit).all()
        return jsonify([_content_brief_payload(r) for r in rows])
    finally:
        db.close()


@saas_api.route("/content/briefs/<int:brief_id>", methods=["GET"])
@require_auth
def content_brief_details(brief_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        brief = db.query(ContentBrief).filter(ContentBrief.id == brief_id).first()
        if not brief:
            return jsonify({"error": "brief not found"}), 404
        if user.role != "admin" and brief.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403

        strategy = (
            db.query(ContentStrategy)
            .filter(ContentStrategy.brief_id == brief.id)
            .order_by(ContentStrategy.created_at.desc())
            .first()
        )
        drafts = (
            db.query(ContentDraft)
            .filter(ContentDraft.brief_id == brief.id)
            .order_by(ContentDraft.platform.asc(), ContentDraft.variant_index.asc(), ContentDraft.id.asc())
            .all()
        )
        return jsonify(
            {
                "brief": _content_brief_payload(brief),
                "strategy": _json_loads_dict(strategy.strategy_json) if strategy else {},
                "drafts": [_content_draft_payload(d) for d in drafts],
            }
        )
    finally:
        db.close()


@saas_api.route("/content/drafts/<int:draft_id>/schedule", methods=["POST"])
@require_auth
def content_draft_schedule(draft_id: int):
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    project_id_raw = data.get("project_id")
    schedule_at_raw = (data.get("schedule_at") or "").strip()
    if not schedule_at_raw:
        return jsonify({"error": "Передайте schedule_at"}), 400
    try:
        schedule_at = _parse_iso_datetime(schedule_at_raw)
    except Exception:
        return jsonify({"error": "schedule_at должен быть в ISO формате"}), 400

    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_SCHEDULE_CREATE, {"source": "/api/content/drafts/schedule"}))
    if pw:
        return pw
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_GENERATE, {"source": "/api/content/drafts/schedule"}))
    if pw:
        return pw

    db = SessionLocal()
    try:
        draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id).first()
        if not draft:
            return jsonify({"error": "draft not found"}), 404
        brief = db.query(ContentBrief).filter(ContentBrief.id == draft.brief_id).first()
        if not brief:
            return jsonify({"error": "brief not found"}), 404
        if user.role != "admin" and brief.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
    finally:
        db.close()

    try:
        project_id = int(project_id_raw) if project_id_raw else get_or_create_default_project(user.id).id
    except Exception:
        return jsonify({"error": "project_id должен быть числом"}), 400

    post, err = _create_post_from_content_draft(
        user=user,
        draft=draft,
        brief=brief,
        project_id=project_id,
        schedule_at=schedule_at,
    )
    if err:
        return err
    recordUsageEvent(user, "POSTS_GENERATED", 1, {"endpoint": "/api/content/drafts/schedule", "post_id": post.id})
    return jsonify({"ok": True, "post_id": post.id, "status": post.status, "schedule_at": post.schedule_at.isoformat() if post.schedule_at else None})


@saas_api.route("/content/drafts/<int:draft_id>/save", methods=["POST"])
@require_auth
def content_draft_save(draft_id: int):
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    project_id_raw = data.get("project_id")

    db = SessionLocal()
    try:
        draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id).first()
        if not draft:
            return jsonify({"error": "draft not found"}), 404
        brief = db.query(ContentBrief).filter(ContentBrief.id == draft.brief_id).first()
        if not brief:
            return jsonify({"error": "brief not found"}), 404
        if user.role != "admin" and brief.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
    finally:
        db.close()

    try:
        project_id = int(project_id_raw) if project_id_raw else get_or_create_default_project(user.id).id
    except Exception:
        return jsonify({"error": "project_id должен быть числом"}), 400

    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_GENERATE, {"source": "/api/content/drafts/save"}))
    if pw:
        return pw

    post, err = _create_post_from_content_draft(
        user=user,
        draft=draft,
        brief=brief,
        project_id=project_id,
        schedule_at=None,
    )
    if err:
        return err
    recordUsageEvent(user, "POSTS_GENERATED", 1, {"endpoint": "/api/content/drafts/save", "post_id": post.id})
    return jsonify({"ok": True, "post_id": post.id, "status": post.status})


@saas_api.route("/content/drafts/<int:draft_id>/publish", methods=["POST"])
@require_auth
def content_draft_publish(draft_id: int):
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    project_id_raw = data.get("project_id")

    db = SessionLocal()
    try:
        draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id).first()
        if not draft:
            return jsonify({"error": "draft not found"}), 404
        brief = db.query(ContentBrief).filter(ContentBrief.id == draft.brief_id).first()
        if not brief:
            return jsonify({"error": "brief not found"}), 404
        if user.role != "admin" and brief.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
    finally:
        db.close()

    try:
        project_id = int(project_id_raw) if project_id_raw else get_or_create_default_project(user.id).id
    except Exception:
        return jsonify({"error": "project_id должен быть числом"}), 400

    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_GENERATE, {"source": "/api/content/drafts/publish"}))
    if pw:
        return pw
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_PUBLISH, {"source": "/api/content/drafts/publish"}))
    if pw:
        return pw

    post, err = _create_post_from_content_draft(
        user=user,
        draft=draft,
        brief=brief,
        project_id=project_id,
        schedule_at=None,
    )
    if err:
        return err
    recordUsageEvent(user, "POSTS_GENERATED", 1, {"endpoint": "/api/content/drafts/publish", "post_id": post.id})

    if draft.platform == "youtube":
        # Keep behavior explicit: youtube direct publish is not supported in /posts publish flow.
        return jsonify({"ok": True, "post_id": post.id, "status": post.status, "message": "YouTube draft сохранен. Для публикации используйте существующий YouTube/Campaign flow."}), 202

    db = SessionLocal()
    try:
        publish_user = db.query(AppUser).filter(AppUser.id == user.id).first()
        g.current_user = publish_user
        return publish_post(post.id)
    finally:
        db.close()


def _campaign_mode_allows(kind_mode: str, platform: str, kind: str) -> bool:
    mode = str(kind_mode or "image").strip().lower()
    platform = str(platform or "").strip().lower()
    kind = str(kind or "").strip().lower()
    if platform == "facebook":
        if kind not in {"image_post", "video"}:
            return False
        if mode == "image":
            return kind == "image_post"
        if mode == "video":
            return kind == "video"
        return kind in {"image_post", "video"}
    if platform == "instagram":
        if kind not in {"image_post", "reel"}:
            return False
        if mode == "image":
            return kind == "image_post"
        if mode == "video":
            return kind == "reel"
        return kind in {"image_post", "reel"}
    if platform == "youtube":
        if kind not in {"shorts", "video"}:
            return False
        return mode in {"video", "both"}
    return False


def _kick_due_deliveries_for_user(user_id: int) -> None:
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        due_rows = (
            db.query(CampaignDelivery)
            .join(Campaign, Campaign.id == CampaignDelivery.campaign_id)
            .filter(Campaign.user_id == user_id)
            .filter(CampaignDelivery.status == "queued")
            .filter((CampaignDelivery.scheduled_at.is_(None)) | (CampaignDelivery.scheduled_at <= now))
            .order_by(CampaignDelivery.created_at.asc())
            .limit(30)
            .all()
        )
        delivery_ids = [d.id for d in due_rows]
    finally:
        db.close()
    for delivery_id in delivery_ids:
        _start_delivery_worker(delivery_id)


def _refresh_campaign_status(db, campaign_id: int) -> str:
    rows = db.query(CampaignDelivery).filter(CampaignDelivery.campaign_id == campaign_id).all()
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        return "failed"
    if not rows:
        campaign.status = "draft"
    else:
        statuses = [str(r.status or "").lower() for r in rows]
        if any(s in {"uploading", "processing"} for s in statuses):
            campaign.status = "publishing"
        elif all(s == "published" for s in statuses):
            campaign.status = "published"
        elif any(s == "failed" for s in statuses):
            campaign.status = "failed"
        elif any(s == "queued" for s in statuses):
            campaign.status = "ready"
        else:
            campaign.status = "ready"
    campaign.updated_at = datetime.utcnow()
    db.commit()
    return campaign.status


def _start_generation_job(job_id: int, payload: dict) -> None:
    def _runner():
        db = SessionLocal()
        try:
            job = db.query(GenerationJob).filter_by(id=job_id).first()
            if not job:
                return
            campaign = db.query(Campaign).filter_by(id=job.campaign_id).first()
            if not campaign:
                job.status = "failed"
                job.error_message = "Campaign not found"
                job.updated_at = datetime.utcnow()
                db.commit()
                return

            job.status = "running"
            job.progress = 8
            job.updated_at = datetime.utcnow()
            db.commit()

            if job.job_type == "generate_image":
                topic = campaign.topic or "контент"
                style = str(payload.get("style") or "реалистично")
                no_text_on_image = bool(payload.get("no_text_on_image") is not False)
                prompt_guards = payload.get("prompt_guards") if isinstance(payload.get("prompt_guards"), dict) else {}
                tone = "friendly"
                if style in {"бизнес", "business"}:
                    tone = "expert"
                elif style in {"лайфстайл", "lifestyle"}:
                    tone = "friendly"
                elif style in {"минимализм", "minimal"}:
                    tone = "neutral"
                no_fantasy = bool(prompt_guards.get("no_fantasy", True))
                prompt_topic = f"{topic}. Стиль: {style}. Реалистично."
                if no_text_on_image:
                    prompt_topic += " Без текста, без надписей, без логотипов, без водяных знаков."
                if no_fantasy:
                    prompt_topic += " Без фантастики, без нереалистичных персонажей."
                image_url = generate_image_url(
                    topic=prompt_topic,
                    category="business",
                    tone=tone,
                    language=campaign.language or "ru",
                ) or build_semantic_fallback_image_url(
                    topic=prompt_topic,
                    category="business",
                    tone=tone,
                    language=campaign.language or "ru",
                )
                mirrored = _download_and_store_binary(image_url, ".jpg")
                final_url = mirrored[0] if mirrored else image_url
                size_bytes = mirrored[1] if mirrored else 0
                job.progress = 92
                job.updated_at = datetime.utcnow()
                db.commit()
                asset = CampaignAsset(
                    campaign_id=campaign.id,
                    type="image",
                    storage_url=final_url,
                    mime_type=_guess_mime(final_url, "image/jpeg"),
                    width=1024,
                    height=1024,
                    duration_sec=None,
                    size_bytes=size_bytes,
                    created_at=datetime.utcnow(),
                )
                db.add(asset)
                campaign.status = "ready"
                campaign.updated_at = datetime.utcnow()
                job.status = "done"
                job.progress = 100
                job.result_json = json.dumps({"asset_id": None, "type": "image"}, ensure_ascii=False)
                job.error_message = None
                job.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(asset)
                job.result_json = json.dumps({"asset": _asset_payload(asset)}, ensure_ascii=False)
                db.commit()
                return

            if job.job_type == "generate_video":
                topic = campaign.topic or "контент"
                duration_sec = int(payload.get("duration_sec") or 30)
                aspect_ratio = str(payload.get("aspect_ratio") or "9:16")
                gen_thumbnail = bool(payload.get("generate_thumbnail") is not False)
                minimize_repeats = bool(payload.get("minimize_repeats") is not False)
                realistic_only = bool(payload.get("realistic_only") is not False)
                scene_seconds = int(payload.get("scene_seconds") or 0) if str(payload.get("scene_seconds") or "").strip() else 0
                duration_sec = max(20, min(480, duration_sec))
                _set_video_job_progress(db, job, status="running", progress=0, step="queued", message="Задача поставлена в очередь")

                def _progress_cb(step: str, progress: int, message: str) -> None:
                    normalized_step = str(step or "").strip().lower()
                    if normalized_step == "footage":
                        legacy_status = "downloading"
                    elif normalized_step == "render":
                        legacy_status = "rendering"
                    elif normalized_step in {"export", "upload"}:
                        legacy_status = "uploading"
                    else:
                        legacy_status = "running"
                    _set_video_job_progress(
                        db,
                        job,
                        status=legacy_status,
                        progress=progress,
                        step=normalized_step or "structure",
                        message=message,
                    )

                produced = None
                last_video_error = "video_generation_failed"
                for _attempt in range(2):
                    try:
                        produced = generate_video_job_payload(
                            job_id=job.id,
                            campaign_id=campaign.id,
                            topic=topic,
                            offer=campaign.offer,
                            language=campaign.language or "ru",
                            target_seconds=duration_sec,
                            aspect_ratio=aspect_ratio,
                            style=str(payload.get("style") or "educational"),
                            style_pack_id=str(payload.get("style_pack_id") or DEFAULT_STYLE_PACK_ID),
                            use_lecture_txt=True,
                            reuse_manifest=bool(payload.get("reuse_manifest")),
                            reuse_from_job_id=(int(payload.get("reuse_from_job_id")) if str(payload.get("reuse_from_job_id", "")).isdigit() else None),
                            scene_seconds=scene_seconds if scene_seconds > 0 else None,
                            minimize_repeats=minimize_repeats,
                            realistic_only=realistic_only,
                            progress_callback=_progress_cb,
                        )
                        break
                    except Exception as exc:
                        last_video_error = str(exc)
                if not produced:
                    raise RuntimeError(last_video_error)
                _set_video_job_progress(db, job, status="rendering", progress=85, step="render", message="Рендер готов, сохраняем результат")
                video_url = str(produced.get("video_url") or "").strip()
                if not video_url:
                    raise RuntimeError("video_render_failed")
                local_video_path = str(produced.get("video_local_path") or "").strip()
                size_bytes = 0
                if local_video_path:
                    try:
                        size_bytes = int(Path(local_video_path).stat().st_size)
                    except Exception:
                        size_bytes = 0
                video_asset = CampaignAsset(
                    campaign_id=campaign.id,
                    type="video",
                    storage_url=video_url,
                    mime_type="video/mp4",
                    width=1080 if aspect_ratio == "9:16" else (1920 if aspect_ratio == "16:9" else 1080),
                    height=1920 if aspect_ratio == "9:16" else (1080 if aspect_ratio == "16:9" else 1080),
                    duration_sec=duration_sec,
                    size_bytes=size_bytes,
                    created_at=datetime.utcnow(),
                )
                db.add(video_asset)
                thumb_asset = None
                if gen_thumbnail:
                    thumb_url = build_semantic_fallback_image_url(
                        topic=f"Обложка для видео: {topic}",
                        category="business",
                        tone="expert",
                        language=campaign.language or "ru",
                    )
                    thumb_mirror = _download_and_store_binary(thumb_url, ".jpg")
                    thumb_final = thumb_mirror[0] if thumb_mirror else thumb_url
                    thumb_asset = CampaignAsset(
                        campaign_id=campaign.id,
                        type="thumbnail",
                        storage_url=thumb_final,
                        mime_type=_guess_mime(thumb_final, "image/jpeg"),
                        width=1280,
                        height=720,
                        duration_sec=None,
                        size_bytes=(thumb_mirror[1] if thumb_mirror else 0),
                        created_at=datetime.utcnow(),
                    )
                    db.add(thumb_asset)
                _set_video_job_progress(db, job, status="uploading", progress=95, step="upload", message="Сохраняем ассеты и метаданные")
                campaign.status = "ready"
                campaign.updated_at = datetime.utcnow()
                job.status = "done"
                job.progress = 100
                job.error_message = None
                job.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(video_asset)
                result_payload = {
                    "video": _asset_payload(video_asset),
                    "publish_meta": {
                        "title": produced.get("title"),
                        "description": produced.get("description"),
                        "hashtags": produced.get("hashtags") or [],
                    },
                    "artifacts": {
                        "audio_url": produced.get("audio_url"),
                        "subtitles_url": produced.get("subtitles_url"),
                        "manifest_url": produced.get("manifest_url"),
                    },
                }
                if thumb_asset:
                    db.refresh(thumb_asset)
                    result_payload["thumbnail"] = _asset_payload(thumb_asset)
                job.result_json = json.dumps(result_payload, ensure_ascii=False)
                db.commit()
                _set_video_job_progress(db, job, status="done", progress=100, step="upload", message="Видео готово к публикации")
                return

            raise RuntimeError("Unsupported job type")
        except Exception as exc:
            db.rollback()
            row = db.query(GenerationJob).filter_by(id=job_id).first()
            if row:
                row.status = "failed"
                row.error_message = str(exc)[:2000]
                row.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    thread = threading.Thread(target=_runner, daemon=True, name=f"generation-job-{job_id}")
    thread.start()


@saas_api.route("/campaigns", methods=["POST"])
@require_auth
def create_campaign():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode") or "image").strip().lower()
    if mode not in {"image", "video", "both"}:
        return jsonify({"error": "mode должен быть image, video или both"}), 400

    project_id = data.get("project_id")
    if project_id is not None:
        try:
            project_id = int(project_id)
        except Exception:
            return jsonify({"error": "project_id должен быть числом"}), 400
        if not can_access_project(user, project_id):
            return jsonify({"error": "Нет доступа к проекту"}), 403
    else:
        project_id = get_or_create_default_project(user.id).id

    topic = (data.get("topic") or "").strip() or "Новая кампания"
    campaign = Campaign(
        user_id=user.id,
        project_id=project_id,
        mode=mode,
        topic=topic,
        offer=(data.get("offer") or "").strip() or None,
        objective=(data.get("objective") or "").strip() or None,
        caption_master=(data.get("caption_master") or "").strip() or None,
        cta=(data.get("cta") or "").strip() or None,
        hashtags_master=json.dumps(data.get("hashtags_master") or [], ensure_ascii=False),
        language=str(data.get("language") or "ru").strip().lower() or "ru",
        status=str(data.get("status") or "draft").strip().lower() or "draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db = SessionLocal()
    try:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return jsonify({"campaign": _campaign_payload(campaign)}), 201
    finally:
        db.close()


@saas_api.route("/campaigns/<int:campaign_id>", methods=["PATCH"])
@require_auth
def update_campaign(campaign_id: int):
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            return jsonify({"error": "Кампания не найдена"}), 404
        if user.role != "admin" and campaign.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403

        if "project_id" in data:
            raw_project = data.get("project_id")
            if raw_project in (None, "", "null"):
                campaign.project_id = None
            else:
                try:
                    pid = int(raw_project)
                except Exception:
                    return jsonify({"error": "project_id должен быть числом"}), 400
                if not can_access_project(user, pid):
                    return jsonify({"error": "Нет доступа к проекту"}), 403
                campaign.project_id = pid
        if "mode" in data:
            mode = str(data.get("mode") or "").strip().lower()
            if mode not in {"image", "video", "both"}:
                return jsonify({"error": "mode должен быть image, video или both"}), 400
            campaign.mode = mode
        if "topic" in data:
            topic = (data.get("topic") or "").strip()
            if not topic:
                return jsonify({"error": "topic обязателен"}), 400
            campaign.topic = topic
        if "offer" in data:
            campaign.offer = (data.get("offer") or "").strip() or None
        if "objective" in data:
            campaign.objective = (data.get("objective") or "").strip() or None
        if "caption_master" in data:
            campaign.caption_master = (data.get("caption_master") or "").strip() or None
        if "cta" in data:
            campaign.cta = (data.get("cta") or "").strip() or None
        if "hashtags_master" in data:
            tags = data.get("hashtags_master")
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split() if t.strip()]
            if not isinstance(tags, list):
                return jsonify({"error": "hashtags_master должен быть массивом или строкой"}), 400
            campaign.hashtags_master = json.dumps(tags[:30], ensure_ascii=False)
        if "language" in data:
            campaign.language = str(data.get("language") or "ru").strip().lower() or "ru"
        if "status" in data:
            status = str(data.get("status") or "").strip().lower()
            if status not in {"draft", "ready", "publishing", "published", "failed"}:
                return jsonify({"error": "Недопустимый status"}), 400
            campaign.status = status
        campaign.updated_at = datetime.utcnow()
        db.commit()
        return jsonify({"campaign": _campaign_payload(campaign)})
    finally:
        db.close()


@saas_api.route("/campaigns/<int:campaign_id>", methods=["GET"])
@require_auth
def campaign_details(campaign_id: int):
    user = g.current_user
    _kick_due_deliveries_for_user(user.id)
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            return jsonify({"error": "Кампания не найдена"}), 404
        if user.role != "admin" and campaign.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
        assets = (
            db.query(CampaignAsset)
            .filter_by(campaign_id=campaign.id)
            .order_by(CampaignAsset.created_at.asc(), CampaignAsset.id.asc())
            .all()
        )
        deliveries = (
            db.query(CampaignDelivery)
            .filter_by(campaign_id=campaign.id)
            .order_by(CampaignDelivery.created_at.asc(), CampaignDelivery.id.asc())
            .all()
        )
        jobs = (
            db.query(GenerationJob)
            .filter_by(campaign_id=campaign.id)
            .order_by(GenerationJob.created_at.desc(), GenerationJob.id.desc())
            .limit(20)
            .all()
        )
        return jsonify(
            {
                "campaign": _campaign_payload(campaign),
                "assets": [_asset_payload(a) for a in assets],
                "deliveries": [_delivery_payload(d) for d in deliveries],
                "jobs": [_job_payload(j) for j in jobs],
            }
        )
    finally:
        db.close()


@saas_api.route("/campaigns", methods=["GET"])
@require_auth
def list_campaigns():
    user = g.current_user
    limit = min(100, max(1, int(request.args.get("limit", 30))))
    db = SessionLocal()
    try:
        query = db.query(Campaign)
        if user.role != "admin":
            query = query.filter(Campaign.user_id == user.id)
        rows = query.order_by(Campaign.created_at.desc(), Campaign.id.desc()).limit(limit).all()
        return jsonify({"items": [_campaign_payload(c) for c in rows]})
    finally:
        db.close()


@saas_api.route("/campaigns/<int:campaign_id>/generate-image", methods=["POST"])
@require_auth
def campaign_generate_image(campaign_id: int):
    user = g.current_user
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            return jsonify({"error": "Кампания не найдена"}), 404
        if user.role != "admin" and campaign.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
        if campaign.mode == "video":
            return jsonify({"error": "Для режима video генерация изображения недоступна"}), 400
        if not (campaign.topic or "").strip():
            return jsonify({"error": "Укажите тему кампании перед генерацией"}), 400

        payload = {
            "style": str(data.get("style") or "реалистично"),
            "no_text_on_image": bool(data.get("no_text_on_image") is not False),
            "realism": bool(data.get("realism") is not False),
            "prompt_guards": data.get("prompt_guards") or {"no_fantasy": True},
        }
        job = GenerationJob(
            campaign_id=campaign.id,
            job_type="generate_image",
            status="queued",
            progress=0,
            result_json=json.dumps({}, ensure_ascii=False),
            error_message=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(job)
        campaign.status = "draft"
        campaign.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        _start_generation_job(job.id, payload)
        return jsonify({"job": _job_payload(job)}), 202
    finally:
        db.close()


@saas_api.route("/campaigns/<int:campaign_id>/generate-video", methods=["POST"])
@require_auth
def campaign_generate_video(campaign_id: int):
    user = g.current_user
    data = request.get_json(silent=True) or {}
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_VIDEO_GENERATE, {"endpoint": "/api/campaigns/generate-video"}))
    if pw:
        return pw
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            return jsonify({"error": "Кампания не найдена"}), 404
        if user.role != "admin" and campaign.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
        if campaign.mode == "image":
            return jsonify({"error": "Для режима image генерация видео недоступна"}), 400
        if not (campaign.topic or "").strip():
            return jsonify({"error": "Укажите тему кампании перед генерацией"}), 400

        duration_sec = int(data.get("duration_sec") or 30)
        if duration_sec < 20 or duration_sec > 480:
            return jsonify({"error": "duration_sec должен быть в диапазоне 20..480"}), 400
        aspect_ratio = str(data.get("aspect_ratio") or "9:16").strip()
        if aspect_ratio not in {"9:16", "1:1", "16:9"}:
            return jsonify({"error": "aspect_ratio должен быть 9:16, 1:1 или 16:9"}), 400
        requested_style_pack = str(data.get("style_pack_id") or "").strip().lower()
        if not requested_style_pack:
            requested_style_pack = _get_user_style_pref(db, user.id)
        normalized_style_pack = get_style_pack(requested_style_pack).get("id") or DEFAULT_STYLE_PACK_ID
        _set_user_style_pref(db, user.id, normalized_style_pack)
        payload = {
            "duration_sec": duration_sec,
            "aspect_ratio": aspect_ratio,
            "realism": bool(data.get("realism") is not False),
            "prompt_guards": data.get("prompt_guards") or {"no_fantasy": True},
            "generate_thumbnail": bool(data.get("generate_thumbnail") is not False),
            "style": str(data.get("style") or "educational"),
            "style_pack_id": normalized_style_pack,
            "reuse_manifest": bool(data.get("reuse_manifest") is True),
            "reuse_from_job_id": int(data.get("reuse_from_job_id")) if str(data.get("reuse_from_job_id", "")).isdigit() else None,
        }
        job = GenerationJob(
            campaign_id=campaign.id,
            job_type="generate_video",
            status="queued",
            progress=0,
            result_json=json.dumps({}, ensure_ascii=False),
            error_message=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(job)
        campaign.status = "draft"
        campaign.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        _start_generation_job(job.id, payload)
        recordUsageEvent(user, "VIDEOS_GENERATED", 1, {"endpoint": "/api/campaigns/generate-video", "campaign_id": campaign.id, "job_id": job.id})
        return jsonify({"job": _job_payload(job)}), 202
    finally:
        db.close()


@saas_api.route("/jobs/<int:job_id>", methods=["GET"])
@require_auth
def get_job_status(job_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter_by(id=job_id).first()
        if not job:
            return jsonify({"error": "Job не найден"}), 404
        campaign = db.query(Campaign).filter_by(id=job.campaign_id).first()
        if not campaign:
            return jsonify({"error": "Campaign не найден"}), 404
        if user.role != "admin" and campaign.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
        return jsonify({"job": _job_payload(job)})
    finally:
        db.close()


@saas_api.route("/video/generate", methods=["POST"])
@saas_api.route("/ai/video/render", methods=["POST"])
@require_auth
def video_generate():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    topic = str(data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "topic обязателен"}), 400
    offer = str(data.get("offer") or "").strip() or None
    language = str(data.get("language") or "ru").strip().lower() or "ru"
    style = str(data.get("style") or "educational").strip() or "educational"
    fmt = str(data.get("format") or "short").strip().lower()
    if fmt not in {"short", "long"}:
        fmt = "short"
    min_sec = 20 if fmt == "short" else 120
    max_sec = 70 if fmt == "short" else 480
    target_seconds = int(data.get("target_seconds") or min_sec)
    target_seconds = max(min_sec, min(max_sec, target_seconds))
    orientation = str(data.get("orientation") or ("vertical" if fmt == "short" else "horizontal")).strip().lower()
    if orientation not in {"vertical", "horizontal"}:
        orientation = "vertical" if fmt == "short" else "horizontal"
    aspect_ratio = "9:16" if orientation == "vertical" else "16:9"
    scene_seconds = int(data.get("scene_seconds") or 0) if str(data.get("scene_seconds") or "").strip() else 0
    minimize_repeats = bool(data.get("minimize_repeats") is not False)
    realistic_only = bool(data.get("realistic_only") is not False)

    project_id_raw = data.get("project_id")
    try:
        project_id = int(project_id_raw) if project_id_raw else get_or_create_default_project(user.id).id
    except Exception:
        return jsonify({"error": "project_id должен быть числом"}), 400
    if not can_access_project(user, project_id):
        return jsonify({"error": "Нет доступа к проекту"}), 403

    endpoint_ref = "/api/ai/video/render" if request.path.endswith("/ai/video/render") else "/api/video/generate"
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_VIDEO_GENERATE, {"endpoint": endpoint_ref}))
    if pw:
        return pw

    db = SessionLocal()
    try:
        requested_style_pack = str(data.get("style_pack_id") or "").strip().lower()
        if not requested_style_pack:
            requested_style_pack = _get_user_style_pref(db, user.id)
        normalized_style_pack = get_style_pack(requested_style_pack).get("id") or DEFAULT_STYLE_PACK_ID
        _set_user_style_pref(db, user.id, normalized_style_pack)
        campaign = Campaign(
            user_id=user.id,
            project_id=project_id,
            mode="video",
            topic=topic,
            offer=offer,
            objective="engagement",
            caption_master=None,
            cta=None,
            hashtags_master=json.dumps([], ensure_ascii=False),
            language=language,
            status="draft",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        job = GenerationJob(
            campaign_id=campaign.id,
            job_type="generate_video",
            status="queued",
            progress=0,
            result_json=json.dumps(
                {
                    "request": {
                        "format": fmt,
                        "target_seconds": target_seconds,
                        "orientation": orientation,
                        "style": style,
                        "style_pack_id": normalized_style_pack,
                        "language": language,
                        "scene_seconds": scene_seconds if scene_seconds > 0 else None,
                        "minimize_repeats": minimize_repeats,
                        "realistic_only": realistic_only,
                    }
                },
                ensure_ascii=False,
            ),
            error_message=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        _start_generation_job(
            job.id,
            {
                "duration_sec": target_seconds,
                "aspect_ratio": aspect_ratio,
                "realism": realistic_only,
                "prompt_guards": {"no_fantasy": realistic_only},
                "generate_thumbnail": True,
                "style": style,
                "style_pack_id": normalized_style_pack,
                "scene_seconds": scene_seconds if scene_seconds > 0 else None,
                "minimize_repeats": minimize_repeats,
                "realistic_only": realistic_only,
                "reuse_manifest": bool(data.get("reuse_manifest") is True),
                "reuse_from_job_id": int(data.get("reuse_from_job_id")) if str(data.get("reuse_from_job_id", "")).isdigit() else None,
            },
        )
        recordUsageEvent(user, "VIDEOS_GENERATED", 1, {"endpoint": endpoint_ref, "campaign_id": campaign.id, "job_id": job.id})
        return jsonify({"job_id": job.id, "campaign_id": campaign.id, "status": job.status}), 202
    finally:
        db.close()


@saas_api.route("/video/structure", methods=["POST"])
@require_auth
def video_structure():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    topic = str(data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "topic обязателен"}), 400
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_VIDEO_GENERATE, {"endpoint": "/api/video/structure"}))
    if pw:
        return pw
    offer = str(data.get("offer") or "").strip() or None
    language = str(data.get("language") or "ru").strip().lower() or "ru"
    style = str(data.get("style") or "educational").strip() or "educational"
    orientation = str(data.get("orientation") or "vertical").strip().lower()
    if orientation not in {"vertical", "horizontal"}:
        orientation = "vertical"
    target_seconds = int(data.get("target_seconds") or 30)
    target_seconds = max(20, min(480, target_seconds))
    scene_seconds = int(data.get("scene_seconds") or 0) if str(data.get("scene_seconds") or "").strip() else 0
    scene_seconds = max(0, min(12, scene_seconds))
    scene_every_4 = bool(data.get("scene_every_4s") is True)
    try:
        script = generate_video_structure(
            topic=topic,
            offer=offer,
            language=language,
            target_seconds=target_seconds,
            style=style,
            style_pack=get_style_pack(data.get("style_pack_id")),
        )
    except Exception as exc:
        return jsonify({"error": f"Не удалось построить структуру видео: {str(exc)}"}), 500

    phrases = list(script.phrases or [])
    per_scene = float(scene_seconds if scene_seconds > 0 else (4 if scene_every_4 else (target_seconds / max(1, len(phrases)))))
    per_scene = max(2.0, min(20.0, per_scene))
    scenes = []
    for idx, phrase in enumerate(phrases):
        shot = (script.shotlist[idx] if idx < len(script.shotlist) else {}) or {}
        scenes.append(
            {
                "index": idx,
                "text": phrase,
                "duration_s": round(per_scene, 2),
                "scene_type": str(shot.get("scene_type") or "work"),
                "queries": list(shot.get("queries") or []),
            }
        )
    return jsonify(
        {
            "status": "ok",
            "data": {
                "topic": topic,
                "title": script.title,
                "description": script.description,
                "hashtags": list(script.hashtags or []),
                "target_seconds": target_seconds,
                "orientation": orientation,
                "scenes": scenes,
                "subtitles": {"enabled": True, "lines": phrases},
                "voiceover": {"voice": "Eddy", "gender": "male"},
                "background_music": {"enabled": bool(settings.VIDEO_BG_MUSIC_ENABLED), "ducking": "low"},
            },
            "warnings": [],
            "debug_code": "",
        }
    )


@saas_api.route("/video/style-packs", methods=["GET"])
@require_auth
def video_style_packs():
    user = g.current_user
    db = SessionLocal()
    try:
        packs = list_style_packs()
        default_style_pack = _get_user_style_pref(db, user.id)
        requested_default = request.args.get("default_style_pack")
        if requested_default:
            default_style_pack = _set_user_style_pref(db, user.id, requested_default)
        return jsonify(
            {
                "items": packs,
                "default_style_pack": default_style_pack,
            }
        )
    finally:
        db.close()


@saas_api.route("/video/jobs/<int:job_id>", methods=["GET"])
@require_auth
def video_job_status(job_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter_by(id=job_id, job_type="generate_video").first()
        if not job:
            return jsonify({"error": "Job не найден"}), 404
        campaign = db.query(Campaign).filter_by(id=job.campaign_id).first()
        if not campaign:
            return jsonify({"error": "Campaign не найден"}), 404
        if user.role != "admin" and campaign.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
        assets = db.query(CampaignAsset).filter_by(campaign_id=campaign.id).order_by(CampaignAsset.created_at.desc()).all()
        return jsonify(
            {
                "job_id": job.id,
                "status": job.status,
                "progress": int(job.progress or 0),
                "error_message": job.error_message,
                "result": _json_loads_safe(job.result_json, {}),
                "campaign_id": campaign.id,
                "assets": [_asset_payload(a) for a in assets],
            }
        )
    finally:
        db.close()


@saas_api.route("/ai/video/jobs/<int:job_id>", methods=["GET"])
@require_auth
def ai_video_job_status(job_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter_by(id=job_id, job_type="generate_video").first()
        if not job:
            return jsonify({"error": "Job не найден"}), 404
        campaign = db.query(Campaign).filter_by(id=job.campaign_id).first()
        if not campaign:
            return jsonify({"error": "Campaign не найден"}), 404
        if user.role != "admin" and campaign.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403

        result = _job_result_dict(job)
        progress_meta = result.get("progress") if isinstance(result.get("progress"), dict) else {}
        step = str(progress_meta.get("step") or "").strip().lower()
        message = str(progress_meta.get("message") or "").strip()
        if not step:
            status_map = {
                "queued": "structure",
                "running": "structure",
                "downloading": "footage",
                "rendering": "render",
                "uploading": "upload",
                "done": "upload",
                "failed": "render",
            }
            step = status_map.get(str(job.status or "").lower(), "structure")
        if not message:
            message_map = {
                "queued": "Задача в очереди",
                "running": "Подготавливаем видео",
                "downloading": "Подбираем футажи",
                "rendering": "Рендерим видео",
                "uploading": "Сохраняем результат",
                "done": "Видео готово",
                "failed": "Ошибка сборки видео",
            }
            message = message_map.get(str(job.status or "").lower(), "Обработка")

        raw_status = str(job.status or "").lower()
        if raw_status in {"done"}:
            out_status = "success"
        elif raw_status in {"failed"}:
            out_status = "error"
        elif raw_status in {"queued"}:
            out_status = "queued"
        else:
            out_status = "running"

        video_url = ""
        preview_url = ""
        if isinstance(result.get("video"), dict):
            video_url = str(result["video"].get("storage_url") or "").strip()
        if isinstance(result.get("thumbnail"), dict):
            preview_url = str(result["thumbnail"].get("storage_url") or "").strip()
        assets = db.query(CampaignAsset).filter_by(campaign_id=campaign.id).order_by(CampaignAsset.created_at.desc()).all()
        if not video_url:
            v_asset = next((a for a in assets if str(a.type or "").lower() == "video"), None)
            if v_asset:
                video_url = str(v_asset.storage_url or "").strip()
        if not preview_url:
            t_asset = next((a for a in assets if str(a.type or "").lower() == "thumbnail"), None)
            if t_asset:
                preview_url = str(t_asset.storage_url or "").strip()

        return jsonify(
            {
                "status": out_status,
                "progress": max(0, min(100, int(job.progress or 0))),
                "step": step,
                "message": message,
                "previewUrl": preview_url or video_url or None,
                "finalUrl": video_url or None,
                "error": (str(job.error_message or "").strip() or None),
            }
        )
    finally:
        db.close()


@saas_api.route("/video/jobs/<int:job_id>/publish", methods=["POST"])
@require_auth
def video_job_publish(job_id: int):
    user = g.current_user
    data = request.get_json(silent=True) or {}
    requested_platforms = data.get("platforms")
    if not isinstance(requested_platforms, list) or not requested_platforms:
        requested_platforms = ["youtube"]
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_VIDEO_PUBLISH, {"endpoint": "/api/video/jobs/publish"}))
    if pw:
        return pw

    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter_by(id=job_id, job_type="generate_video").first()
        if not job:
            return jsonify({"error": "Job не найден"}), 404
        campaign = db.query(Campaign).filter_by(id=job.campaign_id).first()
        if not campaign:
            return jsonify({"error": "Campaign не найден"}), 404
        if user.role != "admin" and campaign.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
        if str(job.status) != "done":
            return jsonify({"error": "Видео еще не готово"}), 400
        has_video = db.query(CampaignAsset).filter_by(campaign_id=campaign.id, type="video").count() > 0
        if not has_video:
            return jsonify({"error": "Видео-ассет не найден"}), 400

        created_rows = []
        for p in requested_platforms:
            platform = str(p or "").strip().lower()
            if platform not in {"youtube", "facebook", "instagram"}:
                continue
            kind = "shorts" if platform == "youtube" else ("reel" if platform == "instagram" else "video")
            row = CampaignDelivery(
                campaign_id=campaign.id,
                platform=platform,
                kind=kind,
                account_ref=None,
                caption_rendered=campaign.caption_master or campaign.topic,
                hashtags_rendered=campaign.hashtags_master or "[]",
                scheduled_at=None,
                status="queued",
                remote_id=None,
                error_message=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(row)
            created_rows.append(row)
        if not created_rows:
            return jsonify({"error": "Нет валидных platforms"}), 400
        campaign.status = "publishing"
        campaign.updated_at = datetime.utcnow()
        db.commit()
        recordUsageEvent(
            user,
            "VIDEOS_PUBLISHED",
            len(created_rows),
            {"endpoint": "/api/video/jobs/publish", "campaign_id": campaign.id, "job_id": job.id},
        )
        for row in created_rows:
            db.refresh(row)
            _start_delivery_worker(row.id)
        return jsonify({"campaign_id": campaign.id, "deliveries": [_delivery_payload(x) for x in created_rows]}), 202
    finally:
        db.close()


@saas_api.route("/campaigns/<int:campaign_id>/publish", methods=["POST"])
@require_auth
def campaign_publish(campaign_id: int):
    user = g.current_user
    data = request.get_json(silent=True) or {}
    requested = data.get("deliveries") if isinstance(data.get("deliveries"), list) else []
    if not requested:
        return jsonify({"error": "Передайте deliveries"}), 400

    has_video_delivery = any(str((x or {}).get("kind") or "").strip().lower() in {"video", "reel", "shorts"} for x in requested if isinstance(x, dict))
    has_image_delivery = any(str((x or {}).get("kind") or "").strip().lower() == "image_post" for x in requested if isinstance(x, dict))
    has_schedule_delivery = any(bool((x or {}).get("scheduled_at")) for x in requested if isinstance(x, dict))
    if has_schedule_delivery:
        pw = _paywall_response_if_needed(authorizeAction(user, ACTION_SCHEDULE_CREATE, {"endpoint": "/api/campaigns/publish"}))
        if pw:
            return pw
    if has_video_delivery:
        pw = _paywall_response_if_needed(authorizeAction(user, ACTION_VIDEO_PUBLISH, {"endpoint": "/api/campaigns/publish"}))
        if pw:
            return pw
    if has_image_delivery:
        pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_PUBLISH, {"endpoint": "/api/campaigns/publish"}))
        if pw:
            return pw

    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            return jsonify({"error": "Кампания не найдена"}), 404
        if user.role != "admin" and campaign.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403

        assets = db.query(CampaignAsset).filter_by(campaign_id=campaign.id).all()
        has_image = any(a.type == "image" for a in assets)
        has_video = any(a.type == "video" for a in assets)

        created_rows = []
        for item in requested:
            if not isinstance(item, dict):
                return jsonify({"error": "Элементы deliveries должны быть объектами"}), 400
            platform = str(item.get("platform") or "").strip().lower()
            kind = str(item.get("kind") or "").strip().lower()
            if platform not in {"facebook", "instagram", "youtube"}:
                return jsonify({"error": f"Неподдерживаемая платформа: {platform}"}), 400
            if not _campaign_mode_allows(campaign.mode, platform, kind):
                return jsonify({"error": f"Режим {campaign.mode} не поддерживает {platform}/{kind}"}), 400
            if kind == "image_post" and not has_image:
                return jsonify({"error": "Сначала сгенерируйте изображение"}), 400
            if kind in {"video", "reel", "shorts"} and not has_video:
                return jsonify({"error": "Сначала сгенерируйте видео"}), 400
            account_ref = (item.get("account_ref") or "").strip() or None
            if platform == "youtube" and not account_ref:
                conn = (
                    db.query(SocialAccount)
                    .filter(SocialAccount.user_id == campaign.user_id, SocialAccount.provider == "youtube")
                    .order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc())
                    .first()
                )
                if conn and conn.channel_id:
                    account_ref = conn.channel_id
            scheduled_at = None
            if item.get("scheduled_at"):
                try:
                    scheduled_at = _parse_iso_datetime(str(item.get("scheduled_at")))
                except Exception:
                    return jsonify({"error": "scheduled_at должен быть в ISO формате"}), 400

            tags = item.get("hashtags_override")
            if tags is None:
                tags = _json_loads_safe(campaign.hashtags_master, [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split() if t.strip()]
            if not isinstance(tags, list):
                tags = []
            caption = (item.get("caption_override") or campaign.caption_master or campaign.topic or "").strip()
            row = CampaignDelivery(
                campaign_id=campaign.id,
                platform=platform,
                kind=kind,
                account_ref=account_ref,
                caption_rendered=caption,
                hashtags_rendered=json.dumps(tags[:30], ensure_ascii=False),
                scheduled_at=scheduled_at,
                status="queued",
                remote_id=None,
                error_message=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(row)
            created_rows.append(row)
        campaign.status = "publishing"
        campaign.updated_at = datetime.utcnow()
        db.commit()
        if created_rows:
            video_count = sum(1 for x in created_rows if str(x.kind or "").lower() in {"video", "reel", "shorts"})
            image_count = sum(1 for x in created_rows if str(x.kind or "").lower() == "image_post")
            if video_count:
                recordUsageEvent(user, "VIDEOS_PUBLISHED", video_count, {"endpoint": "/api/campaigns/publish", "campaign_id": campaign.id})
            if image_count:
                recordUsageEvent(user, "POSTS_PUBLISHED", image_count, {"endpoint": "/api/campaigns/publish", "campaign_id": campaign.id})
        for row in created_rows:
            db.refresh(row)
            if row.scheduled_at is None or row.scheduled_at <= datetime.utcnow():
                _start_delivery_worker(row.id)
        return jsonify({"deliveries": [_delivery_payload(r) for r in created_rows], "campaign": _campaign_payload(campaign)}), 202
    finally:
        db.close()


@saas_api.route("/deliveries/<int:delivery_id>", methods=["GET"])
@require_auth
def delivery_details(delivery_id: int):
    user = g.current_user
    _kick_due_deliveries_for_user(user.id)
    db = SessionLocal()
    try:
        row = db.query(CampaignDelivery).filter_by(id=delivery_id).first()
        if not row:
            return jsonify({"error": "Delivery не найден"}), 404
        campaign = db.query(Campaign).filter_by(id=row.campaign_id).first()
        if not campaign:
            return jsonify({"error": "Campaign не найден"}), 404
        if user.role != "admin" and campaign.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
        _refresh_campaign_status(db, campaign.id)
        return jsonify({"delivery": _delivery_payload(row)})
    finally:
        db.close()


@saas_api.route("/history", methods=["GET"])
@require_auth
def campaigns_history():
    user = g.current_user
    _kick_due_deliveries_for_user(user.id)
    limit = min(200, max(1, int(request.args.get("limit", 80))))
    db = SessionLocal()
    try:
        query = db.query(Campaign)
        if user.role != "admin":
            query = query.filter(Campaign.user_id == user.id)
        campaigns = query.order_by(Campaign.created_at.desc()).limit(limit).all()
        campaign_ids = [c.id for c in campaigns]
        deliveries = []
        if campaign_ids:
            deliveries = (
                db.query(CampaignDelivery)
                .filter(CampaignDelivery.campaign_id.in_(campaign_ids))
                .order_by(CampaignDelivery.created_at.desc())
                .all()
            )
        by_campaign = {}
        for d in deliveries:
            by_campaign.setdefault(d.campaign_id, []).append(_delivery_payload(d))
        payload = []
        for c in campaigns:
            payload.append({"campaign": _campaign_payload(c), "deliveries": by_campaign.get(c.id, [])})
        return jsonify({"items": payload})
    finally:
        db.close()


@saas_api.route("/youtube/generate-video", methods=["POST"])
@require_auth
def youtube_generate_video():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_VIDEO_GENERATE, {"endpoint": "/api/youtube/generate-video"}))
    if pw:
        return pw

    topic = (data.get("topic") or "").strip()
    language = (data.get("language") or "ru").strip().lower()
    tone = (data.get("tone") or "expert").strip().lower()
    audience = (data.get("audience") or "small business owners").strip()
    goal = (data.get("goal") or "engagement").strip()
    style = (data.get("style") or "educational").strip()
    video_type = (data.get("video_type") or "short").strip().lower()
    if video_type not in {"short", "long"}:
        video_type = "short"

    if not topic:
        return jsonify({"error": "Укажите тему видео"}), 400

    min_len, max_len = _youtube_length_bounds(video_type)
    try:
        duration_seconds = int(data.get("duration_seconds") or min_len)
    except Exception:
        return jsonify({"error": "duration_seconds должен быть числом"}), 400
    duration_seconds = max(min_len, min(max_len, duration_seconds))
    eta_seconds = _youtube_eta_seconds(video_type, duration_seconds)

    system_prompt = (
        "Ты YouTube-стратег и сценарист. "
        "Верни только JSON без markdown и пояснений. "
        "Сделай результат конкретным, без воды, применимым сразу."
    )
    user_prompt = (
        f"Сформируй пакет для YouTube видео.\n"
        f"Тема: {topic}\n"
        f"Тип: {video_type}\n"
        f"Длительность: {duration_seconds} секунд\n"
        f"Язык: {language}\n"
        f"Тон: {tone}\n"
        f"ЦА: {audience}\n"
        f"Цель: {goal}\n"
        f"Стиль: {style}\n"
        "JSON-структура:\n"
        "{\n"
        '  "title_options": ["...","...","..."],\n'
        '  "thumbnail_text": "...",\n'
        '  "description": "...",\n'
        '  "hashtags": ["#...","#...","#..."],\n'
        '  "hook": "...",\n'
        '  "timeline": [{"t":"00:00","segment":"...","voiceover":"...","visual":"..."}],\n'
        '  "cta": "...",\n'
        '  "community_post": "...",\n'
        '  "production_notes": ["...","..."]\n'
        "}"
    )

    try:
        gen = generate_structured_text_with_usage(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=900 if video_type == "long" else 650,
            temperature=0.7,
        )
        raw = (gen.text or "").strip()
        payload = None
        try:
            payload = json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                payload = json.loads(m.group(0))
        if not isinstance(payload, dict):
            raise ValueError("model_return_invalid_json")
    except Exception:
        payload = {
            "title_options": [
                f"{topic}: пошаговый разбор без воды",
                f"Как быстро получить результат в теме: {topic}",
                f"{topic}: стратегия на {duration_seconds} секунд",
            ],
            "thumbnail_text": "ПЛАН ДЕЙСТВИЙ",
            "description": f"Практический ролик по теме '{topic}' с понятными шагами и примерами.",
            "hashtags": ["#youtube", "#контент", "#маркетинг"],
            "hook": "За следующие минуты вы получите готовый план действий.",
            "timeline": [
                {"t": "00:00", "segment": "Хук", "voiceover": "Коротко обозначьте боль и обещание результата.", "visual": "Крупный план + заголовок"},
                {"t": "00:10", "segment": "Суть проблемы", "voiceover": "Покажите, где обычно теряют время/деньги.", "visual": "Инфографика"},
                {"t": "00:30", "segment": "Решение", "voiceover": "Дайте 3 конкретных шага.", "visual": "Список шагов"},
            ],
            "cta": "Подпишитесь и напишите в комментариях 'шаблон' - отправим структуру.",
            "community_post": f"Новый ролик по теме '{topic}' уже на канале. Напишите свой кейс в комментариях.",
            "production_notes": [
                "Говорите короткими фразами: 8-14 слов.",
                "Смена плана каждые 2-4 секунды для shorts и 5-8 секунд для long.",
            ],
        }
        gen = type("Gen", (), {"input_tokens": 0, "output_tokens": 0})()

    titles = payload.get("title_options") if isinstance(payload.get("title_options"), list) else []
    timeline = payload.get("timeline") if isinstance(payload.get("timeline"), list) else []
    hashtags = payload.get("hashtags") if isinstance(payload.get("hashtags"), list) else []
    result = {
        "topic": topic,
        "video_type": video_type,
        "duration_seconds": duration_seconds,
        "duration_bounds_seconds": {"min": min_len, "max": max_len},
        "estimated_wait_seconds": eta_seconds,
        "server_capacity_note": f"Рекомендуемый лимит на сервере: до {max_len} секунд для типа {video_type}.",
        "title_options": [str(x).strip() for x in titles[:5] if str(x).strip()],
        "thumbnail_text": str(payload.get("thumbnail_text") or "").strip(),
        "description": str(payload.get("description") or "").strip(),
        "hashtags": [str(x).strip() for x in hashtags[:8] if str(x).strip()],
        "hook": str(payload.get("hook") or "").strip(),
        "timeline": timeline[:24],
        "cta": str(payload.get("cta") or "").strip(),
        "community_post": str(payload.get("community_post") or "").strip(),
        "production_notes": payload.get("production_notes") if isinstance(payload.get("production_notes"), list) else [],
        "tokens_input": int(getattr(gen, "input_tokens", 0) or 0),
        "tokens_output": int(getattr(gen, "output_tokens", 0) or 0),
    }
    recordUsageEvent(user, "VIDEOS_GENERATED", 1, {"endpoint": "/api/youtube/generate-video", "topic": topic, "video_type": video_type})
    return jsonify(result)


@saas_api.route("/youtube/generate-post", methods=["POST"])
@require_auth
def youtube_generate_post():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_GENERATE, {"endpoint": "/api/youtube/generate-post"}))
    if pw:
        return pw
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "Укажите тему поста"}), 400

    post_kind = (data.get("post_kind") or "community").strip().lower()
    if post_kind not in {"community", "announcement", "poll"}:
        post_kind = "community"

    language = (data.get("language") or "ru").strip().lower()
    tone = (data.get("tone") or "friendly").strip().lower()
    project_id_raw = data.get("project_id")
    try:
        project_id = int(project_id_raw) if project_id_raw else get_or_create_default_project(user.id).id
    except Exception:
        return jsonify({"error": "project_id должен быть числом"}), 400
    if not can_access_project(user, project_id):
        return jsonify({"error": "У вас нет доступа к проекту"}), 403

    prompt_text = f"YouTube {post_kind} post"
    try:
        post = create_post_and_charge(
            user_id=user.id,
            project_id=project_id,
            platform="youtube",
            topic=f"[{post_kind}] {topic}",
            category="youtube",
            tone=tone,
            language=language,
            prompt_text=prompt_text,
            media_url=None,
            schedule_at=None,
            variant_count=1,
            translation=False,
            long_post_mode=False,
            generated_text_override=(data.get("generated_text") or "").strip() or None,
            save_as_draft=True,
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 429
    except Exception as exc:
        return jsonify({"error": f"Ошибка генерации YouTube поста: {exc}"}), 500

    recordUsageEvent(user, "POSTS_GENERATED", 1, {"endpoint": "/api/youtube/generate-post", "post_id": post.id})

    return jsonify(
        {
            "id": post.id,
            "platform": post.platform,
            "status": post.status,
            "topic": post.topic,
            "generated_text": post.generated_text,
            "created_at": post.created_at.isoformat() if post.created_at else None,
        }
    ), 202


@saas_api.route("/ai-smm-manager/start", methods=["POST"])
@require_auth
def ai_smm_manager_start():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}

    business_type = (data.get("business_type") or "").strip()
    niche = (data.get("niche") or "").strip()
    goal = (data.get("goal") or "").strip()
    language = (data.get("language") or "ru").strip()
    project_id = data.get("project_id")

    if not business_type:
        return jsonify({"error": "Укажите тип бизнеса"}), 400
    if not niche:
        return jsonify({"error": "Укажите нишу"}), 400
    if not goal:
        return jsonify({"error": "Укажите цель"}), 400

    try:
        project_id = int(project_id) if project_id else get_or_create_default_project(user.id).id
    except Exception:
        return jsonify({"error": "project_id должен быть числом"}), 400

    if not can_access_project(user, project_id):
        return jsonify({"error": "У вас нет доступа к проекту"}), 403

    try:
        result = create_monthly_content_plan(
            user=user,
            project_id=project_id,
            business_type=business_type,
            niche=niche,
            goal=goal,
            language=language,
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 429
    except Exception as exc:
        msg = str(exc)
        if "insufficient_quota" in msg or "You exceeded your current quota" in msg:
            return (
                jsonify(
                    {
                        "error": "OpenAI: недостаточно квоты. Пополните баланс/лимит в OpenAI или включите USE_MOCK_PROVIDERS=true для локального теста.",
                    }
                ),
                402,
            )
        return jsonify({"error": f"AI SMM Manager failed: {msg}"}), 500

    return jsonify(
        {
            "message": "AI SMM Manager generated 30-day strategy and scheduled posts.",
            "result": result,
            "billing": get_billing_summary(_current_user_refetched()),
        }
    )


@saas_api.route("/content-plan", methods=["GET"])
@require_auth
def content_plan_list():
    user = g.current_user
    project_id = request.args.get("project_id", type=int)

    db = SessionLocal()
    try:
        query = db.query(ContentPlan)
        if user.role != "admin":
            query = query.filter(ContentPlan.user_id == user.id)
        if project_id:
            query = query.filter(ContentPlan.project_id == project_id)
        rows = query.order_by(ContentPlan.scheduled_at.asc()).limit(500).all()

        return jsonify(
            [
                {
                    "id": r.id,
                    "project_id": r.project_id,
                    "business_type": r.business_type,
                    "goal": r.goal,
                    "language": r.language,
                    "topic": r.topic,
                    "caption": r.caption,
                    "hashtags": r.hashtags,
                    "cta": r.cta,
                    "scheduled_at": r.scheduled_at.isoformat(),
                    "status": r.status,
                    "post_id": r.post_id,
                }
                for r in rows
            ]
        )
    finally:
        db.close()


@saas_api.route("/content-plan/run-due", methods=["POST"])
@require_auth
def content_plan_run_due():
    user = g.current_user
    project_id = request.args.get("project_id", type=int)
    # Admin can run all due items; regular users run only their own.
    target_user_id = None if user.role == "admin" else user.id
    result = run_due_content_plan(limit=200, user_id=target_user_id, project_id=project_id)
    return jsonify(result)


@saas_api.route("/content-plan/materialize", methods=["POST"])
@require_auth
def content_plan_materialize():
    """
    Generate (and charge) posts for upcoming content plan items without publishing.
    Used by Dashboard quick actions like "Пост на сегодня" and "План на неделю".
    """
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}

    days = int(data.get("days") or 7)
    limit = int(data.get("limit") or 20)
    platform = (data.get("platform") or "instagram").strip().lower()
    project_id = data.get("project_id")

    try:
        project_id = int(project_id) if project_id else get_or_create_default_project(user.id).id
    except Exception:
        return jsonify({"error": "project_id должен быть числом"}), 400

    if not can_access_project(user, project_id):
        return jsonify({"error": "У вас нет доступа к проекту"}), 403

    try:
        result = materialize_content_plan(user=user, project_id=project_id, days=days, limit=limit, platform=platform)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 429
    except Exception as exc:
        msg = str(exc)
        if "insufficient_quota" in msg or "You exceeded your current quota" in msg:
            return (
                jsonify(
                    {
                        "error": "OpenAI: недостаточно квоты. Пополните баланс/лимит в OpenAI или включите USE_MOCK_PROVIDERS=true для локального теста.",
                    }
                ),
                402,
            )
        return jsonify({"error": f"Materialize failed: {msg}"}), 500

    # Enqueue async generation for queued posts.
    try:
        from saas_queue import enqueue_generation

        for pid in (result or {}).get("post_ids", []) or []:
            try:
                enqueue_generation(int(pid))
            except Exception:
                pass
    except Exception:
        # Queue is optional in local dev.
        pass

    return jsonify({"message": "ok", "result": result, "billing": get_billing_summary(_current_user_refetched())})


@saas_api.route("/posts", methods=["POST"])
@require_auth
def create_post_draft():
    data = request.get_json(silent=True) or {}
    schedule_at_raw = data.get("schedule_at")
    schedule_at = None
    if schedule_at_raw:
        try:
            schedule_at = datetime.fromisoformat(schedule_at_raw)
        except Exception:
            return jsonify({"error": "schedule_at РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РІ ISO С„РѕСЂРјР°С‚Рµ"}), 400

    payload = {
        **data,
        "long_post_mode": bool(data.get("long_post_mode") or False),
    }

    if schedule_at:
        payload["schedule_at"] = schedule_at.isoformat()

    # Reuse /generate with schedule through explicit path below if needed.
    return generate()


@saas_api.route("/posts", methods=["GET"])
@require_auth
def posts_history():
    user = g.current_user
    project_id = request.args.get("project_id", type=int)
    include_hidden = str(request.args.get("include_hidden") or "").strip().lower() in {"1", "true", "yes"}

    db = SessionLocal()
    try:
        query = db.query(Post)
        if user.role != "admin":
            query = query.filter(Post.user_id == user.id)
        if project_id:
            query = query.filter(Post.project_id == project_id)
        if not include_hidden:
            query = query.filter(Post.status.notin_(["hidden", "deleted"]))

        posts = query.order_by(Post.created_at.desc()).limit(400).all()
        return jsonify(
            [
                {
                    "id": p.id,
                    "project_id": p.project_id,
                    "platform": p.platform,
                    "topic": p.topic,
                    "category": p.category,
                    "status": p.status,
                    "schedule_at": p.schedule_at.isoformat() if p.schedule_at else None,
                    "published_at": p.published_at.isoformat() if p.published_at else None,
                    "remote_id": p.remote_id,
                    "error_message": p.error_message,
                    "title_preview": ((p.generated_text or "").strip().splitlines()[0][:180] if (p.generated_text or "").strip() else ""),
                    "tokens_total": p.tokens_total,
                    "credits_charged": p.credits_charged,
                    "created_at": p.created_at.isoformat(),
                }
                for p in posts
            ]
        )
    finally:
        db.close()


@saas_api.route("/posts/<int:post_id>", methods=["GET"])
@require_auth
def post_details(post_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        post = db.query(Post).filter_by(id=post_id).first()
        if not post:
            return jsonify({"error": "Пост не найден"}), 404
        if user.role != "admin" and post.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403

        return jsonify(
            {
                "id": post.id,
                "user_id": post.user_id,
                "project_id": post.project_id,
                "platform": post.platform,
                "topic": post.topic,
                "category": post.category,
                "language": post.language,
                "tone": post.tone,
                "media_url": post.media_url,
                "prompt_text": post.prompt_text,
                "generated_text": post.generated_text,
                "status": post.status,
                "schedule_at": post.schedule_at.isoformat() if post.schedule_at else None,
                "published_at": post.published_at.isoformat() if post.published_at else None,
                "remote_id": post.remote_id,
                "error_message": post.error_message,
                "tokens_input": post.tokens_input,
                "tokens_output": post.tokens_output,
                "tokens_total": post.tokens_total,
                "credits_charged": post.credits_charged,
                "created_at": post.created_at.isoformat() if post.created_at else None,
            }
        )
    finally:
        db.close()


@saas_api.route("/posts/<int:post_id>", methods=["PATCH"])
@require_auth
def update_post(post_id: int):
    user = g.current_user
    data = request.get_json(silent=True) or {}

    db = SessionLocal()
    try:
        post = db.query(Post).filter_by(id=post_id).first()
        if not post:
            return jsonify({"error": "Пост не найден"}), 404
        if user.role != "admin" and post.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
        if str(post.status or "").lower() in {"hidden", "deleted"}:
            return jsonify({"error": "Скрытый/удаленный пост нельзя редактировать"}), 409
        status_now = str(post.status or "").lower()
        # Protect only truly published posts. Legacy rows may have status=done without remote_id.
        is_published = bool(post.published_at) or (status_now == "done" and bool(post.remote_id))
        if is_published:
            return jsonify({"error": "Опубликованный пост редактировать нельзя"}), 409

        if "topic" in data:
            topic = (data.get("topic") or "").strip()
            if not topic:
                return jsonify({"error": "Тема поста не может быть пустой"}), 400
            post.topic = topic

        if "generated_text" in data:
            post.generated_text = (data.get("generated_text") or "").strip() or None

        if "platform" in data:
            platform = (data.get("platform") or "").strip().lower()
            if platform not in {"facebook", "instagram", "youtube"}:
                return jsonify({"error": "Платформа должна быть facebook, instagram или youtube"}), 400
            post.platform = platform

        if "media_url" in data:
            media_url = (data.get("media_url") or "").strip()
            post.media_url = media_url or None

        if "schedule_at" in data:
            schedule_raw = data.get("schedule_at")
            if schedule_raw in (None, "", "null"):
                post.schedule_at = None
                if str(post.status or "").lower() not in {"done", "failed"}:
                    post.status = "queued"
            else:
                try:
                    post.schedule_at = _parse_iso_datetime(str(schedule_raw))
                except Exception:
                    return jsonify({"error": "schedule_at должен быть в ISO формате"}), 400
                post.status = "scheduled"

        db.commit()
        return jsonify(
            {
                "id": post.id,
                "status": post.status,
                "topic": post.topic,
                "platform": post.platform,
                "generated_text": post.generated_text,
                "media_url": post.media_url,
                "schedule_at": post.schedule_at.isoformat() if post.schedule_at else None,
                "published_at": post.published_at.isoformat() if post.published_at else None,
            }
        )
    finally:
        db.close()


@saas_api.route("/posts/<int:post_id>", methods=["DELETE"])
@require_auth
def delete_post(post_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        post = db.query(Post).filter_by(id=post_id).first()
        if not post:
            return jsonify({"error": "Пост не найден"}), 404
        if user.role != "admin" and post.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403

        status_now = str(post.status or "").lower()
        # Treat as published only when publication is confirmed.
        # Legacy rows may have status=done without actual publish identifiers.
        is_published = bool(post.published_at) or (status_now == "done" and bool(post.remote_id))
        if is_published:
            return jsonify({"error": "Опубликованный пост нельзя удалить. Используйте «Убрать с сайта»."}), 409

        # Soft-delete to avoid FK conflicts with usage/payment/audit rows.
        post.status = "deleted"
        post.schedule_at = None
        post.error_message = None
        db.commit()
        return jsonify({"ok": True, "id": post_id, "deleted": True, "status": "deleted"})
    finally:
        db.close()


@saas_api.route("/posts/<int:post_id>/hide", methods=["POST"])
@require_auth
def hide_post(post_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        post = db.query(Post).filter_by(id=post_id).first()
        if not post:
            return jsonify({"error": "Пост не найден"}), 404
        if user.role != "admin" and post.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403

        post.status = "hidden"
        post.schedule_at = None
        db.commit()
        return jsonify({"ok": True, "id": post_id, "status": "hidden"})
    finally:
        db.close()


@saas_api.route("/generated-posts", methods=["GET"])
@require_auth
def legacy_generated_posts_alias():
    return posts_history()


@saas_api.route("/posts/<int:post_id>/publish", methods=["POST"])
@require_auth
def publish_post(post_id: int):
    user = g.current_user
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_POST_PUBLISH, {"endpoint": "/api/posts/publish"}))
    if pw:
        return pw
    db = SessionLocal()
    started_at = time.perf_counter()
    timing_ms = {}

    def _mark(stage: str, t0: float) -> None:
        timing_ms[stage] = int((time.perf_counter() - t0) * 1000)

    try:
        post = db.query(Post).filter_by(id=post_id).first()
        if not post:
            return jsonify({"error": "РџРѕСЃС‚ РЅРµ РЅР°Р№РґРµРЅ"}), 404
        if user.role != "admin" and post.user_id != user.id:
            return jsonify({"error": "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ"}), 403
        if post.retry_count >= 3:
            return jsonify({"error": "Р”РѕСЃС‚РёРіРЅСѓС‚ РјР°РєСЃРёРјСѓРј РїРѕРІС‚РѕСЂРѕРІ РїСѓР±Р»РёРєР°С†РёРё (3)"}), 429
        if str(post.platform or "").lower() == "youtube":
            return jsonify({"error": "Автопубликация в YouTube API пока не подключена. Доступна генерация контента."}), 400

        # In local/mock mode keep previous behavior.
        if settings.USE_MOCK_PROVIDERS:
            post.status = "done"
            post.published_at = datetime.utcnow()
            post.remote_id = f"mock_{post.id}_{int(datetime.utcnow().timestamp())}"
            post.retry_count += 1
            db.commit()
            recordUsageEvent(user, "POSTS_PUBLISHED", 1, {"endpoint": "/api/posts/publish", "post_id": post.id, "mode": "mock"})
            return jsonify({"id": post.id, "status": post.status, "remote_id": post.remote_id, "mode": "mock"})

        # Real Meta publish path.
        t_conn = time.perf_counter()
        connection = (
            db.query(SocialAccount)
            .filter(
                SocialAccount.user_id == post.user_id,
                SocialAccount.provider == "meta",
            )
            .order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc())
            .first()
        )
        _mark("connection_lookup_ms", t_conn)
        if not connection:
            return jsonify({"error": "Нет подключенного Meta аккаунта для публикации"}), 400
        if not connection.token_encrypted:
            return jsonify({"error": "Токен подключения не найден. Переподключите Facebook."}), 400

        t_decrypt = time.perf_counter()
        try:
            access_token = decrypt_meta_token(connection.token_encrypted)
        except Exception:
            return jsonify({"error": "Не удалось расшифровать токен. Переподключите Facebook."}), 400
        _mark("token_decrypt_ms", t_decrypt)

        caption = (post.generated_text or post.topic or "").strip()
        if not caption:
            return jsonify({"error": "У поста нет текста для публикации"}), 400

        image_url = (post.media_url or "").strip() or None
        if post.platform == "instagram" and not image_url:
            image_context = f"{post.topic or post.prompt_text or 'social media'}. {(post.generated_text or '')[:220]}".strip()
            image_url = build_semantic_fallback_image_url(
                topic=image_context,
                category=getattr(post, "category", None),
                tone=getattr(post, "tone", "friendly") or "friendly",
                language=getattr(post, "language", "ru") or "ru",
            )
        now = datetime.utcnow()
        post.retry_count += 1

        if post.platform == "facebook":
            if not connection.page_id:
                post.status = "failed"
                post.error_message = "Не выбрана Facebook Page в подключении."
                db.commit()
                return jsonify({"error": post.error_message}), 400
            t_publish = time.perf_counter()
            page_access_token = _resolve_page_access_token(access_token, connection.page_id)
            if not page_access_token:
                _apply_meta_status(connection, "permissions_missing", "page_token_missing")
                post.status = "failed"
                post.error_message = "Meta не выдал page access token. Переподключите Facebook и подтвердите права для страницы."
                db.commit()
                return jsonify({"error": post.error_message, "status_reason_code": "page_token_missing"}), 400
            result = publish_to_facebook(connection.page_id, page_access_token, image_url, caption)
            fb_err = result.get("error") if isinstance(result, dict) else None
            fb_code = str((fb_err or {}).get("code", ""))
            if fb_err and fb_code == "324":
                # If Meta rejects image URL, retry with text-only post.
                result = publish_to_facebook(connection.page_id, page_access_token, None, caption)
            _mark("meta_publish_ms", t_publish)
            remote_id = result.get("post_id") or result.get("id")
        else:
            # Instagram publish should use USER access token.
            # Using page token often fails with opaque OAuth errors during media create.
            if not connection.ig_user_id:
                post.status = "failed"
                post.error_message = "Нет связанного Instagram Business у выбранной страницы."
                db.commit()
                return jsonify({"error": post.error_message}), 400
            ig_token = access_token
            t_publish = time.perf_counter()
            result = publish_to_instagram(connection.ig_user_id, ig_token, image_url, caption)
            _mark("meta_publish_ms", t_publish)
            remote_id = result.get("id")

        if result.get("error") or not remote_id:
            meta_error = result.get("error") or {}
            if isinstance(meta_error, str):
                details = result.get("details") if isinstance(result, dict) else None
                if isinstance(details, dict) and isinstance(details.get("error"), dict):
                    meta_error = details.get("error")
            status_from_error, reason = _meta_error_to_status(meta_error)
            _apply_meta_status(connection, status_from_error, reason)
            post.status = "failed"
            post.error_message = str(result.get("error") or result)
            db.commit()
            timing_ms["total_ms"] = int((time.perf_counter() - started_at) * 1000)
            current_app.logger.warning(
                "publish_post failed post_id=%s user_id=%s platform=%s timings=%s details=%s",
                post.id,
                post.user_id,
                post.platform,
                json.dumps(timing_ms, ensure_ascii=False),
                str(result)[:1200],
            )
            return jsonify({"error": "Ошибка публикации в Meta", "details": result, "timing_ms": timing_ms}), 400

        post.status = "done"
        post.published_at = now
        post.remote_id = str(remote_id)
        post.error_message = None
        _apply_meta_status(connection, "connected_ready", None)
        connection.last_success_at = now
        db.commit()
        timing_ms["total_ms"] = int((time.perf_counter() - started_at) * 1000)
        current_app.logger.info(
            "publish_post ok post_id=%s user_id=%s platform=%s timings=%s",
            post.id,
            post.user_id,
            post.platform,
            json.dumps(timing_ms, ensure_ascii=False),
        )
        recordUsageEvent(user, "POSTS_PUBLISHED", 1, {"endpoint": "/api/posts/publish", "post_id": post.id, "mode": "real"})
        return jsonify({"id": post.id, "status": post.status, "remote_id": post.remote_id, "mode": "real", "timing_ms": timing_ms})
    except Exception as exc:
        db.rollback()
        current_app.logger.exception("publish_post failed for post_id=%s user_id=%s", post_id, getattr(user, "id", None))
        return jsonify(
            {
                "error": "Внутренняя ошибка публикации. Попробуйте снова или переподключите Meta.",
                "details": str(exc),
                "status_reason_code": "publish_internal_error",
            }
        ), 500
    finally:
        db.close()


@saas_api.route("/posts/<int:post_id>/schedule", methods=["POST"])
@require_auth
def schedule_post(post_id: int):
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    schedule_at_raw = data.get("schedule_at")
    if not schedule_at_raw:
        return jsonify({"error": "РџРµСЂРµРґР°Р№С‚Рµ schedule_at"}), 400
    try:
        schedule_at = _parse_iso_datetime(schedule_at_raw)
    except Exception:
        return jsonify({"error": "schedule_at РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РІ ISO С„РѕСЂРјР°С‚Рµ"}), 400

    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_SCHEDULE_CREATE, {"endpoint": "/api/posts/schedule"}))
    if pw:
        return pw

    db = SessionLocal()
    try:
        post = db.query(Post).filter_by(id=post_id).first()
        if not post:
            return jsonify({"error": "РџРѕСЃС‚ РЅРµ РЅР°Р№РґРµРЅ"}), 404
        if user.role != "admin" and post.user_id != user.id:
            return jsonify({"error": "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ"}), 403

        post.schedule_at = schedule_at
        post.status = "scheduled"
        db.commit()
        return jsonify({"id": post.id, "status": post.status, "schedule_at": post.schedule_at.isoformat()})
    finally:
        db.close()


@saas_api.route("/posts/bulk-schedule", methods=["POST"])
@require_auth
def bulk_schedule_posts():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return jsonify({"error": "РџРµСЂРµРґР°Р№С‚Рµ items РјР°СЃСЃРёРІРѕРј"}), 400

    platforms = _normalize_requested_platforms(
        data.get("platforms"),
        data.get("platform"),
        default=["instagram"],
    )
    if not platforms:
        return jsonify({"error": "Р’С‹Р±РµСЂРёС‚Рµ С…РѕС‚СЏ Р±С‹ РѕРґРЅСѓ РїР»Р°С‚С„РѕСЂРјСѓ"}), 400

    project_id_raw = data.get("project_id")
    try:
        project_id = int(project_id_raw) if project_id_raw not in (None, "") else 0
    except (TypeError, ValueError):
        return jsonify({"error": "project_id РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ С‡РёСЃР»РѕРј"}), 400
    if not project_id:
        project_id = get_or_create_default_project(user.id).id

    if not can_access_project(user, project_id):
        return jsonify({"error": "РЈ РІР°СЃ РЅРµС‚ РґРѕСЃС‚СѓРїР° Рє РїСЂРѕРµРєС‚Сѓ"}), 403

    pw = _paywall_response_if_needed(
        authorizeAction(
            user,
            ACTION_SCHEDULE_CREATE,
            {"endpoint": "/api/posts/bulk-schedule", "platforms": platforms, "count": len(raw_items)},
        )
    )
    if pw:
        return pw

    category = (data.get("category") or "").strip() or None
    language = (data.get("language") or "ru").strip() or "ru"
    tone = (data.get("tone") or "friendly").strip() or "friendly"
    image_enabled = bool(data.get("image_enabled"))

    normalized_items = []
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            return jsonify({"error": f"items[{idx}] РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РѕР±СЉРµРєС‚РѕРј"}), 400
        topic = (item.get("topic") or "").strip()
        if not topic:
            return jsonify({"error": f"items[{idx}].topic РѕР±СЏР·Р°С‚РµР»РµРЅ"}), 400
        schedule_at_raw = item.get("schedule_at")
        if not schedule_at_raw:
            return jsonify({"error": f"items[{idx}].schedule_at РѕР±СЏР·Р°С‚РµР»РµРЅ"}), 400
        try:
            schedule_at = _parse_iso_datetime(str(schedule_at_raw))
        except Exception:
            return jsonify({"error": f"items[{idx}].schedule_at РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РІ ISO С„РѕСЂРјР°С‚Рµ"}), 400
        generated_text = (item.get("generated_text") or "").strip()
        media_url = (item.get("media_url") or "").strip() or None
        normalized_items.append(
            {
                "topic": topic,
                "generated_text": generated_text,
                "schedule_at": schedule_at,
                "media_url": media_url,
            }
        )

    db = SessionLocal()
    try:
        created = 0
        reused = 0
        created_ids = []
        reused_ids = []
        for item in normalized_items:
            for platform in platforms:
                existing_post = (
                    db.query(Post)
                    .filter(
                        Post.user_id == user.id,
                        Post.project_id == project_id,
                        Post.platform == platform,
                        Post.topic == item["topic"],
                        Post.schedule_at == item["schedule_at"],
                        Post.status != "deleted",
                    )
                    .order_by(Post.id.asc())
                    .first()
                )
                if existing_post:
                    reused += 1
                    reused_ids.append(int(existing_post.id))
                    continue

                media_url = item["media_url"]
                if image_enabled and not media_url and platform in {"facebook", "instagram"}:
                    try:
                        media = _fetch_post_media_or_error(
                            niche=category or item["topic"],
                            topic=item["topic"],
                            platform=platform,
                            post_text=item["generated_text"],
                            db=db,
                            project_id=project_id,
                        )
                        media_url = media.local_url
                    except (PexelsConfigError, PexelsRateLimitError, PexelsRequestError, PexelsEmptyResultError):
                        media_url = None

                post = Post(
                    user_id=user.id,
                    project_id=project_id,
                    platform=platform,
                    prompt_text=item["topic"],
                    generated_text=item["generated_text"] or item["topic"],
                    topic=item["topic"],
                    category=category,
                    language=language,
                    tone=tone,
                    media_url=media_url,
                    tokens_input=0,
                    tokens_output=0,
                    tokens_total=0,
                    credits_charged=0,
                    status="scheduled",
                    schedule_at=item["schedule_at"],
                    published_at=None,
                    error_message=None,
                )
                db.add(post)
                db.flush()
                created += 1
                created_ids.append(int(post.id))

        db.commit()
        return jsonify(
            {
                "created": created,
                "reused": reused,
                "total": created + reused,
                "created_ids": created_ids,
                "reused_ids": reused_ids,
            }
        )
    finally:
        db.close()



META_CONNECTION_STATUSES = {
    "not_connected",
    "connected_need_page",
    "connected_ready",
    "token_expired",
    "permissions_missing",
    "disconnected",
    "error",
}


def _normalize_connection_status(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in META_CONNECTION_STATUSES:
        return raw
    if raw == "connected":
        return "connected_ready"
    if raw in {"action_required", "needs_action"}:
        return "connected_need_page"
    if raw == "failed":
        return "error"
    return "not_connected"


def _status_help_text(reason_code: str, status: str) -> str:
    reason = (reason_code or "").strip().lower()
    if status == "connected_ready":
        return "Подключение работает. Можно публиковать и планировать посты."
    if reason == "no_pages":
        return "У аккаунта нет доступных Facebook Pages. Проверьте роли страницы и права pages_show_list."
    if reason == "ig_not_linked":
        return "У выбранной Facebook Page не привязан Instagram Business."
    if reason == "permissions_revoked":
        return "Приложению не хватает разрешений. Переподключите аккаунт и подтвердите все запрошенные права."
    if reason == "page_token_missing":
        return "Для выбранной страницы не выдан page access token. Переподключите аккаунт и подтвердите права для страницы."
    if reason == "access_token_invalid":
        return "Токен недействителен или истёк. Выполните переподключение."
    if reason == "user_revoked_access":
        return "Доступ был отозван в Meta. Нажмите «Переподключить»."
    if reason == "meta_api_error":
        return "Meta API вернул ошибку. Попробуйте снова или откройте детали."
    if status in {"token_expired", "permissions_missing", "disconnected"}:
        return "Требуется переподключение."
    if status == "connected_need_page":
        return "Выберите рабочую Facebook Page для публикаций."
    return "Проверьте детали подключения и попробуйте снова."


def _meta_error_to_status(meta_error):
    if isinstance(meta_error, dict):
        err = meta_error
        msg = str(err.get("message") or "").lower()
        code = str(err.get("code") or "")
    else:
        msg = str(meta_error or "").lower()
        code = ""
    if code in {"190", "102"} or "access token" in msg or "oauth" in msg:
        return "token_expired", "access_token_invalid"
    if code in {"10", "200"} or "permission" in msg or "requires" in msg or "insufficient" in msg:
        return "permissions_missing", "permissions_revoked"
    if "user_denied" in msg or "denied" in msg:
        return "disconnected", "user_revoked_access"
    return "error", "meta_api_error"


def _extract_meta_error_text(payload) -> str:
    if not isinstance(payload, dict):
        return ""
    err = payload.get("error")
    if isinstance(err, dict):
        msg = str(err.get("message") or "").strip()
        code = str(err.get("code") or "").strip()
        if code and msg:
            return f"[{code}] {msg}"
        return msg
    if isinstance(err, str):
        return err.strip()
    return ""


def _resolve_page_access_token(user_access_token: str, page_id: str) -> str:
    if not user_access_token or not page_id:
        return ""
    raw = list_pages(user_access_token, include_page_access_token=True)
    pages = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(pages, list):
        return ""
    selected = next((p for p in pages if str(p.get("id")) == str(page_id)), None)
    if not isinstance(selected, dict):
        return ""
    return str(selected.get("access_token") or "").strip()


def _fetch_post_media_or_error(
    *,
    niche: str | None,
    topic: str,
    platform: str,
    post_text: str | None = None,
    db=None,
    project_id: int | None = None,
    used_external_ids: set[str] | None = None,
    used_urls: set[str] | None = None,
):
    return fetch_post_image(
        niche=niche,
        topic=topic,
        platform=platform,
        post_text=post_text,
        db=db,
        project_id=project_id,
        used_external_ids=used_external_ids,
        used_urls=used_urls,
    )


def _latest_meta_connection(db, user_id: int):
    return (
        db.query(SocialAccount)
        .filter(
            SocialAccount.user_id == user_id,
            SocialAccount.provider == "meta",
        )
        .order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc())
        .first()
    )


def _publish_post_via_meta(db, post: Post, *, publish_to_linked_instagram: bool = False) -> dict:
    connection = _latest_meta_connection(db, post.user_id)
    if not connection:
        return {"ok": False, "error": "??? ????????????? Meta ???????? ??? ??????????"}
    if not connection.token_encrypted:
        return {"ok": False, "error": "????? ??????????? ?? ??????. ?????????????? Facebook."}

    try:
        access_token = decrypt_meta_token(connection.token_encrypted)
    except Exception:
        return {"ok": False, "error": "?? ??????? ???????????? ?????. ?????????????? Facebook."}

    caption = (post.generated_text or post.topic or "").strip()
    if not caption:
        return {"ok": False, "error": "? ????? ??? ?????? ??? ??????????"}

    image_url = (post.media_url or "").strip() or None
    needs_instagram = str(post.platform or "").lower() == "instagram"
    if needs_instagram and not image_url:
        try:
            media = _fetch_post_media_or_error(
                niche=getattr(post, "category", None) or post.topic,
                topic=post.topic or post.prompt_text or "social media",
                platform="instagram",
                post_text=post.generated_text or "",
                db=db,
                project_id=int(getattr(post, "project_id", 0) or 0) or None,
            )
            image_url = media.local_url
            post.media_url = media.local_url
            db.flush()
        except (PexelsConfigError, PexelsRateLimitError, PexelsRequestError, PexelsEmptyResultError):
            image_url = None

    if str(post.platform or "").lower() == "facebook":
        if not connection.page_id:
            post.status = "failed"
            post.error_message = "?? ??????? Facebook Page ? ???????????."
            db.flush()
            return {"ok": False, "error": post.error_message}
        page_access_token = _resolve_page_access_token(access_token, connection.page_id)
        if not page_access_token:
            _apply_meta_status(connection, "permissions_missing", "page_token_missing")
            post.status = "failed"
            post.error_message = "Meta ?? ????? page access token. ?????????????? Facebook ? ??????????? ????? ??? ????????."
            db.flush()
            return {"ok": False, "error": post.error_message, "status_reason_code": "page_token_missing"}
        result = publish_to_facebook(connection.page_id, page_access_token, image_url, caption)
        fb_err = result.get("error") if isinstance(result, dict) else None
        fb_code = str((fb_err or {}).get("code", ""))
        if fb_err and fb_code == "324":
            result = publish_to_facebook(connection.page_id, page_access_token, None, caption)
        remote_id = result.get("post_id") or result.get("id")
        if result.get("error") or not remote_id:
            meta_error = result.get("error") or {}
            if isinstance(meta_error, str):
                details = result.get("details") if isinstance(result, dict) else None
                if isinstance(details, dict) and isinstance(details.get("error"), dict):
                    meta_error = details.get("error")
            status_from_error, reason = _meta_error_to_status(meta_error)
            _apply_meta_status(connection, status_from_error, reason)
            post.status = "failed"
            post.error_message = str(result.get("error") or result)
            db.flush()
            return {"ok": False, "error": "?????? ?????????? ? Facebook", "details": result}
        post.status = "done"
        post.published_at = datetime.utcnow()
        post.remote_id = str(remote_id)
        post.error_message = None
        _apply_meta_status(connection, "connected_ready", None)
        connection.last_success_at = datetime.utcnow()
        db.flush()
        return {"ok": True, "facebook": result, "remote_id": str(remote_id)}

    if not connection.ig_user_id:
        post.status = "failed"
        post.error_message = "??? ?????????? Instagram Business ? ????????? ????????."
        db.flush()
        return {"ok": False, "error": post.error_message}

    result = publish_to_instagram(connection.ig_user_id, access_token, image_url, caption)
    remote_id = result.get("id")
    if result.get("error") or not remote_id:
        meta_error = result.get("error") or {}
        status_from_error, reason = _meta_error_to_status(meta_error)
        _apply_meta_status(connection, status_from_error, reason)
        post.status = "failed"
        post.error_message = str(result.get("error") or result)
        db.flush()
        return {"ok": False, "error": "?????? ?????????? ? Instagram", "details": result}

    post.status = "done"
    post.published_at = datetime.utcnow()
    post.remote_id = str(remote_id)
    post.error_message = None
    _apply_meta_status(connection, "connected_ready", None)
    connection.last_success_at = datetime.utcnow()
    db.flush()
    return {"ok": True, "instagram": result, "remote_id": str(remote_id)}


def _scheduled_publish_error_text(result: dict | None = None, exc: Exception | None = None) -> str:
    if exc is not None:
        return f"{exc.__class__.__name__}: {str(exc)[:1000]}".strip()
    if isinstance(result, dict):
        details_text = _extract_meta_error_text(result.get("details"))
        if details_text:
            return details_text[:1000]
        err = str(result.get("error") or "").strip()
        if err:
            return err[:1000]
        reason = str(result.get("status_reason_code") or "").strip()
        if reason:
            return reason[:1000]
    return "scheduled_publish_failed"


def _scheduled_publish_timeout_minutes() -> int:
    return 20


def _recover_stuck_publishing_posts(db, now: datetime, timeout_minutes: int = 20) -> int:
    safe_timeout = max(1, int(timeout_minutes or 20))
    cutoff = now - timedelta(minutes=safe_timeout)
    recovery_reason = f"publishing timeout recovery after {safe_timeout} minutes"
    bind = db.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "") or ""

    if dialect_name == "postgresql":
        rows = db.execute(
            text(
                """
                WITH stuck AS (
                    SELECT id, platform, schedule_at, created_at
                    FROM posts
                    WHERE status = 'publishing'
                      AND published_at IS NULL
                      AND COALESCE(schedule_at, created_at) <= :cutoff
                    ORDER BY COALESCE(schedule_at, created_at) ASC, id ASC
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE posts AS p
                SET status = 'failed',
                    error_message = :recovery_reason,
                    retry_count = COALESCE(p.retry_count, 0) + 1
                FROM stuck
                WHERE p.id = stuck.id
                RETURNING
                    p.id AS id,
                    p.platform AS platform,
                    p.schedule_at AS schedule_at,
                    p.created_at AS created_at,
                    p.retry_count AS retry_count
                """
            ),
            {
                "cutoff": cutoff,
                "recovery_reason": recovery_reason,
            },
        ).mappings().all()
        db.commit()
        for row in rows:
            age_basis = row.get("schedule_at") or row.get("created_at")
            logging.warning(
                "scheduled publish recovered stuck post post_id=%s platform=%s reason=%s timeout_minutes=%s age_basis=%s retry_count=%s",
                row.get("id"),
                row.get("platform"),
                recovery_reason,
                safe_timeout,
                age_basis,
                row.get("retry_count"),
            )
        return len(rows)

    # Best-effort fallback for non-Postgres/dev runtimes. Production correctness relies on the
    # Postgres path above; this branch keeps local import/runtime compatibility without widening scope.
    rows = (
        db.query(Post)
        .filter(
            Post.status == "publishing",
            Post.published_at.is_(None),
            func.coalesce(Post.schedule_at, Post.created_at) <= cutoff,
        )
        .order_by(func.coalesce(Post.schedule_at, Post.created_at).asc(), Post.id.asc())
        .all()
    )
    recovered = 0
    for post in rows:
        post.status = "failed"
        post.error_message = recovery_reason
        post.retry_count = int(post.retry_count or 0) + 1
        recovered += 1
        age_basis = post.schedule_at or post.created_at
        logging.warning(
            "scheduled publish recovered stuck post post_id=%s platform=%s reason=%s timeout_minutes=%s age_basis=%s retry_count=%s",
            post.id,
            post.platform,
            recovery_reason,
            safe_timeout,
            age_basis,
            post.retry_count,
        )
    db.commit()
    return recovered


def _claim_due_scheduled_posts(db, now: datetime, limit: int) -> list[dict]:
    safe_limit = max(1, int(limit or 20))
    bind = db.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "") or ""

    if dialect_name == "postgresql":
        rows = db.execute(
            text(
                """
                WITH due AS (
                    SELECT id, status AS previous_status, platform, schedule_at
                    FROM posts
                    WHERE status IN ('scheduled', 'queued')
                      AND schedule_at IS NOT NULL
                      AND schedule_at <= :now
                    ORDER BY schedule_at ASC, id ASC
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE posts AS p
                SET status = 'publishing'
                FROM due
                WHERE p.id = due.id
                RETURNING
                    p.id AS id,
                    due.previous_status AS previous_status,
                    p.platform AS platform,
                    p.schedule_at AS schedule_at
                """
            ),
            {"now": now, "limit": safe_limit},
        ).mappings().all()
        db.commit()
        return [dict(row) for row in rows]

    # Best-effort fallback for non-Postgres/dev runtimes. Production correctness relies on the
    # Postgres path above; this branch keeps local import/runtime compatibility without widening scope.
    rows = (
        db.query(Post.id, Post.status, Post.platform, Post.schedule_at)
        .filter(
            Post.status.in_(["scheduled", "queued"]),
            Post.schedule_at.isnot(None),
            Post.schedule_at <= now,
        )
        .order_by(Post.schedule_at.asc(), Post.id.asc())
        .limit(safe_limit)
        .all()
    )
    claimed: list[dict] = []
    for row in rows:
        updated = (
            db.query(Post)
            .filter(Post.id == row.id, Post.status == row.status)
            .update({"status": "publishing"}, synchronize_session=False)
        )
        if updated:
            claimed.append(
                {
                    "id": int(row.id),
                    "previous_status": str(row.status or ""),
                    "platform": str(row.platform or ""),
                    "schedule_at": row.schedule_at,
                }
            )
    db.commit()
    return claimed


def publish_due_scheduled_posts(limit: int = 20) -> dict:
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        timeout_minutes = _scheduled_publish_timeout_minutes()
        recovered = _recover_stuck_publishing_posts(db, now, timeout_minutes)
        logging.info(
            "scheduled publish recovery recovered=%s timeout_minutes=%s",
            recovered,
            timeout_minutes,
        )
        claimed = _claim_due_scheduled_posts(db, now, limit)
        logging.info("scheduled publish claimed limit=%s claimed=%s", max(1, int(limit or 20)), len(claimed))
        published = 0
        failed = 0
        if not claimed:
            return {"published": 0, "failed": 0, "processed": 0}

        post_ids = [int(item["id"]) for item in claimed]
        posts = db.query(Post).filter(Post.id.in_(post_ids)).all()
        posts_by_id = {int(post.id): post for post in posts}

        for item in claimed:
            post_id = int(item["id"])
            post = posts_by_id.get(post_id)
            platform = str(item.get("platform") or "")
            if not post:
                failed += 1
                logging.error(
                    "scheduled publish missing claimed post post_id=%s platform=%s previous_status=%s",
                    post_id,
                    platform,
                    item.get("previous_status"),
                )
                continue

            logging.info(
                "scheduled publish picked post_id=%s platform=%s status_before=%s claimed_status=%s schedule_at=%s",
                post_id,
                platform,
                item.get("previous_status"),
                str(post.status or ""),
                item.get("schedule_at"),
            )

            try:
                result = _publish_post_via_meta(db, post)
                if result.get("ok"):
                    published += 1
                    db.commit()
                    logging.info(
                        "scheduled publish success post_id=%s platform=%s remote_id=%s",
                        post_id,
                        platform,
                        result.get("remote_id"),
                    )
                    continue

                failed += 1
                if str(post.status or "") == "publishing":
                    post.status = "failed"
                    post.error_message = _scheduled_publish_error_text(result=result)
                    db.flush()
                db.commit()
                logging.warning(
                    "scheduled publish failure post_id=%s platform=%s reason=%s status_reason_code=%s",
                    post_id,
                    platform,
                    _scheduled_publish_error_text(result=result),
                    result.get("status_reason_code"),
                )
            except Exception as exc:
                db.rollback()
                failed += 1
                recovery_post = db.query(Post).filter_by(id=post_id).first()
                if recovery_post and str(recovery_post.status or "") == "publishing":
                    recovery_post.status = "failed"
                    recovery_post.error_message = _scheduled_publish_error_text(exc=exc)
                    db.commit()
                logging.exception(
                    "scheduled publish unexpected error post_id=%s platform=%s",
                    post_id,
                    platform,
                )

        logging.info(
            "scheduled publish batch processed=%s published=%s failed=%s",
            len(claimed),
            published,
            failed,
        )
        return {"published": published, "failed": failed, "processed": len(claimed)}
    finally:
        db.close()

def _apply_meta_status(row: SocialAccount, status: str, reason_code: str = None) -> None:
    row.status = _normalize_connection_status(status)
    row.status_reason_code = reason_code
    row.updated_at = datetime.utcnow()
    if row.status == "connected_ready":
        row.last_success_at = datetime.utcnow()
        row.status_reason_code = None


def _connection_primary_action(status: str):
    mapping = {
        "not_connected": {"label": "Подключить Facebook", "action": "connect"},
        "connected_need_page": {"label": "Выбрать страницу", "action": "pick_page"},
        "connected_ready": {"label": "Тест публикации", "action": "test"},
        "token_expired": {"label": "Переподключить", "action": "reconnect"},
        "permissions_missing": {"label": "Переподключить", "action": "reconnect"},
        "disconnected": {"label": "Переподключить", "action": "reconnect"},
        "error": {"label": "Повторить", "action": "retry"},
    }
    return mapping.get(status, mapping["error"])


def _serialize_connection(row: SocialAccount) -> dict:
    status = _normalize_connection_status(row.status)
    reason = row.status_reason_code
    # Defensive correction so "Готово" cannot appear with incomplete data.
    if status == "connected_ready" and (not row.page_id or not row.token_encrypted):
        status = "connected_need_page"
    if not row.token_encrypted and status not in {"disconnected", "error"}:
        status = "not_connected"

    primary = _connection_primary_action(status)
    return {
        "id": row.id,
        "provider": row.provider,
        "facebook_page_id": row.page_id,
        "facebook_page_name": row.page_name,
        "facebook_page_picture_url": getattr(row, "page_picture_url", None),
        "instagram_business_id": row.ig_user_id,
        "instagram_username": getattr(row, "ig_username", None),
        # Backward-compatible aliases for existing frontend code.
        "page_id": row.page_id,
        "page_name": row.page_name,
        "page_picture_url": getattr(row, "page_picture_url", None),
        "ig_user_id": row.ig_user_id,
        "ig_username": getattr(row, "ig_username", None),
        "status": status,
        "status_reason_code": reason,
        "status_help_text": _status_help_text(reason, status),
        "primary_action": primary,
        "meta_redirect_uri": _meta_redirect_uri(),
        "last_success_at": row.last_success_at.isoformat() if row.last_success_at else None,
        "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        "token_expires_at": row.token_expires_at.isoformat() if row.token_expires_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "tech_log": json.dumps(
            {
                "connection_id": row.id,
                "provider": row.provider,
                "status": status,
                "status_reason_code": reason,
                "meta_redirect_uri": _meta_redirect_uri(),
                "facebook_page_id": row.page_id,
                "instagram_business_id": row.ig_user_id,
                "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
            },
            ensure_ascii=False,
        ),
    }


def _serialize_youtube_connection(row: SocialAccount | None) -> dict:
    if not row:
        return {
            "connected": False,
            "status": "not_connected",
            "channel_id": None,
            "channel_name": None,
            "updated_at": None,
        }
    status = str(row.status or "not_connected").strip().lower()
    connected = status in {"connected", "connected_ready"}
    return {
        "connected": connected,
        "status": status,
        "channel_id": row.page_id,
        "channel_name": row.page_name,
        "channel_picture_url": getattr(row, "page_picture_url", None),
        "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
    }


@saas_api.route("/integrations/meta/connect", methods=["POST"])
@saas_api.route("/connections/meta/start", methods=["POST"])
@require_auth
def meta_start():
    pw = _paywall_response_if_needed(authorizeAction(g.current_user, ACTION_ACCOUNT_CONNECT, {"provider": "meta", "endpoint": "/api/integrations/meta/connect"}))
    if pw:
        return pw
    if settings.MOCK_META:
        return jsonify(
            {
                "oauth_url": f"{_frontend_connections_url('connected=1&mock_meta=1')}",
                "redirect_uri": _meta_redirect_uri(),
                "mock": True,
            }
        )

    app_id = (os.getenv("FB_APP_ID") or _facebook_client_id() or "").strip()
    redirect_uri = _meta_redirect_uri()
    # Use exactly the configured scopes. Meta may reject some permissions as "Invalid Scopes"
    # unless the corresponding products/use-cases are added and access is granted.
    scope_raw = os.getenv(
        "FB_OAUTH_SCOPE",
        "pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,instagram_content_publish,business_management",
    ).strip()
    scopes = [s.strip() for s in scope_raw.split(",") if s.strip()]
    # Deduplicate while preserving order.
    seen = set()
    scope = ",".join([s for s in scopes if not (s in seen or seen.add(s))])

    if not app_id:
        return jsonify({"error": "Facebook App ID не настроен. Добавьте FB_APP_ID или FB_LOGIN_APP_ID в .env"}), 400

    oauth_url = f"https://www.facebook.com/v20.0/dialog/oauth?{urlencode({'client_id': app_id, 'redirect_uri': redirect_uri, 'scope': scope, 'state': f'user_{g.current_user.id}'})}"
    print(f"[meta_oauth] start client_id={app_id} redirect_uri={redirect_uri} scope={scope}")
    return jsonify({"oauth_url": oauth_url, "redirect_uri": redirect_uri})


@saas_api.route("/integrations/meta/callback", methods=["GET"])
@saas_api.route("/connections/meta/callback", methods=["GET"])
def meta_callback():
    if settings.MOCK_META:
        return redirect(_frontend_connections_url("connected=1&mock_meta=1"))

    if request.args.get("error"):
        # User denied or Meta returned authorization error.
        state_token = request.args.get("state") or ""
        user_id = None
        if state_token.startswith("user_"):
            try:
                user_id = int(state_token.split("_", 1)[1])
            except Exception:
                user_id = None
        if user_id:
            db = SessionLocal()
            try:
                row = db.query(SocialAccount).filter_by(user_id=user_id, provider="meta").first()
                if row:
                    _apply_meta_status(row, "disconnected", "user_revoked_access")
                    db.commit()
            finally:
                db.close()
        return redirect(_frontend_connections_url("error=oauth_denied"))

    code = request.args.get("code")
    state_token = request.args.get("state")
    if not code:
        return jsonify({"error": "Missing code"}), 400

    # Must match redirect_uri used in /integrations/meta/connect
    redirect_uri = _meta_redirect_uri()

    token_data = exchange_code_for_token(code, redirect_uri=redirect_uri)
    access_token = token_data.get("access_token")
    if not access_token:
        err = token_data.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or ""
            err_type = err.get("type") or ""
            err_code = err.get("code") or ""
        else:
            msg = str(err or "")
            err_type = ""
            err_code = ""
        http_status = token_data.get("_http_status") or ""
        print(
            f"[meta_oauth] token_exchange_failed status={http_status} type={err_type} code={err_code} "
            f"redirect_uri={redirect_uri} msg={msg[:220]}"
        )
        return redirect(
            _frontend_connections_url(
                f"error=token_exchange_failed&status={quote(str(http_status))}&message={quote(str(msg)[:180])}"
            )
        )

    page_id, ig_user_id, raw = get_page_and_ig_id(access_token)
    page_name = None
    if raw.get("data"):
        # Prefer page that has IG business; fallback to first page.
        pages = raw.get("data") or []
        selected_page = next((p for p in pages if p.get("instagram_business_account")), pages[0])
        page_name = selected_page.get("name")
        page_id = selected_page.get("id")
        ig_user_id = (selected_page.get("instagram_business_account") or {}).get("id")

    user_id = None
    if state_token:
        # state format expected: user_{id}
        if state_token.startswith("user_"):
            try:
                user_id = int(state_token.split("_", 1)[1])
            except Exception:
                user_id = None

    if not user_id:
        return redirect(_frontend_connections_url("error=state_invalid"))

    db_guard = SessionLocal()
    try:
        callback_user = db_guard.query(AppUser).filter_by(id=user_id).first()
    finally:
        db_guard.close()
    if not callback_user:
        return redirect(_frontend_connections_url("error=state_invalid"))
    authz = authorizeAction(callback_user, ACTION_ACCOUNT_CONNECT, {"provider": "meta", "endpoint": "/api/integrations/meta/callback"})
    if not authz.get("allowed", False):
        code = (authz.get("error_payload") or {}).get("error") or "PAYWALL_LIMIT"
        return redirect(_frontend_connections_url(f"error=paywall&message={quote(code)}"))

    db = SessionLocal()
    try:
        row = db.query(SocialAccount).filter_by(user_id=user_id, provider="meta").first()
        if not row:
            row = SocialAccount(user_id=user_id, provider="meta")
            db.add(row)

        row.page_id = page_id
        row.page_name = page_name
        # Try to store page picture / IG username for clearer UI. Not critical if missing.
        try:
            if raw.get("data"):
                pages = raw.get("data") or []
                selected_page = next((p for p in pages if p.get("instagram_business_account")), pages[0])
                pic = (selected_page.get("picture") or {}).get("data") or {}
                row.page_picture_url = pic.get("url")
                row.ig_username = (selected_page.get("instagram_business_account") or {}).get("username")
        except Exception:
            pass
        row.ig_user_id = ig_user_id
        row.token_encrypted = encrypt_meta_token(access_token)
        if raw.get("error"):
            status, reason = _meta_error_to_status(raw.get("error") or {})
            _apply_meta_status(row, status, reason)
        elif not page_id:
            _apply_meta_status(row, "connected_need_page", "no_pages")
        elif not ig_user_id:
            _apply_meta_status(row, "connected_need_page", "ig_not_linked")
        else:
            _apply_meta_status(row, "connected_ready")
        db.commit()
    finally:
        db.close()

    if raw.get("error"):
        msg = (raw.get("error") or {}).get("message") or ""
        return redirect(_frontend_connections_url(f"error=meta_api_error&message={quote(msg[:180])}"))
    if not page_id:
        # Help debug: often missing permissions or user has no Page roles.
        return redirect(_frontend_connections_url("error=no_pages&message=Проверьте%20что%20у%20аккаунта%20есть%20роль%20на%20Facebook%20Page%20и%20выданы%20права%20pages_show_list/pages_manage_posts"))
    if not ig_user_id:
        return redirect(_frontend_connections_url("error=no_ig_business"))
    return redirect(_frontend_connections_url("connected=1"))


@saas_api.route("/connections", methods=["GET"])
@require_auth
def list_connections():
    user = g.current_user
    include_all = (request.args.get("scope") or "").strip().lower() == "all"
    db = SessionLocal()
    try:
        query = db.query(SocialAccount)
        if user.role != "admin" or not include_all:
            query = query.filter(SocialAccount.user_id == user.id)
        rows_all = query.order_by(SocialAccount.created_at.desc()).all()
        rows = []
        for row in rows_all:
            if row.provider != "meta":
                continue
            rows.append(row)
        return jsonify([_serialize_connection(row) for row in rows])
    finally:
        db.close()


@saas_api.route("/dashboard/sync", methods=["POST"])
@require_auth
def dashboard_sync_metrics():
    db = SessionLocal()
    try:
        max_items = int((request.get_json(silent=True) or {}).get("max_items_per_account") or 25)
        result = sync_dashboard_metrics_for_user(db, g.current_user.id, max_items_per_account=max_items)
        return jsonify(result)
    finally:
        db.close()


@saas_api.route("/dashboard/summary", methods=["GET"])
@require_auth
def dashboard_metrics_summary():
    days = int((request.args.get("days") or "30").strip() or 30)
    db = SessionLocal()
    try:
        return jsonify(dashboard_summary(db, g.current_user.id, days))
    finally:
        db.close()


@saas_api.route("/dashboard/ai-score", methods=["GET"])
@require_auth
def dashboard_metrics_ai_score():
    days = int((request.args.get("days") or "30").strip() or 30)
    pw = _paywall_response_if_needed(authorizeAction(g.current_user, ACTION_ANALYTICS_ADVANCED, {"endpoint": "/api/dashboard/ai-score"}))
    if pw:
        return pw
    db = SessionLocal()
    try:
        payload = dashboard_ai_score(db, g.current_user.id, days, persist=True)
        db.commit()
        return jsonify(payload)
    finally:
        db.close()


@saas_api.route("/dashboard/forecast", methods=["GET"])
@require_auth
def dashboard_metrics_forecast():
    horizon = int((request.args.get("horizon") or "7").strip() or 7)
    days = int((request.args.get("days") or "90").strip() or 90)
    db = SessionLocal()
    try:
        payload = dashboard_forecast(db, g.current_user.id, horizon=horizon, days=days, persist=True)
        db.commit()
        return jsonify(payload)
    finally:
        db.close()


@saas_api.route("/dashboard/timeseries", methods=["GET"])
@require_auth
def dashboard_metrics_timeseries():
    days = int((request.args.get("days") or "30").strip() or 30)
    db = SessionLocal()
    try:
        return jsonify(dashboard_timeseries(db, g.current_user.id, days))
    finally:
        db.close()


@saas_api.route("/dashboard/insights", methods=["GET"])
@require_auth
def dashboard_metrics_insights():
    days = int((request.args.get("days") or "30").strip() or 30)
    pw = _paywall_response_if_needed(authorizeAction(g.current_user, ACTION_ANALYTICS_ADVANCED, {"endpoint": "/api/dashboard/insights"}))
    if pw:
        return pw
    db = SessionLocal()
    try:
        return jsonify(dashboard_insights(db, g.current_user.id, days))
    finally:
        db.close()


@saas_api.route("/dashboard/recent", methods=["GET"])
@require_auth
def dashboard_metrics_recent():
    limit = int((request.args.get("limit") or "10").strip() or 10)
    db = SessionLocal()
    try:
        return jsonify(dashboard_recent(db, g.current_user.id, limit))
    finally:
        db.close()


def _weekday_ru(idx: int) -> str:
    arr = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return arr[int(idx) % 7]


def _default_best_slots(platform_key: str) -> tuple[list[int], list[int]]:
    key = str(platform_key or "instagram").lower()
    if key == "youtube":
        return [1, 5], [12, 19]
    return [2, 4], [11, 18]


def _next_slot_datetimes(best_days: list[int], best_hours: list[int], take: int = 6) -> list[datetime]:
    now = datetime.utcnow()
    out = []
    for shift in range(0, 21):
        day = now + timedelta(days=shift)
        if day.weekday() not in best_days:
            continue
        for h in best_hours:
            dt = day.replace(hour=int(h), minute=0, second=0, microsecond=0)
            if dt <= now:
                continue
            out.append(dt)
    out.sort()
    return out[: max(1, int(take))]


@saas_api.route("/ai/best-posting-times", methods=["GET"])
@require_auth
def ai_best_posting_times():
    pw = _paywall_response_if_needed(authorizeAction(g.current_user, ACTION_ANALYTICS_ADVANCED, {"endpoint": "/api/ai/best-posting-times"}))
    if pw:
        return pw
    days = int((request.args.get("days") or "90").strip() or 90)
    days = max(14, min(days, 365))
    platform = str(request.args.get("platform") or "instagram").strip().lower()
    provider_platform = "youtube" if platform == "youtube" else "meta"
    now = datetime.utcnow()
    since = now - timedelta(days=days)

    db = SessionLocal()
    try:
        # Aggregate engagement score by weekday from available metrics.
        items = (
            db.query(ContentItem.id, ContentItem.published_at, ContentItem.platform)
            .filter(
                ContentItem.user_id == g.current_user.id,
                ContentItem.published_at.isnot(None),
                ContentItem.published_at >= since,
            )
            .all()
        )
        item_ids = [int(x[0]) for x in items if x and x[0]]
        metric_rows = []
        if item_ids:
            metric_rows = (
                db.query(
                    ContentMetricDaily.content_item_id,
                    ContentMetricDaily.day,
                    ContentMetricDaily.reach,
                    ContentMetricDaily.likes,
                    ContentMetricDaily.comments,
                    ContentMetricDaily.shares,
                    ContentMetricDaily.views,
                )
                .filter(ContentMetricDaily.content_item_id.in_(item_ids), ContentMetricDaily.day >= since.date())
                .all()
            )

        item_map = {int(i[0]): {"published_at": i[1], "platform": str(i[2] or "").lower()} for i in items if i and i[0]}
        day_scores = {k: [] for k in range(7)}
        hour_scores = {k: [] for k in range(24)}

        for row in metric_rows:
            cid = int(row[0])
            meta = item_map.get(cid) or {}
            p = str(meta.get("platform") or "")
            if p and p != provider_platform:
                continue
            day_obj = row[1]
            reach = float(row[2] or 0.0)
            eng = float((row[3] or 0) + (row[4] or 0) + (row[5] or 0))
            views = float(row[6] or 0.0)
            rate = (eng / max(reach, 1.0)) * 0.7 + (views / max(reach, 1.0)) * 0.3
            wd = day_obj.weekday()
            day_scores[wd].append(rate)
            published_at = meta.get("published_at")
            if published_at:
                hour_scores[published_at.hour].append(rate)

        # Fallback to post scheduling/publish patterns if metrics are sparse.
        if not any(day_scores[k] for k in day_scores):
            posts = (
                db.query(Post.platform, Post.schedule_at, Post.published_at)
                .filter(
                    Post.user_id == g.current_user.id,
                    ((Post.schedule_at.isnot(None)) | (Post.published_at.isnot(None))),
                    (((Post.schedule_at >= since) | (Post.published_at >= since))),
                )
                .all()
            )
            for p, s_at, pub_at in posts:
                p_key = "youtube" if str(p or "").lower() == "youtube" else "meta"
                if p_key != provider_platform:
                    continue
                dt = pub_at or s_at
                if not dt:
                    continue
                day_scores[dt.weekday()].append(0.1)
                hour_scores[dt.hour].append(0.1)

        if any(day_scores[k] for k in day_scores):
            ranked_days = sorted(day_scores.keys(), key=lambda d: (sum(day_scores[d]) / max(len(day_scores[d]), 1.0)), reverse=True)
            best_days = ranked_days[:2]
        else:
            best_days, _ = _default_best_slots(platform)

        if any(hour_scores[k] for k in hour_scores):
            ranked_hours = sorted(hour_scores.keys(), key=lambda h: (sum(hour_scores[h]) / max(len(hour_scores[h]), 1.0)), reverse=True)
            day_hours = [h for h in ranked_hours if 8 <= int(h) <= 21]
            best_hours = (day_hours[:2] if len(day_hours) >= 2 else ranked_hours[:2])
        else:
            _, best_hours = _default_best_slots(platform)

        next_slots = _next_slot_datetimes(best_days=best_days, best_hours=best_hours, take=6)
        return jsonify(
            {
                "status": "ok",
                "platform": platform,
                "best_days": [{"weekday": int(d), "label": _weekday_ru(d)} for d in best_days],
                "best_hours": [int(h) for h in best_hours],
                "next_slots": [dt.isoformat() for dt in next_slots],
                "source_days": days,
            }
        )
    finally:
        db.close()


@saas_api.route("/dashboard/recent/<int:item_id>", methods=["DELETE"])
@require_auth
def dashboard_metrics_recent_delete(item_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
        if not item:
            return jsonify({"error": "Публикация не найдена"}), 404
        if user.role != "admin" and item.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403

        db.query(ContentMetricDaily).filter(ContentMetricDaily.content_item_id == item.id).delete(synchronize_session=False)
        db.delete(item)
        db.commit()
        return jsonify({"ok": True, "deleted_id": item_id})
    finally:
        db.close()


@saas_api.route("/integrations/youtube/status", methods=["GET"])
@saas_api.route("/connections/youtube/status", methods=["GET"])
@require_auth
def youtube_status():
    user = g.current_user
    db = SessionLocal()
    try:
        row = (
            db.query(SocialAccount)
            .filter(SocialAccount.user_id == user.id, SocialAccount.provider == "youtube")
            .order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc())
            .first()
        )
        return jsonify(_serialize_youtube_connection(row))
    finally:
        db.close()


@saas_api.route("/integrations/youtube/start", methods=["POST"])
@saas_api.route("/connections/youtube/start", methods=["POST"])
@require_auth
def youtube_start():
    pw = _paywall_response_if_needed(authorizeAction(g.current_user, ACTION_ACCOUNT_CONNECT, {"provider": "youtube", "endpoint": "/api/integrations/youtube/start"}))
    if pw:
        return pw
    client_id = _google_client_id()
    client_secret = _google_client_secret()
    redirect_uri = _youtube_redirect_uri()
    if not client_id or not client_secret:
        return jsonify({"error": "Google OAuth не настроен. Укажите GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET."}), 400

    state = _store_oauth_state("youtube_connect", {"user_id": g.current_user.id})
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.readonly",
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent select_account",
        "state": state,
    }
    oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return jsonify({"oauth_url": oauth_url, "redirect_uri": redirect_uri})


@saas_api.route("/integrations/youtube/callback", methods=["GET"])
@saas_api.route("/connections/youtube/callback", methods=["GET"])
def youtube_callback():
    if request.args.get("error"):
        return redirect(_frontend_connections_url("youtube_error=oauth_denied"))

    state_token = (request.args.get("state") or "").strip()
    state_meta = _consume_oauth_state_meta(state_token, "youtube_connect")
    if not state_meta:
        return redirect(_frontend_connections_url("youtube_error=state_invalid"))

    user_id = int(state_meta.get("user_id") or 0)
    if not user_id:
        return redirect(_frontend_connections_url("youtube_error=state_invalid"))
    db_guard = SessionLocal()
    try:
        callback_user = db_guard.query(AppUser).filter_by(id=user_id).first()
    finally:
        db_guard.close()
    if not callback_user:
        return redirect(_frontend_connections_url("youtube_error=state_invalid"))
    authz = authorizeAction(callback_user, ACTION_ACCOUNT_CONNECT, {"provider": "youtube", "endpoint": "/api/integrations/youtube/callback"})
    if not authz.get("allowed", False):
        code = (authz.get("error_payload") or {}).get("error") or "PAYWALL_FEATURE"
        return redirect(_frontend_connections_url(f"youtube_error=paywall&message={quote(code)}"))

    code = (request.args.get("code") or "").strip()
    if not code:
        return redirect(_frontend_connections_url("youtube_error=missing_code"))
    return _finalize_youtube_oauth_connect(user_id, code, _youtube_redirect_uri())


@saas_api.route("/integrations/youtube/connect", methods=["POST"])
@saas_api.route("/connections/youtube/connect", methods=["POST"])
@require_auth
def youtube_connect():
    user = g.current_user
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_ACCOUNT_CONNECT, {"provider": "youtube", "endpoint": "/api/integrations/youtube/connect"}))
    if pw:
        return pw
    payload = request.get_json(silent=True) or {}
    channel_id = str(payload.get("channel_id") or "").strip()
    channel_name = str(payload.get("channel_name") or "").strip() or "YouTube канал"

    db = SessionLocal()
    try:
        row = (
            db.query(SocialAccount)
            .filter(SocialAccount.user_id == user.id, SocialAccount.provider == "youtube")
            .order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc())
            .first()
        )
        if not row:
            row = SocialAccount(user_id=user.id, provider="youtube")
            db.add(row)
            db.flush()

        row.page_id = channel_id or row.page_id or f"yt-{user.id}"
        row.page_name = channel_name
        row.page_picture_url = None
        row.ig_user_id = None
        row.ig_username = None
        row.status = "connected_ready"
        row.status_reason_code = None
        row.updated_at = datetime.utcnow()
        row.last_success_at = datetime.utcnow()
        db.commit()
        return jsonify(_serialize_youtube_connection(row))
    finally:
        db.close()


@saas_api.route("/integrations/youtube/disconnect", methods=["POST"])
@saas_api.route("/connections/youtube/disconnect", methods=["POST"])
@require_auth
def youtube_disconnect():
    user = g.current_user
    db = SessionLocal()
    try:
        row = (
            db.query(SocialAccount)
            .filter(SocialAccount.user_id == user.id, SocialAccount.provider == "youtube")
            .order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc())
            .first()
        )
        if not row:
            return jsonify(_serialize_youtube_connection(None))

        row.page_id = None
        row.page_name = None
        row.page_picture_url = None
        row.status = "not_connected"
        row.status_reason_code = "user_disconnected"
        row.updated_at = datetime.utcnow()
        db.commit()
        return jsonify(_serialize_youtube_connection(row))
    finally:
        db.close()


@saas_api.route("/integrations/meta/pages", methods=["GET"])
@saas_api.route("/connections/meta/pages", methods=["GET"])
@require_auth
def meta_pages():
    """
    Returns all Pages visible to the stored Meta user token for the current user.
    Used by UI to let user choose a Page explicitly.
    """
    user = g.current_user
    connection_id = (request.args.get("connection_id") or "").strip()

    db = SessionLocal()
    try:
        q = db.query(SocialAccount).filter_by(user_id=user.id, provider="meta")
        if connection_id:
            try:
                q = q.filter(SocialAccount.id == int(connection_id))
            except Exception:
                return jsonify({"error": "Invalid connection_id"}), 400
        row = q.order_by(SocialAccount.created_at.desc()).first()
        if not row or not row.token_encrypted:
            return jsonify({"error": "Meta connection not found. Connect Facebook first.", "status": "not_connected"}), 400

        try:
            access_token = decrypt_meta_token(row.token_encrypted)
        except Exception:
            return jsonify({"error": "Cannot decrypt token. Reconnect Facebook."}), 400

        if settings.MOCK_META:
            pages = [
                {
                    "page_id": f"mock-page-{user.id}-1",
                    "page_name": "Demo Business Page",
                    "page_picture_url": None,
                    "ig_user_id": f"mock-ig-{user.id}",
                    "ig_username": f"demo_ig_{user.id}",
                    "has_ig": True,
                    "already_connected": False,
                },
                {
                    "page_id": f"mock-page-{user.id}-2",
                    "page_name": "Demo No IG Page",
                    "page_picture_url": None,
                    "ig_user_id": None,
                    "ig_username": None,
                    "has_ig": False,
                    "already_connected": False,
                },
            ]
            return jsonify({"pages": pages})

        raw = list_pages(access_token)
        if raw.get("error"):
            status, reason = _meta_error_to_status(raw.get("error") or {})
            _apply_meta_status(row, status, reason)
            db.commit()
            return jsonify({"error": "Meta API error", "details": raw.get("error"), "status_reason_code": reason}), 400

        connected_page_ids = {
            str(r.page_id)
            for r in db.query(SocialAccount)
            .filter(SocialAccount.user_id == user.id, SocialAccount.provider == "meta")
            .all()
            if r.page_id and r.status != "disconnected"
        }

        pages = []
        for p in raw.get("data") or []:
            ig = p.get("instagram_business_account") or {}
            pic = (p.get("picture") or {}).get("data") or {}
            pages.append(
                {
                    "page_id": p.get("id"),
                    "page_name": p.get("name"),
                    "page_picture_url": pic.get("url"),
                    "ig_user_id": ig.get("id"),
                    "ig_username": ig.get("username"),
                    "has_ig": bool(ig.get("id")),
                    "already_connected": str(p.get("id")) in connected_page_ids,
                }
            )
        return jsonify({"pages": pages})
    finally:
        db.close()


@saas_api.route("/integrations/meta/select-page", methods=["POST"])
@saas_api.route("/connections/meta/select-page", methods=["POST"])
@require_auth
def meta_select_page():
    """
    Sets the selected Page/IG for the current user's Meta connection.
    Body: { connection_id?: number, page_id: string }
    """
    user = g.current_user
    payload = request.get_json(silent=True) or {}
    connection_id = payload.get("connection_id")
    page_id = (payload.get("page_id") or "").strip()
    if not page_id:
        return jsonify({"error": "page_id is required"}), 400

    db = SessionLocal()
    try:
        q = db.query(SocialAccount).filter_by(user_id=user.id, provider="meta")
        if connection_id is not None:
            try:
                q = q.filter(SocialAccount.id == int(connection_id))
            except Exception:
                return jsonify({"error": "Invalid connection_id"}), 400
        row = q.order_by(SocialAccount.created_at.desc()).first()
        if not row or not row.token_encrypted:
            return jsonify({"error": "Meta connection not found. Connect Facebook first.", "status": "not_connected"}), 400

        if settings.MOCK_META:
            row.page_id = page_id
            row.page_name = "Mock Selected Page"
            row.page_picture_url = None
            row.ig_user_id = f"mock-ig-{user.id}"
            row.ig_username = f"demo_ig_{user.id}"
            _apply_meta_status(row, "connected_ready")
            db.commit()
            return jsonify(_serialize_connection(row))

        access_token = decrypt_meta_token(row.token_encrypted)
        raw = list_pages(access_token)
        if raw.get("error"):
            status, reason = _meta_error_to_status(raw.get("error") or {})
            _apply_meta_status(row, status, reason)
            db.commit()
            return jsonify({"error": "Meta API error", "details": raw.get("error"), "status_reason_code": reason}), 400

        selected = next((p for p in (raw.get("data") or []) if str(p.get("id")) == page_id), None)
        if not selected:
            _apply_meta_status(row, "connected_need_page", "no_pages")
            db.commit()
            return jsonify({"error": "Page not found for this token. Reconnect and grant Pages access.", "status_reason_code": "no_pages"}), 404

        ig = selected.get("instagram_business_account") or {}
        pic = (selected.get("picture") or {}).get("data") or {}
        row.page_id = selected.get("id")
        row.page_name = selected.get("name")
        row.page_picture_url = pic.get("url")
        row.ig_user_id = ig.get("id")
        row.ig_username = ig.get("username")
        if row.page_id and row.ig_user_id:
            _apply_meta_status(row, "connected_ready")
        elif row.page_id and not row.ig_user_id:
            _apply_meta_status(row, "connected_need_page", "ig_not_linked")
        else:
            _apply_meta_status(row, "connected_need_page", "no_pages")
        db.commit()

        return jsonify(_serialize_connection(row))
    finally:
        db.close()


@saas_api.route("/connections/meta/add-page", methods=["POST"])
@require_auth
def meta_add_page():
    """
    Add a new Meta connection row for a different Facebook Page using the same stored token.
    Body: { source_connection_id: number, page_id: string }
    """
    user = g.current_user
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_ACCOUNT_CONNECT, {"provider": "meta", "endpoint": "/api/connections/meta/add-page"}))
    if pw:
        return pw
    payload = request.get_json(silent=True) or {}
    try:
        source_id = int(payload.get("source_connection_id"))
    except Exception:
        return jsonify({"error": "source_connection_id is required"}), 400
    page_id = (payload.get("page_id") or "").strip()
    if not page_id:
        return jsonify({"error": "page_id is required"}), 400

    db = SessionLocal()
    try:
        source = db.query(SocialAccount).filter_by(id=source_id).first()
        if not source or source.provider != "meta":
            return jsonify({"error": "Source connection not found"}), 404
        if user.role != "admin" and source.user_id != user.id:
            return jsonify({"error": "Недостаточно прав"}), 403
        if not source.token_encrypted:
            return jsonify({"error": "No token found. Reconnect Facebook."}), 400

        # Avoid duplicates: if already connected, return existing row.
        existing = (
            db.query(SocialAccount)
            .filter(
                SocialAccount.user_id == source.user_id,
                SocialAccount.provider == "meta",
                SocialAccount.page_id == page_id,
                SocialAccount.status.in_(["connected_ready", "connected_need_page", "permissions_missing", "token_expired"]),
            )
            .first()
        )
        if existing:
            return jsonify(
                {
                    **_serialize_connection(existing),
                }
            )

        access_token = decrypt_meta_token(source.token_encrypted)
        raw = list_pages(access_token)
        if raw.get("error"):
            return jsonify({"error": "Meta API error", "details": raw.get("error")}), 400
        selected = next((p for p in (raw.get("data") or []) if str(p.get("id")) == page_id), None)
        if not selected:
            return jsonify({"error": "Page not found for this token. Reconnect and grant Pages access."}), 404

        ig = selected.get("instagram_business_account") or {}
        pic = (selected.get("picture") or {}).get("data") or {}
        row = SocialAccount(user_id=source.user_id, provider="meta")
        row.page_id = selected.get("id")
        row.page_name = selected.get("name")
        row.page_picture_url = pic.get("url")
        row.ig_user_id = ig.get("id")
        row.ig_username = ig.get("username")
        row.token_encrypted = source.token_encrypted  # reuse same token
        if row.page_id and row.ig_user_id:
            _apply_meta_status(row, "connected_ready")
        elif row.page_id and not row.ig_user_id:
            _apply_meta_status(row, "connected_need_page", "ig_not_linked")
        else:
            _apply_meta_status(row, "connected_need_page", "no_pages")
        db.add(row)
        db.commit()

        return jsonify(_serialize_connection(row))
    finally:
        db.close()


@saas_api.route("/connections/meta/mock-connect", methods=["POST"])
@require_auth
def mock_connect():
    if not settings.USE_MOCK_PROVIDERS:
        return jsonify({"error": "USE_MOCK_PROVIDERS=false. Mock РїРѕРґРєР»СЋС‡РµРЅРёРµ РѕС‚РєР»СЋС‡РµРЅРѕ."}), 400

    user = g.current_user
    pw = _paywall_response_if_needed(authorizeAction(user, ACTION_ACCOUNT_CONNECT, {"provider": "meta", "endpoint": "/api/connections/meta/mock-connect"}))
    if pw:
        return pw
    db = SessionLocal()
    try:
        row = db.query(SocialAccount).filter_by(user_id=user.id, provider="meta").first()
        if not row:
            row = SocialAccount(user_id=user.id, provider="meta")
            db.add(row)

        row.page_id = f"page-{user.id}"
        row.page_name = "Demo Facebook Page"
        row.page_picture_url = None
        row.ig_user_id = f"ig-{user.id}"
        row.ig_username = f"demo_ig_{user.id}"
        row.token_encrypted = encrypt_meta_token("mock_token")
        _apply_meta_status(row, "connected_ready")
        db.commit()
        return jsonify(_serialize_connection(row))
    finally:
        db.close()


@saas_api.route("/connections/<int:connection_id>/disconnect", methods=["POST"])
@require_auth
def disconnect_connection(connection_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        row = db.query(SocialAccount).filter_by(id=connection_id).first()
        if not row:
            return jsonify({"error": "РџРѕРґРєР»СЋС‡РµРЅРёРµ РЅРµ РЅР°Р№РґРµРЅРѕ"}), 404
        if user.role != "admin" and row.user_id != user.id:
            return jsonify({"error": "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ"}), 403

        row.token_encrypted = None
        row.token_expires_at = None
        row.page_id = None
        row.page_name = None
        row.page_picture_url = None
        row.ig_user_id = None
        row.ig_username = None
        _apply_meta_status(row, "not_connected", "user_disconnected")
        db.commit()
        return jsonify(_serialize_connection(row))
    finally:
        db.close()


@saas_api.route("/connections/<int:connection_id>/refresh-token", methods=["POST"])
@require_auth
def refresh_connection_token(connection_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        row = db.query(SocialAccount).filter_by(id=connection_id).first()
        if not row:
            return jsonify({"error": "РџРѕРґРєР»СЋС‡РµРЅРёРµ РЅРµ РЅР°Р№РґРµРЅРѕ"}), 404
        if user.role != "admin" and row.user_id != user.id:
            return jsonify({"error": "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ"}), 403

        if row.provider != "meta":
            _apply_meta_status(row, "error", "unsupported_provider")
            db.commit()
            return jsonify(_serialize_connection(row)), 400

        if not row.token_encrypted:
            _apply_meta_status(row, "not_connected", "no_token")
            db.commit()
            return jsonify(_serialize_connection(row))

        try:
            access_token = decrypt_meta_token(row.token_encrypted)
            raw = list_pages(access_token)
            if raw.get("error"):
                status, reason = _meta_error_to_status(raw.get("error") or {})
                _apply_meta_status(row, status, reason)
            else:
                pages = raw.get("data") or []
                if not pages:
                    _apply_meta_status(row, "connected_need_page", "no_pages")
                else:
                    selected = None
                    if row.page_id:
                        selected = next((p for p in pages if str(p.get("id")) == str(row.page_id)), None)
                    if not selected:
                        selected = next((p for p in pages if p.get("instagram_business_account")), pages[0])
                    ig = selected.get("instagram_business_account") or {}
                    pic = (selected.get("picture") or {}).get("data") or {}
                    row.page_id = selected.get("id")
                    row.page_name = selected.get("name")
                    row.page_picture_url = pic.get("url")
                    row.ig_user_id = ig.get("id")
                    row.ig_username = ig.get("username")
                    if row.page_id and row.ig_user_id:
                        _apply_meta_status(row, "connected_ready")
                    else:
                        _apply_meta_status(row, "connected_need_page", "ig_not_linked")
        except Exception:
            _apply_meta_status(row, "error", "refresh_failed")

        db.commit()
        return jsonify(_serialize_connection(row))
    finally:
        db.close()


@saas_api.route("/connections/<int:connection_id>/test-publish", methods=["POST"])
@require_auth
def test_publish_connection(connection_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        row = db.query(SocialAccount).filter_by(id=connection_id).first()
        if not row:
            return jsonify({"error": "РџРѕРґРєР»СЋС‡РµРЅРёРµ РЅРµ РЅР°Р№РґРµРЅРѕ"}), 404
        if user.role != "admin" and row.user_id != user.id:
            return jsonify({"error": "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ"}), 403

        status = _normalize_connection_status(row.status)
        if status != "connected_ready":
            return jsonify(
                {
                    "error": "Подключение не готово к публикации",
                    "status": status,
                    "status_reason_code": row.status_reason_code,
                }
            ), 400
        if not row.page_id:
            _apply_meta_status(row, "connected_need_page", "no_pages")
            db.commit()
            return jsonify({"error": "Выберите Facebook Page для публикации", "status_reason_code": "no_pages"}), 400

        if not row.token_encrypted:
            _apply_meta_status(row, "token_expired", "access_token_invalid")
            db.commit()
            return jsonify({"error": "Токен подключения не найден. Переподключите Facebook.", "status_reason_code": "access_token_invalid"}), 400

        if settings.USE_MOCK_PROVIDERS:
            _apply_meta_status(row, "connected_ready")
            db.commit()
            return jsonify(
                {
                    "result": "ok",
                    "mode": "mock",
                    "message": "Mock тест публикации пройден",
                    "status": row.status,
                    "status_reason_code": row.status_reason_code,
                    "post_id": f"mock_meta_test_{row.id}_{int(time.time())}",
                }
            )

        try:
            access_token = decrypt_meta_token(row.token_encrypted)
        except Exception:
            _apply_meta_status(row, "token_expired", "access_token_invalid")
            db.commit()
            return jsonify({"error": "Не удалось расшифровать токен. Переподключите Facebook.", "status_reason_code": "access_token_invalid"}), 400

        page_access_token = _resolve_page_access_token(access_token, row.page_id)
        if not page_access_token:
            _apply_meta_status(row, "permissions_missing", "page_token_missing")
            db.commit()
            return jsonify(
                {
                    "error": "Не удалось получить page access token. Переподключите Facebook и подтвердите права для страницы.",
                    "status": row.status,
                    "status_reason_code": row.status_reason_code,
                }
            ), 400

        caption = (
            "AutoSocial GPT: тестовая публикация\n"
            f"Connection #{row.id}, {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        requested = (request.get_json(silent=True) or {}).get("platform")
        requested = (requested or "").strip().lower()

        # If IG is linked, test Instagram by default (or when requested explicitly).
        should_test_instagram = bool(row.ig_user_id) and requested in {"", "instagram"}
        if should_test_instagram:
            ig_image_url = (
                (request.get_json(silent=True) or {}).get("image_url")
                or build_semantic_fallback_image_url(
                    topic="Тест публикации для соцсетей",
                    category="business",
                    tone="friendly",
                    language="ru",
                )
            ).strip()
            # Instagram publish should use USER access token.
            result = publish_to_instagram(row.ig_user_id, access_token, ig_image_url, caption)
            meta_error = result.get("error") if isinstance(result, dict) else None
            post_id = (result or {}).get("id")
            if meta_error or not post_id:
                status_from_error, reason = _meta_error_to_status(meta_error or {})
                _apply_meta_status(row, status_from_error, reason)
                db.commit()
                meta_text = _extract_meta_error_text(result)
                full_error = "Ошибка тестовой публикации в Instagram"
                if meta_text:
                    full_error = f"{full_error}: {meta_text}"
                return jsonify(
                    {
                        "error": full_error,
                        "details": result,
                        "status": row.status,
                        "status_reason_code": row.status_reason_code,
                    }
                ), 400

            _apply_meta_status(row, "connected_ready")
            db.commit()
            return jsonify(
                {
                    "result": "ok",
                    "mode": "real",
                    "platform": "instagram",
                    "message": "Тестовая публикация создана в Instagram",
                    "status": row.status,
                    "status_reason_code": row.status_reason_code,
                    "post_id": str(post_id),
                }
            )

        # Fallback Facebook test publish.
        result = publish_to_facebook(row.page_id, page_access_token, None, caption)
        meta_error = result.get("error") if isinstance(result, dict) else None
        post_id = (result or {}).get("post_id") or (result or {}).get("id")
        if meta_error or not post_id:
            status_from_error, reason = _meta_error_to_status(meta_error or {})
            _apply_meta_status(row, status_from_error, reason)
            db.commit()
            meta_text = _extract_meta_error_text(result)
            full_error = "Ошибка тестовой публикации в Facebook"
            if meta_text:
                full_error = f"{full_error}: {meta_text}"
            return jsonify(
                {
                    "error": full_error,
                    "details": result,
                    "status": row.status,
                    "status_reason_code": row.status_reason_code,
                }
            ), 400

        _apply_meta_status(row, "connected_ready")
        db.commit()
        return jsonify(
            {
                "result": "ok",
                "mode": "real",
                "platform": "facebook",
                "message": "Тестовая публикация создана в Facebook",
                "status": row.status,
                "status_reason_code": row.status_reason_code,
                "post_id": str(post_id),
            }
        )
    finally:
        db.close()


def _latest_user_meta_connection(db, user_id: int):
    return (
        db.query(SocialAccount)
        .filter(SocialAccount.user_id == user_id, SocialAccount.provider == "meta")
        .order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc())
        .first()
    )


@saas_api.route("/integrations/meta/disconnect", methods=["POST"])
@require_auth
def integration_meta_disconnect():
    db = SessionLocal()
    try:
        row = _latest_user_meta_connection(db, g.current_user.id)
        if not row:
            return jsonify({"status": "not_connected", "status_reason_code": "no_connection"})
        row.token_encrypted = None
        row.token_expires_at = None
        row.page_id = None
        row.page_name = None
        row.page_picture_url = None
        row.ig_user_id = None
        row.ig_username = None
        _apply_meta_status(row, "not_connected", "user_disconnected")
        db.commit()
        return jsonify(_serialize_connection(row))
    finally:
        db.close()


@saas_api.route("/integrations/meta/refresh", methods=["POST"])
@require_auth
def integration_meta_refresh():
    db = SessionLocal()
    try:
        row = _latest_user_meta_connection(db, g.current_user.id)
        if not row:
            return jsonify({"status": "not_connected", "status_reason_code": "no_connection"})
        return refresh_connection_token(row.id)
    finally:
        db.close()


@saas_api.route("/integrations/meta/test-post", methods=["POST"])
@require_auth
def integration_meta_test_post():
    db = SessionLocal()
    try:
        row = _latest_user_meta_connection(db, g.current_user.id)
        if not row:
            return jsonify({"error": "Подключение не найдено", "status": "not_connected"}), 400
        if settings.MOCK_META:
            _apply_meta_status(row, "connected_ready")
            db.commit()
            return jsonify(
                {
                    "result": "ok",
                    "message": "Mock test publish success",
                    "status": row.status,
                    "status_reason_code": row.status_reason_code,
                    "post_id": f"mock_meta_test_{row.id}_{int(time.time())}",
                }
            )
        return test_publish_connection(row.id)
    finally:
        db.close()


@saas_api.route("/billing/summary", methods=["GET"])
@require_auth
def billing_summary():
    user = _current_user_refetched()
    return jsonify(get_billing_summary(user))


@saas_api.route("/billing/entitlements", methods=["GET"])
@require_auth
def billing_entitlements():
    user = _current_user_refetched()
    return jsonify(getEntitlementsPayload(user))


@saas_api.route("/billing/checkout/subscription", methods=["POST"])
@require_auth
def billing_checkout_subscription():
    data = request.get_json(silent=True) or {}
    plan_name = normalize_plan_code((data.get("plan") or "").strip().lower())
    if plan_name not in {"starter", "growth", "agency"}:
        return jsonify({"error": "Выберите тариф starter, growth или agency"}), 400
    if not get_plan_spec(plan_name).payment_available:
        return jsonify({"error": "Оплата этого тарифа пока недоступна. Тариф появится в оплате позже."}), 409

    user = _current_user_refetched()
    try:
        checkout_url = create_subscription_checkout(user, plan_name)
        return jsonify({"checkout_url": checkout_url})
    except Exception as exc:
        return jsonify({"error": f"Stripe checkout error: {str(exc)}"}), 400


@saas_api.route("/billing/checkout/credits", methods=["POST"])
@require_auth
def billing_checkout_credits():
    data = request.get_json(silent=True) or {}
    pack_code = (data.get("pack") or "").strip().lower()
    if pack_code not in CREDIT_PACKS:
        return jsonify({"error": "Р’С‹Р±РµСЂРёС‚Рµ pack_s, pack_m РёР»Рё pack_l"}), 400

    user = _current_user_refetched()
    try:
        checkout_url = create_credit_pack_checkout(user, pack_code)
        return jsonify({"checkout_url": checkout_url})
    except Exception as exc:
        return jsonify({"error": f"Stripe checkout error: {str(exc)}"}), 400


@saas_api.route("/billing/portal", methods=["POST"])
@require_auth
def billing_portal():
    user = _current_user_refetched()
    try:
        url = create_portal_link(user)
        return jsonify({"portal_url": url})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@saas_api.route("/blog/posts", methods=["GET"])
def blog_posts_public():
    rows = list_blog_posts(limit=100)
    return jsonify(
        [
            {
                "id": r.id,
                "title": r.title,
                "slug": r.slug,
                "content": r.content,
                "meta_title": r.meta_title,
                "meta_description": r.meta_description,
                "keywords": r.keywords,
                "published_at": r.published_at.isoformat() if r.published_at else None,
            }
            for r in rows
        ]
    )


@saas_api.route("/admin/blog/generate", methods=["POST"])
@require_auth
@require_role("admin")
def admin_blog_generate():
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip() or None
    language = (data.get("language") or "ru").strip()
    post = create_daily_blog_post(topic=topic, language=language, author_user_id=g.current_user.id)
    return jsonify({"id": post.id, "title": post.title, "slug": post.slug, "published_at": post.published_at.isoformat()})


@saas_api.route("/billing/upgrade-demo", methods=["POST"])
@require_auth
def upgrade_demo_only_for_mock():
    if not settings.USE_MOCK_PROVIDERS:
        return jsonify({"error": "Р”РµРјРѕ-Р°РїРіСЂРµР№Рґ РѕС‚РєР»СЋС‡РµРЅ"}), 400

    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=g.current_user.id).first()
        user.plan = "growth"
        plan = db.query(Plan).filter_by(name="growth").first()
        user.plan_id = plan.id if plan else user.plan_id
        user.billing_status = "active"
        db.commit()
    finally:
        db.close()

    return jsonify({"plan": "growth"})


@saas_api.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        event = verify_and_construct_event(payload, sig_header)
        process_stripe_event(event)
        return jsonify({"received": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@saas_api.route("/settings/profile", methods=["PATCH"])
@require_auth
def settings_profile():
    user = g.current_user
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "Email РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РїСѓСЃС‚С‹Рј"}), 400

    db = SessionLocal()
    try:
        clash = db.query(AppUser).filter(AppUser.email == email, AppUser.id != user.id).first()
        if clash:
            return jsonify({"error": "Р­С‚РѕС‚ email СѓР¶Рµ Р·Р°РЅСЏС‚"}), 409

        db_user = db.query(AppUser).filter_by(id=user.id).first()
        db_user.email = email
        db.commit()
        return jsonify({"email": db_user.email})
    finally:
        db.close()


@saas_api.route("/settings/password", methods=["POST"])
@require_auth
def settings_password():
    user = g.current_user
    data = request.get_json(silent=True) or {}
    current_password = (data.get("current_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()

    if len(new_password) < 8:
        return jsonify({"error": "РќРѕРІС‹Р№ РїР°СЂРѕР»СЊ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РЅРµ РєРѕСЂРѕС‡Рµ 8 СЃРёРјРІРѕР»РѕРІ"}), 400

    db = SessionLocal()
    try:
        db_user = db.query(AppUser).filter_by(id=user.id).first()
        if not verify_password(current_password, db_user.password_hash):
            return jsonify({"error": "РўРµРєСѓС‰РёР№ РїР°СЂРѕР»СЊ РІРІРµРґРµРЅ РЅРµРІРµСЂРЅРѕ"}), 400

        db_user.password_hash = hash_password(new_password)
        db.commit()
        return jsonify({"message": "РџР°СЂРѕР»СЊ РѕР±РЅРѕРІР»РµРЅ"})
    finally:
        db.close()


@saas_api.route("/admin/users", methods=["GET"])
@require_auth
@require_role("admin")
def admin_users():
    db = SessionLocal()
    try:
        users = db.query(AppUser).order_by(AppUser.created_at.desc()).all()
        return jsonify(
            [
                {
                    "id": u.id,
                    "email": u.email,
                    "role": u.role,
                    "plan": normalize_plan_code(u.plan),
                    "credits_left": u.credits_left,
                    "posts_used_month": u.posts_used_month,
                    "billing_status": u.billing_status,
                    "created_at": u.created_at.isoformat(),
                    "last_login": u.last_login.isoformat() if u.last_login else None,
                }
                for u in users
            ]
        )
    finally:
        db.close()


@saas_api.route("/admin/users/<int:user_id>/plan", methods=["PATCH"])
@require_auth
@require_role("admin")
def admin_update_plan(user_id: int):
    data = request.get_json(silent=True) or {}
    new_plan = normalize_plan_code((data.get("plan") or "").strip().lower())
    if new_plan not in {"free", "starter", "growth", "agency"}:
        return jsonify({"error": "Тариф должен быть free/starter/growth/agency"}), 400

    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(id=user_id).first()
        plan = db.query(Plan).filter_by(name=new_plan).first()
        if not user:
            return jsonify({"error": "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ"}), 404
        if not plan:
            return jsonify({"error": "РџР»Р°РЅ РЅРµ РЅР°Р№РґРµРЅ"}), 404

        user.plan = plan.name
        user.plan_id = plan.id
        db.commit()
        now = datetime.utcnow()
        if plan.name == "free":
            sync_subscription_state(
                user.id,
                plan="trial",
                status="trialing",
                current_period_start=user.created_at or now,
                current_period_end=(user.created_at or now) + timedelta(days=7),
            )
        else:
            sync_subscription_state(
                user.id,
                plan=plan.name,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        log_event("plan_changed", actor_user_id=g.current_user.id, context=f"target={user_id};plan={new_plan}")
        return jsonify({"id": user.id, "plan": user.plan})
    finally:
        db.close()


@saas_api.route("/admin/users/<int:user_id>/credits", methods=["PATCH"])
@require_auth
@require_role("admin")
def admin_adjust_credits(user_id: int):
    from saas_services import add_credits

    data = request.get_json(silent=True) or {}
    delta = int(data.get("delta") or 0)
    if delta == 0:
        return jsonify({"error": "delta РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РЅРµ 0"}), 400

    try:
        add_credits(user_id=user_id, delta=delta, ledger_type="admin_adjust", meta={"actor": g.current_user.id})
        return jsonify({"ok": True, "delta": delta})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@saas_api.route("/admin/projects", methods=["GET"])
@require_auth
@require_role("admin")
def admin_projects():
    db = SessionLocal()
    try:
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
        return jsonify([{"id": p.id, "user_id": p.user_id, "name": p.name, "created_at": p.created_at.isoformat()} for p in projects])
    finally:
        db.close()


@saas_api.route("/admin/content", methods=["GET"])
@require_auth
@require_role("admin")
def admin_content():
    db = SessionLocal()
    try:
        posts = db.query(Post).order_by(Post.created_at.desc()).limit(500).all()
        return jsonify(
            [
                {
                    "id": p.id,
                    "project_id": p.project_id,
                    "user_id": p.user_id,
                    "topic": p.topic,
                    "status": p.status,
                    "tokens_total": p.tokens_total,
                    "credits_charged": p.credits_charged,
                    "created_at": p.created_at.isoformat(),
                }
                for p in posts
            ]
        )
    finally:
        db.close()


@saas_api.route("/admin/content-strategies", methods=["GET"])
@require_auth
@require_role("admin")
def admin_content_strategies():
    db = SessionLocal()
    try:
        rows = db.query(ContentPlan).order_by(ContentPlan.created_at.desc()).limit(500).all()
        return jsonify(
            [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "project_id": r.project_id,
                    "business_type": r.business_type,
                    "goal": r.goal,
                    "language": r.language,
                    "topic": r.topic,
                    "status": r.status,
                    "scheduled_at": r.scheduled_at.isoformat(),
                    "post_id": r.post_id,
                }
                for r in rows
            ]
        )
    finally:
        db.close()


@saas_api.route("/admin/blog", methods=["GET"])
@require_auth
@require_role("admin")
def admin_blog_list():
    rows = list_blog_posts(limit=300)
    return jsonify(
        [
            {
                "id": r.id,
                "title": r.title,
                "slug": r.slug,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "status": r.status,
            }
            for r in rows
        ]
    )


@saas_api.route("/admin/logs", methods=["GET"])
@require_auth
@require_role("admin")
def admin_logs():
    db = SessionLocal()
    try:
        rows = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(500).all()
        return jsonify(
            [
                {
                    "id": r.id,
                    "actor_user_id": r.actor_user_id,
                    "level": r.level,
                    "message": r.message,
                    "context": r.context,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        )
    finally:
        db.close()


@saas_api.route("/admin/payments", methods=["GET"])
@require_auth
@require_role("admin")
def admin_payments():
    db = SessionLocal()
    try:
        events = db.query(PaymentEvent).order_by(PaymentEvent.created_at.desc()).limit(500).all()
        return jsonify(
            [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "amount_eur": e.amount_eur,
                    "status": e.status,
                    "customer_id": e.customer_id,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ]
        )
    finally:
        db.close()


@saas_api.route("/admin/revenue", methods=["GET"])
@require_auth
@require_role("admin")
def admin_revenue():
    return jsonify(get_revenue_metrics())


@saas_api.route("/admin/abuse", methods=["GET"])
@require_auth
@require_role("admin")
def admin_abuse():
    from saas_models import AuditLog

    db = SessionLocal()
    try:
        rows = db.query(AuditLog).filter(AuditLog.action == "abnormal_usage").order_by(AuditLog.created_at.desc()).limit(200).all()
        return jsonify(
            [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "action": r.action,
                    "meta_json": r.meta_json,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        )
    finally:
        db.close()


@saas_api.route("/admin/niche-hooks", methods=["GET"])
@require_auth
@require_role("admin")
def admin_niche_hooks():
    db = SessionLocal()
    try:
        rows = db.query(NicheHook).order_by(NicheHook.niche.asc(), NicheHook.id.asc()).all()
        return jsonify([{"id": r.id, "niche": r.niche, "hook": r.hook} for r in rows])
    finally:
        db.close()







