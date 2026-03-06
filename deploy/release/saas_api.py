import json
import os
import random
import re
import smtplib
import ssl
import hashlib
import hmac
from pathlib import Path
from urllib.parse import quote
from urllib.parse import urlsplit
from email.utils import parseaddr
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from email.message import EmailMessage

import requests
from flask import Blueprint, current_app, g, jsonify, redirect, request, send_from_directory

from database import SessionLocal
from facebook_api import (
    exchange_code_for_token,
    get_page_and_ig_id,
    list_pages,
    publish_to_facebook,
    publish_to_instagram,
)
from gpt_generator import build_semantic_fallback_image_url, generate_structured_text_with_usage
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
    Project,
    SocialAccount,
    SystemLog,
    TopicSuggestion,
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
from stripe_service import (
    create_credit_pack_checkout,
    create_portal_link,
    create_subscription_checkout,
    process_stripe_event,
    verify_and_construct_event,
)

saas_api = Blueprint("saas_api", __name__, url_prefix="/api")
OAUTH_STATES = {}
OAUTH_STATE_TTL_SECONDS = 600
MEDIA_DIR = Path(__file__).resolve().with_name("generated_media")
MEDIA_DIR.mkdir(exist_ok=True)
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
    envelope_from = (smtp_user or parseaddr(smtp_from)[1] or smtp_from).strip()
    if smtp_use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=10) as smtp:
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(message, from_addr=envelope_from)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            if smtp_use_starttls:
                smtp.starttls(context=context)
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(message, from_addr=envelope_from)

    log_event("auth_code_email_sent", context=f"flow={flow};email={email};ip={ip_addr}")
    return True


def _current_user_refetched() -> AppUser:
    db = SessionLocal()
    try:
        return db.query(AppUser).filter_by(id=g.current_user.id).first()
    finally:
        db.close()


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
    safe_name = os.path.basename((filename or '').strip())
    if not safe_name:
        return jsonify({'error': 'file_not_found'}), 404
    full_path = MEDIA_DIR / safe_name
    if not full_path.exists():
        return jsonify({'error': 'file_not_found'}), 404
    return send_from_directory(MEDIA_DIR, safe_name)


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
        or settings.GOOGLE_REDIRECT_URI
        or os.getenv("GOOGLE_REDIRECT_URI")
        or ""
    ).strip()
    if env:
        return env
    # By default reuse Google login callback to avoid redirect_uri_mismatch
    # when only one Google OAuth callback URI is configured in Cloud Console.
    return _google_redirect_uri()


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
    payload["message"] = "Код отправлен на email. Если письмо не пришло, используйте код на экране."
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
    return {"token": token, "user": {"id": user_id, "email": user_email, "role": user_role, "plan": user_plan}}, 200


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
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(email=email).first()
        if user and user.role == "admin" and verify_password(password, user.password_hash):
            seed_plans()
            ensure_user_plan_and_credits(user.id)
            get_or_create_default_project(user.id)
            token = create_token(user.id)
            log_event("admin_login", actor_user_id=user.id, context=f"email={user.email};ip={_ip()};via=password_direct")
            return jsonify({"token": token, "user": {"id": user.id, "email": user.email, "role": user.role, "plan": user.plan}}), 200
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
        return redirect(_frontend_connections_url("youtube_error=youtube_api_failed"))

    yt_data = yt_resp.json() if yt_resp.content else {}
    items = yt_data.get("items") if isinstance(yt_data, dict) else None
    if not isinstance(items, list) or not items:
        return redirect(_frontend_connections_url("youtube_error=no_channel"))

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
    return jsonify(
        {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "plan": user.plan,
            "billing": get_billing_summary(user),
        }
    )


@saas_api.route("/plans", methods=["GET"])
def plans():
    seed_plans()
    db = SessionLocal()
    try:
        rows = db.query(Plan).order_by(Plan.price_eur_month.asc()).all()
        return jsonify(
            [
                {
                    "name": p.name,
                    "price_eur_month": p.price_eur_month,
                    "monthly_credits": p.monthly_credits,
                    "max_projects": p.max_projects,
                    "max_posts_month": p.max_posts_month,
                    "max_daily_posts": p.max_daily_posts,
                    "can_schedule": p.can_schedule,
                    "can_autopublish": p.can_autopublish,
                    "templates_enabled": p.templates_enabled,
                    "team_seats": p.team_seats,
                }
                for p in rows
            ]
        )
    finally:
        db.close()


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

    if user.role != "admin":
        usage = check_project_limit(user)
        if usage["used"] >= usage["limit"]:
            return jsonify({"error": "Р”РѕСЃС‚РёРіРЅСѓС‚ Р»РёРјРёС‚ РїСЂРѕРµРєС‚РѕРІ. РћР±РЅРѕРІРёС‚Рµ С‚Р°СЂРёС„."}), 429

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
        billing = get_billing_summary(user)
        if not billing["limits"].get("can_schedule"):
            return jsonify({"error": "Планирование доступно только на платных тарифах"}), 403

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


@saas_api.route("/youtube/generate-video", methods=["POST"])
@require_auth
def youtube_generate_video():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}

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
    return jsonify(result)


@saas_api.route("/youtube/generate-post", methods=["POST"])
@require_auth
def youtube_generate_post():
    user = _current_user_refetched()
    data = request.get_json(silent=True) or {}
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

    billing = get_billing_summary(user)
    if not billing["limits"]["can_schedule"]:
        return jsonify({"error": "РџР»Р°РЅРёСЂРѕРІР°РЅРёРµ РґРѕСЃС‚СѓРїРЅРѕ С‚РѕР»СЊРєРѕ РЅР° РїР»Р°С‚РЅС‹С… С‚Р°СЂРёС„Р°С…"}), 403

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
            status = _normalize_connection_status(row.status)
            # Hide empty disconnected shells from UI after explicit disconnect.
            if status in {"not_connected", "disconnected"} and not row.token_encrypted and not row.page_id and not row.ig_user_id:
                continue
            rows.append(row)
        return jsonify([_serialize_connection(row) for row in rows])
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

    code = (request.args.get("code") or "").strip()
    if not code:
        return redirect(_frontend_connections_url("youtube_error=missing_code"))
    return _finalize_youtube_oauth_connect(user_id, code, _youtube_redirect_uri())


@saas_api.route("/integrations/youtube/connect", methods=["POST"])
@saas_api.route("/connections/youtube/connect", methods=["POST"])
@require_auth
def youtube_connect():
    user = g.current_user
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


@saas_api.route("/billing/checkout/subscription", methods=["POST"])
@require_auth
def billing_checkout_subscription():
    data = request.get_json(silent=True) or {}
    plan_name = (data.get("plan") or "").strip().lower()
    if plan_name not in {"starter", "growth", "agency"}:
        return jsonify({"error": "Выберите валидный тариф: starter/growth/agency"}), 400

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
                    "plan": u.plan,
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
    new_plan = (data.get("plan") or "").strip().lower()
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







