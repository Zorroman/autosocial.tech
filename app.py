import os
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# Always load .env from the project directory, regardless of current working dir.
# Passenger can execute from __pycache__, so probe both current dir and parent.
_app_file = Path(__file__).resolve()
_env_candidates = [
    _app_file.parent / ".env",
    _app_file.parent.parent / ".env" if _app_file.parent.name == "__pycache__" else None,
]
for _env_path in _env_candidates:
    if _env_path and _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
        break

from database import engine
from facebook_api import exchange_code_for_token, get_page_and_ig_id, publish_to_facebook, publish_to_instagram
from gpt_generator import generate_post
from image_picker import get_image_by_niche
from migrations import run_migrations
from models import Base, User
from saas_api import saas_api
from saas_auth import hash_password
from saas_models import AppUser, Plan, SaaSBase
from saas_services import (
    ensure_user_plan_and_credits,
    get_or_create_default_project,
    list_blog_posts,
    log_event,
    seed_niche_catalog,
    seed_niche_hooks,
    seed_plans,
    seed_platform_rules,
)
from saas_settings import settings

app = Flask(__name__)

LOG_DIR = Path(os.getenv("LOG_DIR") or Path(__file__).resolve().with_name("logs"))
LOG_FILE = LOG_DIR / "api.log"
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
try:
    LOG_DIR.mkdir(exist_ok=True)
    _file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    if not any(isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "") == str(LOG_FILE) for h in _root_logger.handlers):
        _root_logger.addHandler(_file_handler)
except OSError:
    if not any(isinstance(h, logging.StreamHandler) for h in _root_logger.handlers):
        _stream_handler = logging.StreamHandler()
        _stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        _root_logger.addHandler(_stream_handler)

cors_origins = [x.strip() for x in str(settings.CORS_ORIGIN or "").split(",") if x.strip()]
if not cors_origins:
    cors_origins = [settings.FRONTEND_BASE_URL]
CORS(app, resources={r"/api/*": {"origins": cors_origins}}, supports_credentials=True)

Base.metadata.create_all(bind=engine)
SaaSBase.metadata.create_all(bind=engine)
run_migrations()
seed_plans()
seed_platform_rules()
seed_niche_hooks()
seed_niche_catalog()

app.register_blueprint(saas_api)

from channels_api import channels_api  # noqa: E402
app.register_blueprint(channels_api)

from video_projects_api import video_projects_api  # noqa: E402
app.register_blueprint(video_projects_api)

from publications_api import publications_api  # noqa: E402
app.register_blueprint(publications_api)

if settings.PRIVATE_ADMIN_MODE and not settings.ADMIN_ALLOWLIST_EMAILS:
    _msg = (
        "PRIVATE_ADMIN_MODE=true but ADMIN_ALLOWLIST_EMAILS is empty: "
        "all authenticated access is denied (fail closed). "
        "Set ADMIN_ALLOWLIST_EMAILS in the environment."
    )
    if (settings.ENV or "").lower() in {"production", "prod"}:
        raise RuntimeError(_msg)
    logging.getLogger(__name__).critical(_msg)


def _is_set(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def validate_auth_config() -> None:
    google_ok = _is_set("GOOGLE_CLIENT_ID") and _is_set("GOOGLE_CLIENT_SECRET")
    facebook_client_ok = _is_set("FB_LOGIN_APP_ID") or _is_set("FB_APP_ID") or _is_set("FACEBOOK_APP_ID")
    facebook_secret_ok = _is_set("FB_LOGIN_APP_SECRET") or _is_set("FB_APP_SECRET") or _is_set("FACEBOOK_APP_SECRET")
    facebook_ok = facebook_client_ok and facebook_secret_ok

    print("[auth] OAuth config check:")
    print(f"  - Google OAuth: {'OK' if google_ok else 'MISSING'} (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)")
    print(
        "  - Facebook OAuth: "
        f"{'OK' if facebook_ok else 'MISSING'} "
        "(FB_LOGIN_APP_ID/FB_APP_ID/FACEBOOK_APP_ID + FB_LOGIN_APP_SECRET/FB_APP_SECRET/FACEBOOK_APP_SECRET)"
    )
    if not google_ok:
        print("[auth] Google login will be disabled in UI until GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set.")
    if not facebook_ok:
        print("[auth] Facebook login will be disabled in UI until Facebook client id/secret are set.")


@app.route('/')
def home():
    return 'рџ”Ґ AutoSocial GPT backend + DB ready'


@app.route('/health')
def app_health():
    return jsonify({"ok": True, "service": "autosocial-api", "env": settings.ENV})


@app.route('/sitemap.xml')
def sitemap():
    rows = list_blog_posts(limit=500)
    frontend = settings.FRONTEND_BASE_URL.rstrip("/")
    urls = [f"<url><loc>{frontend}/blog/</loc></url>"]
    for row in rows:
        urls.append(f"<url><loc>{frontend}/blog/?slug={row.slug}</loc></url>")
    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
        + "".join(urls)
        + "</urlset>"
    )
    return Response(xml, mimetype="application/xml")


@app.route('/auth/callback')
def fb_callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing code"}), 400

    token_data = exchange_code_for_token(code)
    access_token = token_data.get("access_token")
    if not access_token:
        return jsonify({"error": "Token exchange failed", "details": token_data}), 400

    page_id, ig_id, raw = get_page_and_ig_id(access_token)

    fb_user_id = raw["data"][0]["id"] if raw.get("data") else None
    if not fb_user_id:
        return jsonify({"error": "No page_id found", "raw": raw}), 400

    from database import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(fb_user_id=fb_user_id).first()
        if user:
            user.access_token = access_token
            user.page_id = page_id
            user.ig_user_id = ig_id
        else:
            user = User(fb_user_id=fb_user_id, access_token=access_token, page_id=page_id, ig_user_id=ig_id)
            db.add(user)

        db.commit()
    finally:
        db.close()

    return jsonify({"fb_user_id": fb_user_id, "page_id": page_id, "ig_user_id": ig_id, "access_token": access_token})


@app.route('/generate-full-post', methods=['POST'])
def generate_full_post():
    data = request.get_json(silent=True) or {}

    niche = (data.get('niche') or 'Р±РёР·РЅРµСЃ').strip()
    topic = (data.get('topic') or '').strip()

    post_text = generate_post(niche=niche, topic=topic or None)
    image_url = get_image_by_niche(
        niche=niche,
        manual_topic=topic or niche,
        language="ru",
        goal="awareness",
        orientation="any",
    )

    return jsonify({"mode": "manual_topic" if topic else "niche_only", "niche": niche, "topic": topic, "post": post_text, "image_url": image_url})


@app.route('/publish-all', methods=['POST'])
def publish_all():
    data = request.get_json(silent=True) or {}
    fb_user_id = data.get("fb_user_id")
    caption = data.get("caption")
    image_url = data.get("image_url")

    from database import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(fb_user_id=fb_user_id).first()
    finally:
        db.close()

    if not user:
        return jsonify({"error": "User not found"}), 404

    insta_result = publish_to_instagram(ig_user_id=user.ig_user_id, access_token=user.access_token, image_url=image_url, caption=caption)
    fb_result = publish_to_facebook(page_id=user.page_id, access_token=user.access_token, image_url=image_url, caption=caption)
    return jsonify({"instagram": insta_result, "facebook": fb_result})


def seed_admin() -> None:
    admin_email = os.getenv("ADMIN_EMAIL", "admin@autosocial.local").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "admin12345").strip()

    from database import SessionLocal

    db = SessionLocal()
    try:
        existing = db.query(AppUser).filter_by(email=admin_email).first()
        if existing:
            ensure_user_plan_and_credits(existing.id)
            return

        agency = db.query(Plan).filter_by(name="agency").first()
        admin_user = AppUser(
            email=admin_email,
            password_hash=hash_password(admin_password),
            role="admin",
            plan="agency",
            plan_id=agency.id if agency else None,
            billing_status="active",
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        ensure_user_plan_and_credits(admin_user.id)
        get_or_create_default_project(admin_user.id)
        log_event("admin_seeded", actor_user_id=admin_user.id, context=admin_email)
    finally:
        db.close()


seed_admin()
validate_auth_config()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

