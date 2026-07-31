"""CLI: create a starter channel for the admin user.

Usage:
    python seed_channel.py            # creates the default esoteric channel
    ADMIN_EMAIL=... python seed_channel.py

Idempotent: skips creation if a channel with the same slug exists.
All settings are editable later via /api/channels.
"""
import json
import os

from database import SessionLocal
from app_models import AppUser, Channel, SaaSBase
from database import engine

SaaSBase.metadata.create_all(engine)

DEFAULT = {
    "name": "Эзотерика",
    "slug": "esoterica",
    "niche": "эзотерика",
    "description": "Короткие атмосферные ролики об эзотерике: символы, практики, история мистических традиций.",
    "language": "ru",
    "target_audience": "Интересующиеся эзотерикой, мистикой, символизмом; 18-45.",
    "content_style": "интригующий, атмосферный, культурно-исторический",
    "narration_style": "спокойная или интригующая подача",
    "visual_style": "атмосферный, мистический, тёмные тона, читаемый текст",
    "default_video_duration_seconds": 45,
    "default_video_format": "shorts",
    "publication_frequency": "daily",
    "status": "testing",
    "prohibited_topics": "медицинские утверждения; финансовые гарантии; юридические советы; опасные инструкции; гарантированные предсказания будущего",
    "generation_settings_json": json.dumps(
        {"structure": ["hook", "explanation", "intrigue", "cta"], "tone": "entertainment/cultural"},
        ensure_ascii=False,
    ),
    "subtitle_template_json": json.dumps({"required": True, "format": "9:16"}, ensure_ascii=False),
    "music_settings_json": json.dumps({"mood": "calm", "duck_under_voice": True}, ensure_ascii=False),
}


if __name__ == "__main__":
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    db = SessionLocal()
    try:
        q = db.query(AppUser)
        admin = q.filter_by(email=admin_email).first() if admin_email else q.filter_by(role="admin").first()
        if not admin:
            raise SystemExit("No admin user found. Run seed_admin.py first.")
        existing = db.query(Channel).filter_by(slug=DEFAULT["slug"]).first()
        if existing:
            print(f"Channel already exists: {existing.slug} (id={existing.id})")
        else:
            channel = Channel(owner_user_id=admin.id, **DEFAULT)
            db.add(channel)
            db.commit()
            db.refresh(channel)
            print(f"Channel created: {channel.name} (id={channel.id}, owner={admin.email})")
    finally:
        db.close()
