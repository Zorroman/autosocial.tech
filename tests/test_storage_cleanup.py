"""Disk-usage cleanup for the footage cache and confirmed-published render
outputs (see the 2026-08-11 disk-full outage). Scope: only files past their
retention window get deleted, reserved/unreserved footage and
unconfirmed/confirmed publications are never confused, and a missing local
file never crashes anything downstream."""
import sys

from datetime import datetime, timedelta

import pytest

from tests.test_private_admin import _fresh_app, _seed_admin, _token_for


@pytest.fixture()
def client(tmp_path):
    for m in ("storage_cleanup",):
        sys.modules.pop(m, None)
    app_module = _fresh_app(tmp_path)
    admin_id = _seed_admin()
    with app_module.app.test_client() as c:
        c.admin_token = _token_for(admin_id)
        c.tmp_path = tmp_path
        yield c


def _h(c):
    return {"Authorization": f"Bearer {c.admin_token}"}


def _mk_footage_asset(db, tmp_path, *, provider_asset_id, last_used_at=None,
                      created_at=None, reserved_by_job_id=None, write_file=True):
    from app_models import FootageAsset

    path = tmp_path / f"{provider_asset_id}.mp4"
    if write_file:
        path.write_bytes(b"x" * 1000)
    a = FootageAsset(
        provider="pexels", provider_asset_id=provider_asset_id,
        local_path=str(path), reserved_by_job_id=reserved_by_job_id,
        last_used_at=last_used_at, created_at=created_at or datetime.utcnow(),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a, path


def test_footage_cleanup_deletes_only_stale_unreserved_files(client):
    import storage_cleanup as sc
    from database import SessionLocal

    db = SessionLocal()
    now = datetime.utcnow()
    try:
        old_unreserved, old_path = _mk_footage_asset(
            db, client.tmp_path, provider_asset_id="old_unreserved",
            last_used_at=now - timedelta(days=30))
        recent, recent_path = _mk_footage_asset(
            db, client.tmp_path, provider_asset_id="recent",
            last_used_at=now - timedelta(days=1))
        old_reserved, reserved_path = _mk_footage_asset(
            db, client.tmp_path, provider_asset_id="old_reserved",
            last_used_at=now - timedelta(days=30), reserved_by_job_id=42)
        never_used, never_used_path = _mk_footage_asset(
            db, client.tmp_path, provider_asset_id="never_used",
            last_used_at=None, created_at=now - timedelta(days=30))

        deleted, freed = sc.cleanup_footage_cache(db, now)

        assert deleted == 2  # old_unreserved + never_used
        assert freed > 0
        assert not old_path.exists()
        assert not never_used_path.exists()
        assert recent_path.exists()
        assert reserved_path.exists()  # reserved -- never touched

        db.refresh(old_unreserved)
        db.refresh(recent)
        db.refresh(old_reserved)
        assert old_unreserved.local_path is None  # row kept, path cleared
        assert recent.local_path == str(recent_path)
        assert old_reserved.local_path == str(reserved_path)
    finally:
        db.close()


def test_footage_cleanup_missing_file_still_clears_row_without_crashing(client):
    # Row survives a DB restart with the underlying file already gone (e.g.
    # manually cleaned, or a prior partial run) -- must not raise.
    import storage_cleanup as sc
    from database import SessionLocal

    db = SessionLocal()
    now = datetime.utcnow()
    try:
        asset, path = _mk_footage_asset(
            db, client.tmp_path, provider_asset_id="already_gone",
            last_used_at=now - timedelta(days=30), write_file=False)
        assert not path.exists()

        deleted, freed = sc.cleanup_footage_cache(db, now)

        assert deleted == 1
        assert freed == 0
        db.refresh(asset)
        assert asset.local_path is None
    finally:
        db.close()


def _mk_project_and_publication(db, channel_id, *, output_path, status,
                                youtube_video_id, published_at):
    from app_models import VideoProject, Publication

    p = VideoProject(channel_id=channel_id, title="T", status="rendered",
                     duration_target_seconds=30, output_path=output_path)
    db.add(p)
    db.flush()
    pub = Publication(channel_id=channel_id, project_id=p.id, title=p.title,
                      status=status, privacy_status="public", publish_mode="immediate",
                      youtube_video_id=youtube_video_id, youtube_url="https://x",
                      published_at=published_at)
    db.add(pub)
    db.commit()
    return p, pub


def test_output_cleanup_deletes_only_old_confirmed_published_files(client, monkeypatch):
    import storage_cleanup as sc
    from database import SessionLocal
    from app_settings import settings

    base = client.tmp_path / "base"
    (base / "output" / "videos").mkdir(parents=True)
    monkeypatch.setattr(settings, "BASE_DIR", base)

    old_file = base / "output" / "videos" / "old.mp4"
    old_file.write_bytes(b"x" * 500)
    recent_file = base / "output" / "videos" / "recent.mp4"
    recent_file.write_bytes(b"x" * 500)
    unpublished_file = base / "output" / "videos" / "unpublished.mp4"
    unpublished_file.write_bytes(b"x" * 500)
    stuck_file = base / "output" / "videos" / "stuck_upload.mp4"
    stuck_file.write_bytes(b"x" * 500)

    db = SessionLocal()
    now = datetime.utcnow()
    try:
        r = client.post("/api/channels", json={"name": "C", "niche": "test"}, headers=_h(client))
        ch = r.get_json()["channel"]["id"]

        _mk_project_and_publication(
            db, ch, output_path="output/videos/old.mp4", status="published",
            youtube_video_id="v1", published_at=now - timedelta(days=10))
        _mk_project_and_publication(
            db, ch, output_path="output/videos/recent.mp4", status="published",
            youtube_video_id="v2", published_at=now - timedelta(days=1))
        _mk_project_and_publication(
            db, ch, output_path="output/videos/unpublished.mp4", status="draft",
            youtube_video_id=None, published_at=None)
        _mk_project_and_publication(
            db, ch, output_path="output/videos/stuck_upload.mp4", status="uploading",
            youtube_video_id=None, published_at=None)

        deleted, freed = sc.cleanup_published_outputs(db, now)

        assert deleted == 1
        assert freed == 500
        assert not old_file.exists()
        assert recent_file.exists()
        assert unpublished_file.exists()
        assert stuck_file.exists()  # exactly the 2026-08-11 stuck-upload case -- never touched
    finally:
        db.close()


def test_output_cleanup_refuses_to_escape_base_dir(client, monkeypatch):
    # A path traversal in output_path (however it got there) must never
    # delete anything outside BASE_DIR.
    import storage_cleanup as sc
    from database import SessionLocal
    from app_settings import settings

    base = client.tmp_path / "base"
    base.mkdir(parents=True)
    monkeypatch.setattr(settings, "BASE_DIR", base)

    outside = client.tmp_path / "outside.mp4"
    outside.write_bytes(b"x" * 100)

    db = SessionLocal()
    now = datetime.utcnow()
    try:
        r = client.post("/api/channels", json={"name": "C", "niche": "test"}, headers=_h(client))
        ch = r.get_json()["channel"]["id"]
        _mk_project_and_publication(
            db, ch, output_path="../outside.mp4", status="published",
            youtube_video_id="v1", published_at=now - timedelta(days=10))

        sc.cleanup_published_outputs(db, now)

        assert outside.exists()
    finally:
        db.close()


def test_run_cleanup_is_once_per_calendar_day(client):
    import storage_cleanup as sc
    from database import SessionLocal

    db = SessionLocal()
    now = datetime.utcnow()
    try:
        first = sc.run_cleanup(now)
        assert "skipped" not in first
        second = sc.run_cleanup(now)
        assert second == {"skipped": "already_ran_today"}
    finally:
        db.close()
