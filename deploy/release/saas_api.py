import json
import os
from urllib.parse import quote
from urllib.parse import urlsplit
import secrets
import time
from datetime import datetime
from urllib.parse import urlencode

import requests
from flask import Blueprint, g, jsonify, redirect, request

from database import SessionLocal
from facebook_api import (
    exchange_code_for_token,
    get_page_and_ig_id,
    list_pages,
    publish_to_facebook,
    publish_to_instagram,
)
from saas_auth import create_token, hash_password, require_auth, require_role, verify_password
from saas_models import (
    AppUser,
    BlogPost,
    ContentPlan,
    NicheHook,
    PaymentEvent,
    Plan,
    PlatformRule,
    Post,
    Project,
    SocialAccount,
    SystemLog,
)
from saas_services import (
    CREDIT_PACKS,
    can_access_project,
    check_project_limit,
    create_post_and_charge,
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


def _ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "")


def _current_user_refetched() -> AppUser:
    db = SessionLocal()
    try:
        return db.query(AppUser).filter_by(id=g.current_user.id).first()
    finally:
        db.close()


def _frontend_base_url() -> str:
    return (settings.FRONTEND_BASE_URL or os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")).rstrip("/")


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


def _store_oauth_state(provider: str) -> str:
    now = time.time()
    expired = [k for k, v in OAUTH_STATES.items() if v["exp"] < now]
    for key in expired:
        OAUTH_STATES.pop(key, None)

    state = secrets.token_urlsafe(24)
    OAUTH_STATES[state] = {"provider": provider, "exp": now + OAUTH_STATE_TTL_SECONDS}
    return state


def _consume_oauth_state(state: str, provider: str) -> bool:
    if not state:
        return False
    meta = OAUTH_STATES.pop(state, None)
    if not meta:
        return False
    if meta["provider"] != provider:
        return False
    return meta["exp"] >= time.time()


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


@saas_api.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Введите email и пароль"}), 400
    if len(password) < 8:
        return jsonify({"error": "Пароль должен быть не короче 8 символов"}), 400

    db = SessionLocal()
    try:
        if db.query(AppUser).filter_by(email=email).first():
            return jsonify({"error": "Пользователь с таким email уже существует"}), 409

        user = AppUser(email=email, password_hash=hash_password(password), role="user", plan="free")
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    seed_plans()
    ensure_user_plan_and_credits(user.id)
    get_or_create_default_project(user.id)

    token = create_token(user.id)
    log_event("user_registered", actor_user_id=user.id, context=f"email={email};ip={_ip()}")
    return jsonify({"token": token, "user": {"id": user.id, "email": user.email, "role": user.role, "plan": user.plan}})


@saas_api.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    user_id = None
    user_role = None
    user_plan = None
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter_by(email=email).first()
        if not user or not verify_password(password, user.password_hash):
            return jsonify({"error": "Неверный email или пароль"}), 401
        user.last_login = datetime.utcnow()
        user_id = user.id
        user_role = user.role
        user_plan = user.plan
        db.commit()
    finally:
        db.close()

    if user_id is None:
        return jsonify({"error": "Пользователь не найден"}), 404

    seed_plans()
    ensure_user_plan_and_credits(user_id)
    token = create_token(user_id)
    log_event("user_login", actor_user_id=user_id, context=f"email={email};ip={_ip()}")
    return jsonify({"token": token, "user": {"id": user_id, "email": email, "role": user_role, "plan": user_plan}})


@saas_api.route("/auth/providers", methods=["GET"])
def auth_providers():
    google_configured = bool(_google_client_id() and _google_client_secret())
    facebook_configured = bool(_facebook_client_id() and _facebook_client_secret())
    return jsonify(
        {
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


@saas_api.route("/auth/oauth/google/callback", methods=["GET"])
def oauth_google_callback():
    if request.args.get("error"):
        return _oauth_redirect({"oauth_error": "google_denied"})

    state_token = (request.args.get("state") or "").strip()
    if not _consume_oauth_state(state_token, "google"):
        return _oauth_redirect({"oauth_error": "state_invalid"})

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
    platform = (data.get("platform") or "instagram").strip()
    language = (data.get("language") or "ru").strip()
    tone = (data.get("tone") or "friendly").strip()
    prompt_text = (data.get("prompt_text") or "").strip()
    media_url = (data.get("media_url") or "").strip() or None

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
    return jsonify({"id": post.id, "status": post.status, "billing": billing}), 202


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

    db = SessionLocal()
    try:
        query = db.query(Post)
        if user.role != "admin":
            query = query.filter(Post.user_id == user.id)
        if project_id:
            query = query.filter(Post.project_id == project_id)

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


@saas_api.route("/generated-posts", methods=["GET"])
@require_auth
def legacy_generated_posts_alias():
    return posts_history()


@saas_api.route("/posts/<int:post_id>/publish", methods=["POST"])
@require_auth
def publish_post(post_id: int):
    user = g.current_user
    db = SessionLocal()
    try:
        post = db.query(Post).filter_by(id=post_id).first()
        if not post:
            return jsonify({"error": "РџРѕСЃС‚ РЅРµ РЅР°Р№РґРµРЅ"}), 404
        if user.role != "admin" and post.user_id != user.id:
            return jsonify({"error": "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ"}), 403
        if post.retry_count >= 3:
            return jsonify({"error": "Р”РѕСЃС‚РёРіРЅСѓС‚ РјР°РєСЃРёРјСѓРј РїРѕРІС‚РѕСЂРѕРІ РїСѓР±Р»РёРєР°С†РёРё (3)"}), 429

        # In local/mock mode keep previous behavior.
        if settings.USE_MOCK_PROVIDERS:
            post.status = "done"
            post.published_at = datetime.utcnow()
            post.remote_id = f"mock_{post.id}_{int(datetime.utcnow().timestamp())}"
            post.retry_count += 1
            db.commit()
            return jsonify({"id": post.id, "status": post.status, "remote_id": post.remote_id, "mode": "mock"})

        # Real Meta publish path.
        connection = (
            db.query(SocialAccount)
            .filter(
                SocialAccount.user_id == post.user_id,
                SocialAccount.provider == "meta",
                SocialAccount.status == "connected_ready",
            )
            .order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc())
            .first()
        )
        if not connection:
            return jsonify({"error": "Нет подключенного Meta аккаунта для публикации"}), 400
        if not connection.token_encrypted:
            return jsonify({"error": "Токен подключения не найден. Переподключите Facebook."}), 400

        try:
            access_token = decrypt_meta_token(connection.token_encrypted)
        except Exception:
            return jsonify({"error": "Не удалось расшифровать токен. Переподключите Facebook."}), 400

        caption = (post.generated_text or post.topic or "").strip()
        if not caption:
            return jsonify({"error": "У поста нет текста для публикации"}), 400

        image_url = (post.media_url or "").strip() or None
        if post.platform == "instagram" and not image_url:
            image_url = (os.getenv("DEFAULT_IG_IMAGE_URL") or "https://picsum.photos/seed/autosocial-gpt/1200/1200").strip()
        now = datetime.utcnow()
        post.retry_count += 1

        if post.platform == "facebook":
            if not connection.page_id:
                post.status = "failed"
                post.error_message = "Не выбрана Facebook Page в подключении."
                db.commit()
                return jsonify({"error": post.error_message}), 400
            result = publish_to_facebook(connection.page_id, access_token, image_url, caption)
            remote_id = result.get("post_id") or result.get("id")
        else:
            # Instagram requires media URL via Graph API.
            if not connection.ig_user_id:
                post.status = "failed"
                post.error_message = "Нет связанного Instagram Business у выбранной страницы."
                db.commit()
                return jsonify({"error": post.error_message}), 400
            result = publish_to_instagram(connection.ig_user_id, access_token, image_url, caption)
            remote_id = result.get("id")

        if result.get("error") or not remote_id:
            post.status = "failed"
            post.error_message = str(result.get("error") or result)
            db.commit()
            return jsonify({"error": "Ошибка публикации в Meta", "details": result}), 400

        post.status = "done"
        post.published_at = now
        post.remote_id = str(remote_id)
        post.error_message = None
        db.commit()
        return jsonify({"id": post.id, "status": post.status, "remote_id": post.remote_id, "mode": "real"})
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
        schedule_at = datetime.fromisoformat(schedule_at_raw)
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


def _meta_error_to_status(meta_error: dict):
    err = meta_error or {}
    msg = str(err.get("message") or "").lower()
    code = str(err.get("code") or "")
    if code in {"190", "102"} or "access token" in msg or "oauth" in msg:
        return "token_expired", "access_token_invalid"
    if code in {"10", "200"} or "permission" in msg or "requires" in msg or "insufficient" in msg:
        return "permissions_missing", "permissions_revoked"
    if "user_denied" in msg or "denied" in msg:
        return "disconnected", "user_revoked_access"
    return "error", "meta_api_error"


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
        "pages_show_list,pages_read_engagement,instagram_basic,business_management",
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
        rows = [row for row in rows_all if row.provider == "meta"]
        return jsonify([_serialize_connection(row) for row in rows])
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

        caption = (
            "AutoSocial GPT: тестовая публикация\n"
            f"Connection #{row.id}, {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        result = publish_to_facebook(row.page_id, access_token, None, caption)
        meta_error = result.get("error") if isinstance(result, dict) else None
        post_id = (result or {}).get("post_id") or (result or {}).get("id")
        if meta_error or not post_id:
            status_from_error, reason = _meta_error_to_status(meta_error or {})
            _apply_meta_status(row, status_from_error, reason)
            db.commit()
            return jsonify(
                {
                    "error": "Ошибка тестовой публикации в Facebook",
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
    if plan_name not in {"light", "pro", "agency"}:
        return jsonify({"error": "Р’С‹Р±РµСЂРёС‚Рµ РІР°Р»РёРґРЅС‹Р№ С‚Р°СЂРёС„: light/pro/agency"}), 400

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
        user.plan = "pro"
        plan = db.query(Plan).filter_by(name="pro").first()
        user.plan_id = plan.id if plan else user.plan_id
        user.billing_status = "active"
        db.commit()
    finally:
        db.close()

    return jsonify({"plan": "pro"})


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
    if new_plan not in {"free", "light", "pro", "agency"}:
        return jsonify({"error": "РўР°СЂРёС„ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ free/light/pro/agency"}), 400

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


