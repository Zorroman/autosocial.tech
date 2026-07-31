import secrets
from functools import wraps
from typing import Optional

from flask import g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from database import SessionLocal
from app_models import ApiToken, AppUser
from app_settings import settings


def is_email_allowed(email: str) -> bool:
    """Private-admin allowlist check. Fail closed: in private mode an empty
    allowlist denies everyone rather than opening the system."""
    if not settings.PRIVATE_ADMIN_MODE:
        return True
    normalized = (email or "").strip().lower()
    if not settings.ADMIN_ALLOWLIST_EMAILS:
        return False
    return normalized in settings.ADMIN_ALLOWLIST_EMAILS


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def create_token(user_id: int) -> str:
    token = secrets.token_hex(32)
    db = SessionLocal()
    try:
        db.add(ApiToken(token=token, user_id=user_id))
        db.commit()
        return token
    finally:
        db.close()


def get_user_by_token(token: str) -> Optional[AppUser]:
    db = SessionLocal()
    try:
        token_row = db.query(ApiToken).filter_by(token=token).first()
        if not token_row:
            return None
        return db.query(AppUser).filter_by(id=token_row.user_id).first()
    finally:
        db.close()


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401

        token = auth_header.split(" ", 1)[1].strip()
        user = get_user_by_token(token)
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        if not is_email_allowed(user.email):
            return jsonify({"error": "Access restricted"}), 403

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def require_role(role: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            if user.role != role:
                return jsonify({"error": "Forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
