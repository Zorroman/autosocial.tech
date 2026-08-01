"""CLI: create reproducible demo/E2E fixture data for the video factory.

Usage:
    python scripts/seed_demo_data.py

Requires seed_admin.py (and, for a channel to attach projects to,
seed_channel.py) to have run first. Idempotent: safe to re-run, skips
anything that already exists by name/slug.

Creates one video project in each of the states a reviewer or an E2E suite
needs to see without waiting for a real render:
  - "Demo Short (completed)"    -> status=rendered, has an output_path
  - "Demo Long (completed)"     -> status=rendered, has an output_path
  - "Demo Short (processing)"   -> status=rendering
  - "Demo Short (failed)"       -> status=failed, with a real-shaped error
  - a mock Publication attached to the completed short, privacy=private,
    a youtube_video_id that is obviously fake (never a real upload)

No real API calls, no real YouTube upload, no real OAuth token -- every
value here is either synthetic or clearly marked "mock".
"""
import os
import sys
from pathlib import Path

# Repo root, not scripts/, so sibling top-level modules import cleanly
# regardless of how this script is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app_models import AppUser, Channel, Publication, RenderJob, VideoProject  # noqa: E402
from database import SessionLocal  # noqa: E402


def _get_admin(db):
    admin_email = (os.getenv("ADMIN_EMAIL") or "admin@autosocial.local").strip().lower()
    admin = db.query(AppUser).filter_by(email=admin_email).first()
    if not admin:
        raise SystemExit("No admin user found. Run seed_admin.py first.")
    return admin


def _get_or_create_channel(db, admin):
    channel = db.query(Channel).filter_by(slug="demo-channel").first()
    if channel:
        return channel
    channel = Channel(
        owner_user_id=admin.id,
        name="Demo Channel",
        slug="demo-channel",
        niche="demo",
        description="Synthetic channel for local verification and E2E tests -- not a real YouTube channel.",
        language="ru",
        status="testing",
        default_video_format="shorts",
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    print(f"Channel created: {channel.name} (id={channel.id})")
    return channel


def _get_or_create_project(db, channel, *, title, status, **extra):
    existing = db.query(VideoProject).filter_by(channel_id=channel.id, title=title).first()
    if existing:
        print(f"Project already exists: {title} (id={existing.id})")
        return existing
    project = VideoProject(
        channel_id=channel.id,
        title=title,
        status=status,
        script_text="Раз. Два. Три. Четыре.",
        voice_mode="silent",
        **extra,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    print(f"Project created: {title} (id={project.id}, status={status})")
    return project


def _get_or_create_render_job(db, project, channel, *, status, **extra):
    existing = db.query(RenderJob).filter_by(project_id=project.id).first()
    if existing:
        print(f"Render job already exists for project {project.id} (id={existing.id})")
        return existing
    job = RenderJob(project_id=project.id, channel_id=channel.id, status=status, **extra)
    db.add(job)
    db.commit()
    db.refresh(job)
    print(f"Render job created for project {project.id} (id={job.id}, status={status})")
    return job


def main():
    db = SessionLocal()
    try:
        admin = _get_admin(db)
        channel = _get_or_create_channel(db, admin)

        completed_short = _get_or_create_project(
            db, channel,
            title="Demo Short (completed)",
            status="rendered",
            aspect_ratio="9:16",
            duration_target_seconds=45,
            output_path="output/videos/demo-short-mock.mp4",
        )
        _get_or_create_project(
            db, channel,
            title="Demo Long (completed)",
            status="rendered",
            aspect_ratio="16:9",
            duration_target_seconds=600,
            output_path="output/videos/demo-long-mock.mp4",
        )
        processing_project = _get_or_create_project(
            db, channel,
            title="Demo Short (processing)",
            status="rendering",
            aspect_ratio="9:16",
        )
        _get_or_create_render_job(
            db, processing_project, channel,
            status="running", progress=40, attempts=1,
        )
        failed_project = _get_or_create_project(
            db, channel,
            title="Demo Short (failed)",
            status="failed",
            aspect_ratio="9:16",
            error="scenes_missing_media: scenes [0, 1] have no attached media file",
        )
        _get_or_create_render_job(
            db, failed_project, channel,
            status="failed", attempts=1,
            error="scenes_missing_media: scenes [0, 1] have no attached media file",
        )

        existing_pub = db.query(Publication).filter_by(project_id=completed_short.id).first()
        if existing_pub:
            print(f"Publication already exists for project {completed_short.id} (id={existing_pub.id})")
        else:
            pub = Publication(
                channel_id=channel.id,
                project_id=completed_short.id,
                title="Demo Short (completed)",
                description="Synthetic publication for local verification -- never actually uploaded.",
                privacy_status="private",
                publish_mode="manual",
                status="published",
                youtube_video_id="mock_demo_video_id",
                youtube_url="https://example.invalid/mock-demo-video",
            )
            db.add(pub)
            db.commit()
            db.refresh(pub)
            print(f"Mock publication created (id={pub.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
