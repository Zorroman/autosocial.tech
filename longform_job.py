"""Long-form render + publish RQ job.

Runs on the same single "render" worker as the Shorts factory, so the two
never render concurrently (no CPU/RAM contention on the 3.8 GB box). Flow:

  1. longform_pipeline.run(project_id)  — memory-safe chunked 1080p render.
  2. gate on QC: only a QC-passed video (1080p, has audio spanning the full
     8–12 min) is ever published; anything else lands at needs_review.
  3. publish PUBLIC via the proven resumable upload, record a Publication,
     sort into the content pillar's YouTube playlist.

This is the ONLY auto-publish path for long-form. It deliberately does NOT go
through factory_pipeline (whose gates + render are Shorts-shaped) and writes
the correct /watch?v= URL (long-form is not a Short).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import requests

log = logging.getLogger("longform.job")

_JOB_ROOT = "/app/output/longform_jobs"
_BASE = "/app"


def _publish(db, p, ch, final_abs: Path) -> str:
    """Publish an already-rendered, QC-passed long-form MP4. Returns watch URL.
    Idempotent: refuses to double-publish a project."""
    from saas_models import SocialAccount, Publication
    from publications_api import _valid_account_token, _add_video_to_playlist, _YT_VIDEO_ID_RE
    import ai_publisher

    already = (db.query(Publication)
               .filter(Publication.project_id == p.id, Publication.status == "published")
               .first())
    if already:
        return already.youtube_url or "already_published"

    acc = db.query(SocialAccount).filter_by(id=ch.youtube_social_account_id).first()
    token = _valid_account_token(db, acc) if acc else None
    if not token:
        raise RuntimeError("youtube_token_unavailable")

    size = final_abs.stat().st_size
    rel = str(final_abs).replace(_BASE + "/", "", 1)

    pkg = ai_publisher.generate_publish_package(
        topic=p.title or "", script_text=(p.script_text or "")[:4000],
        language=(ch.language or "ru"), privacy="public")
    titles = pkg.get("title_options") or [p.title]
    descs = pkg.get("description_options") or [(p.script_text or "")[:500]]
    title = (titles[0] or p.title or "").strip()[:100]
    description = (descs[0] or "").strip()
    hashtags = [h for h in (pkg.get("hashtags") or []) if str(h).strip()]
    if hashtags:
        description = description + "\n\n" + " ".join(hashtags)
    description = description[:4900]
    tags = [str(t).strip() for t in (pkg.get("tags") or []) if str(t).strip()][:15]
    pkg["privacy"] = "public"
    p.youtube_meta_json = json.dumps(pkg, ensure_ascii=False)
    p.output_path = rel
    p.status = "rendered"
    db.commit()

    body = {"snippet": {"title": title, "description": description,
                        "tags": tags, "categoryId": "24"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    init = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4",
                 "X-Upload-Content-Length": str(size)},
        json=body, timeout=30)
    if init.status_code == 403:
        raise RuntimeError(f"forbidden: {init.text[:200]}")
    if not init.ok or "Location" not in init.headers:
        raise RuntimeError(f"upload_init_failed: HTTP {init.status_code}")
    with final_abs.open("rb") as fh:
        up = requests.put(init.headers["Location"], data=fh,
                          headers={"Content-Type": "video/mp4"}, timeout=3600)
    if not up.ok:
        raise RuntimeError(f"upload_failed: HTTP {up.status_code}")
    video_id = str((up.json() or {}).get("id") or "").strip()
    if not _YT_VIDEO_ID_RE.match(video_id):
        raise RuntimeError("upload_no_video_id")
    watch_url = f"https://www.youtube.com/watch?v={video_id}"

    pub = Publication(channel_id=p.channel_id, project_id=p.id,
                      title=title, description=description,
                      tags_json=json.dumps(tags, ensure_ascii=False),
                      privacy_status="public", publish_mode="immediate",
                      status="published", youtube_video_id=video_id,
                      youtube_url=watch_url, published_at=datetime.utcnow())
    db.add(pub)
    p.pipeline_stage = "publish"
    p.pipeline_state = "done"
    p.pipeline_error = None
    db.commit()
    try:
        _add_video_to_playlist(db, p, video_id, token)
        db.commit()
    except Exception:
        pass
    from ai_pricing import record_cost
    try:
        record_cost(provider="google", model="youtube-data-api",
                    operation_type="YouTube upload (long-form)",
                    channel_id=p.channel_id, project_id=p.id,
                    request_id=f"lf-upload:{p.id}:{video_id}", db=db)
    except Exception:
        pass
    return watch_url


def render_and_publish(project_id: int) -> dict:
    """RQ entry point: render the long-form project, then publish it if QC passes."""
    import longform_pipeline
    from database import SessionLocal
    from saas_models import VideoProject, Channel

    res = longform_pipeline.run(project_id, job_root=_JOB_ROOT)
    qc = (res or {}).get("qc") or {}
    if not qc.get("passed"):
        db = SessionLocal()
        try:
            p = db.query(VideoProject).filter_by(id=project_id).first()
            if p:
                p.pipeline_stage = "render"
                p.pipeline_state = "needs_review"
                p.pipeline_error = f"long-form QC failed: {res.get('result')}"
                db.commit()
        finally:
            db.close()
        log.warning("longform %s: QC failed (%s) — not publishing", project_id, res.get("result"))
        return {"published": False, "reason": "qc_failed", "qc": qc}

    final_abs = Path(qc["file"])
    db = SessionLocal()
    try:
        p = db.query(VideoProject).filter_by(id=project_id).first()
        ch = db.query(Channel).filter_by(id=p.channel_id).first()
        try:
            url = _publish(db, p, ch, final_abs)
            log.info("longform %s published: %s", project_id, url)
            return {"published": True, "url": url, "qc": qc}
        except Exception as exc:
            p.pipeline_stage = "publish"
            p.pipeline_state = "needs_review"
            p.pipeline_error = f"long-form publish failed: {str(exc)[:200]}"
            db.commit()
            log.warning("longform %s publish failed: %s", project_id, str(exc)[:200])
            return {"published": False, "reason": str(exc)[:200], "qc": qc}
    finally:
        db.close()
