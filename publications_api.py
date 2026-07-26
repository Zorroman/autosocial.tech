"""YouTube publication workflow (private factory mode).

Manual-first: prepare metadata from a rendered VideoProject, download the MP4,
upload by hand, save the resulting YouTube URL. Automatic upload goes through
the render queue and requires a linked YouTube connection with upload scope;
it is never triggered implicitly.

Tokens are Fernet-encrypted in social_accounts and are never returned by any
endpoint here.
"""
import json
import re
import threading
from datetime import datetime
from pathlib import Path

import requests
from flask import Blueprint, g, jsonify, request

from database import SessionLocal
from saas_auth import require_auth
from saas_models import Channel, Publication, RenderJob, SocialAccount, VideoProject, VideoScene
from saas_services import decrypt_meta_token, encrypt_meta_token
from saas_settings import settings

publications_api = Blueprint("publications_api", __name__, url_prefix="/api")

PRIVACY_STATUSES = {"public", "unlisted", "private"}
PUBLISH_MODES = {"manual", "immediate", "scheduled"}
PUB_STATUSES = {"draft", "ready", "uploading", "published", "failed", "cancelled"}
PUB_ACTIVE = {"draft", "ready", "uploading"}
YT_MAX_FILE_BYTES = 256 * 1024 * 1024 * 1024  # YouTube API hard limit (256 GB)
_YT_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _own_channel(db, channel_id: int) -> Channel | None:
    return (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


def _own_project(db, project_id: int) -> VideoProject | None:
    return (
        db.query(VideoProject)
        .join(Channel, Channel.id == VideoProject.channel_id)
        .filter(VideoProject.id == project_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


def _own_publication(db, pub_id: int) -> Publication | None:
    return (
        db.query(Publication)
        .join(Channel, Channel.id == Publication.channel_id)
        .filter(Publication.id == pub_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


def _iso(dt):
    return dt.isoformat() if dt else None


def _pub_dict(p: Publication) -> dict:
    return {
        "id": p.id,
        "channel_id": p.channel_id,
        "project_id": p.project_id,
        "title": p.title,
        "description": p.description,
        "tags": json.loads(p.tags_json) if p.tags_json else [],
        "privacy_status": p.privacy_status,
        "publish_mode": p.publish_mode,
        "scheduled_at": _iso(p.scheduled_at),
        "status": p.status,
        "youtube_video_id": p.youtube_video_id,
        "youtube_url": p.youtube_url,
        "attempts": p.attempts,
        "last_error": p.last_error,
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
        "published_at": _iso(p.published_at),
    }


# ------------------------------------------------------- channel <-> YouTube

def _user_youtube_account(db) -> SocialAccount | None:
    return (
        db.query(SocialAccount)
        .filter(SocialAccount.user_id == g.current_user.id, SocialAccount.provider == "youtube")
        .order_by(SocialAccount.updated_at.desc())
        .first()
    )


def _yt_channel_status_dict(c: Channel) -> dict:
    return {
        "youtube_channel_id": c.youtube_channel_id,
        "youtube_channel_title": c.youtube_channel_title,
        "youtube_connection_status": c.youtube_connection_status or "not_connected",
        "youtube_connected_at": _iso(c.youtube_connected_at),
        "youtube_last_verified_at": _iso(c.youtube_last_verified_at),
    }


def _yt_list_my_channels(access_token: str) -> tuple[list[dict] | None, str | None]:
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true", "maxResults": 50},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        return None, f"network_error: {str(exc)[:200]}"
    if not resp.ok:
        detail = ""
        try:
            detail = str(((resp.json() or {}).get("error") or {}).get("message") or "")[:200]
        except Exception:
            pass
        return None, f"youtube_api_{resp.status_code}: {detail}"
    items = (resp.json() or {}).get("items") or []
    out = []
    for it in items:
        sn = it.get("snippet") or {}
        out.append({"id": str(it.get("id") or ""), "title": str(sn.get("title") or "")})
    return out, None


def _account_token(acc: SocialAccount) -> str | None:
    if not acc or not acc.token_encrypted:
        return None
    try:
        return decrypt_meta_token(acc.token_encrypted)
    except Exception:
        return None


def _refresh_account_token(db, acc: SocialAccount) -> str | None:
    """Refresh the Google access token using the stored refresh token."""
    import os
    if not acc or not acc.refresh_token_encrypted:
        return None
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        return None
    try:
        refresh_token = decrypt_meta_token(acc.refresh_token_encrypted)
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
        if not resp.ok:
            return None
        data = resp.json() or {}
        token = str(data.get("access_token") or "").strip()
        if not token:
            return None
        acc.token_encrypted = encrypt_meta_token(token)
        from datetime import timedelta
        acc.token_expires_at = datetime.utcnow() + timedelta(seconds=int(data.get("expires_in") or 0))
        acc.updated_at = datetime.utcnow()
        db.commit()
        return token
    except Exception:
        return None


def _valid_account_token(db, acc: SocialAccount) -> str | None:
    token = _account_token(acc)
    if token and acc.token_expires_at and acc.token_expires_at > datetime.utcnow():
        return token
    refreshed = _refresh_account_token(db, acc)
    return refreshed or token


@publications_api.route("/channels/<int:channel_id>/youtube/status", methods=["GET"])
@require_auth
def channel_youtube_status(channel_id: int):
    import os
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        acc = _user_youtube_account(db)
        missing = [
            name for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")
            if not (os.getenv(name) or "").strip()
        ]
        out = _yt_channel_status_dict(c)
        out["oauth_configured"] = not missing
        out["oauth_missing_vars"] = missing
        out["account_connected"] = bool(acc and acc.status == "connected_ready")
        return jsonify(out)
    finally:
        db.close()


@publications_api.route("/channels/<int:channel_id>/youtube/available", methods=["GET"])
@require_auth
def channel_youtube_available(channel_id: int):
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        acc = _user_youtube_account(db)
        if not acc:
            return jsonify({"error": "YouTube account is not connected. Use «Подключить YouTube» first."}), 409
        token = _valid_account_token(db, acc)
        if not token:
            return jsonify({"error": "YouTube token is missing or expired; reconnect the account."}), 409
        channels, err = _yt_list_my_channels(token)
        if err:
            return jsonify({"error": err}), 502
        return jsonify({"channels": channels})
    finally:
        db.close()


@publications_api.route("/channels/<int:channel_id>/youtube/link", methods=["POST"])
@require_auth
def channel_youtube_link(channel_id: int):
    data = request.get_json(silent=True) or {}
    yt_id = str(data.get("youtube_channel_id") or "").strip()
    if not yt_id:
        return jsonify({"error": "youtube_channel_id is required"}), 400
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        acc = _user_youtube_account(db)
        token = _valid_account_token(db, acc) if acc else None
        if not token:
            return jsonify({"error": "YouTube account is not connected"}), 409
        channels, err = _yt_list_my_channels(token)
        if err:
            return jsonify({"error": err}), 502
        match = next((ch for ch in channels if ch["id"] == yt_id), None)
        if not match:
            return jsonify({"error": "This YouTube channel is not available for the connected account"}), 400
        conflict = (
            db.query(Channel)
            .filter(Channel.youtube_channel_id == yt_id, Channel.id != c.id,
                    Channel.owner_user_id == g.current_user.id, Channel.status != "archived")
            .first()
        )
        if conflict:
            return jsonify({"error": f"YouTube channel already linked to «{conflict.name}»"}), 409
        c.youtube_channel_id = yt_id
        c.youtube_channel_title = match["title"][:255]
        c.youtube_connection_status = "connected"
        c.youtube_connected_at = datetime.utcnow()
        c.youtube_social_account_id = acc.id
        c.youtube_last_verified_at = datetime.utcnow()
        db.commit()
        return jsonify(_yt_channel_status_dict(c))
    finally:
        db.close()


@publications_api.route("/channels/<int:channel_id>/youtube/verify", methods=["POST"])
@require_auth
def channel_youtube_verify(channel_id: int):
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        if not c.youtube_channel_id:
            return jsonify({"error": "Channel has no linked YouTube channel"}), 409
        acc = db.query(SocialAccount).filter_by(id=c.youtube_social_account_id).first() if c.youtube_social_account_id else _user_youtube_account(db)
        token = _valid_account_token(db, acc) if acc else None
        if not token:
            c.youtube_connection_status = "token_expired"
            db.commit()
            return jsonify({"error": "Token missing/expired", **_yt_channel_status_dict(c)}), 409
        channels, err = _yt_list_my_channels(token)
        if err:
            c.youtube_connection_status = "error"
            db.commit()
            return jsonify({"error": err, **_yt_channel_status_dict(c)}), 502
        ok = any(ch["id"] == c.youtube_channel_id for ch in channels)
        c.youtube_connection_status = "connected" if ok else "error"
        c.youtube_last_verified_at = datetime.utcnow()
        db.commit()
        return jsonify(_yt_channel_status_dict(c))
    finally:
        db.close()


@publications_api.route("/channels/<int:channel_id>/youtube/unlink", methods=["POST"])
@require_auth
def channel_youtube_unlink(channel_id: int):
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        c.youtube_channel_id = None
        c.youtube_channel_title = None
        c.youtube_connection_status = "not_connected"
        c.youtube_connected_at = None
        c.youtube_social_account_id = None
        c.youtube_last_verified_at = None
        db.commit()
        return jsonify(_yt_channel_status_dict(c))
    finally:
        db.close()


# ------------------------------------------------------------- publications

def _project_output_file(p: VideoProject) -> Path | None:
    if not p.output_path:
        return None
    f = (settings.BASE_DIR / p.output_path).resolve()
    if settings.BASE_DIR not in f.parents:
        return None
    return f if f.exists() else None


@publications_api.route("/video-projects/<int:project_id>/prepare-publication", methods=["POST"])
@require_auth
def prepare_publication(project_id: int):
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        if p.status != "rendered":
            return jsonify({"error": f"Project render is not completed (status={p.status})"}), 409
        out_file = _project_output_file(p)
        if not out_file:
            return jsonify({"error": "Rendered MP4 file is missing"}), 409
        active = (
            db.query(Publication)
            .filter(Publication.project_id == p.id, Publication.status.in_(PUB_ACTIVE))
            .first()
        )
        if active:
            return jsonify({"error": "An active publication already exists for this project",
                            "publication": _pub_dict(active)}), 409
        published = (
            db.query(Publication)
            .filter(Publication.project_id == p.id, Publication.status == "published")
            .first()
        )
        if published:
            return jsonify({"error": "This project is already published",
                            "publication": _pub_dict(published)}), 409
        channel = db.query(Channel).filter_by(id=p.channel_id).first()
        tags = []
        if channel and channel.niche:
            tags = [w.strip() for w in re.split(r"[,;]", channel.niche) if w.strip()][:10]
        pub = Publication(
            channel_id=p.channel_id,
            project_id=p.id,
            title=p.title[:100],
            description=(p.script_text or "")[:4500],
            tags_json=json.dumps(tags, ensure_ascii=False),
            privacy_status="private",
            publish_mode="manual",
            status="draft",
        )
        db.add(pub)
        db.commit()
        db.refresh(pub)
        out = _pub_dict(pub)
        out["file"] = {
            "path": p.output_path,
            "url": f"/api/media/{p.output_path}",
            "size_bytes": out_file.stat().st_size,
        }
        return jsonify({"publication": out}), 201
    finally:
        db.close()


@publications_api.route("/publications", methods=["GET"])
@require_auth
def list_publications():
    db = SessionLocal()
    try:
        q = (
            db.query(Publication)
            .join(Channel, Channel.id == Publication.channel_id)
            .filter(Channel.owner_user_id == g.current_user.id)
        )
        status = (request.args.get("status") or "").strip().lower()
        if status:
            q = q.filter(Publication.status == status)
        channel_id = request.args.get("channel_id", type=int)
        if channel_id:
            q = q.filter(Publication.channel_id == channel_id)
        rows = q.order_by(Publication.created_at.desc()).limit(100).all()
        return jsonify({"publications": [_pub_dict(r) for r in rows]})
    finally:
        db.close()


@publications_api.route("/publications/<int:pub_id>", methods=["GET"])
@require_auth
def get_publication(pub_id: int):
    db = SessionLocal()
    try:
        pub = _own_publication(db, pub_id)
        if not pub:
            return jsonify({"error": "Publication not found"}), 404
        out = _pub_dict(pub)
        project = db.query(VideoProject).filter_by(id=pub.project_id).first()
        if project and project.output_path:
            f = _project_output_file(project)
            out["file"] = {
                "path": project.output_path,
                "url": f"/api/media/{project.output_path}",
                "size_bytes": f.stat().st_size if f else None,
                "exists": bool(f),
            }
        return jsonify({"publication": out})
    finally:
        db.close()


@publications_api.route("/publications/<int:pub_id>", methods=["PATCH"])
@require_auth
def update_publication(pub_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        pub = _own_publication(db, pub_id)
        if not pub:
            return jsonify({"error": "Publication not found"}), 404
        if pub.status in {"published", "uploading"}:
            return jsonify({"error": f"Publication is {pub.status} and cannot be edited"}), 409
        if "title" in data:
            title = str(data.get("title") or "").strip()
            if not title:
                return jsonify({"error": "title cannot be empty"}), 400
            pub.title = title[:100]
        if "description" in data:
            pub.description = str(data.get("description") or "").strip()[:4900] or None
        if "tags" in data:
            tags = data.get("tags")
            if isinstance(tags, str):
                tags = [t.strip().lstrip("#") for t in re.split(r"[,\s]+", tags) if t.strip()]
            if not isinstance(tags, list):
                return jsonify({"error": "tags must be a list or comma-separated string"}), 400
            pub.tags_json = json.dumps([str(t)[:60] for t in tags][:30], ensure_ascii=False)
        if "privacy_status" in data:
            priv = str(data.get("privacy_status") or "").strip().lower()
            if priv not in PRIVACY_STATUSES:
                return jsonify({"error": f"privacy_status must be one of {sorted(PRIVACY_STATUSES)}"}), 400
            pub.privacy_status = priv
        if "publish_mode" in data:
            mode = str(data.get("publish_mode") or "").strip().lower()
            if mode not in PUBLISH_MODES:
                return jsonify({"error": f"publish_mode must be one of {sorted(PUBLISH_MODES)}"}), 400
            pub.publish_mode = mode
        if "scheduled_at" in data:
            raw = str(data.get("scheduled_at") or "").strip()
            if raw:
                try:
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except ValueError:
                    return jsonify({"error": "scheduled_at must be ISO datetime"}), 400
                dt_utc = dt.replace(tzinfo=None) if dt.tzinfo is None else dt.astimezone(tz=None).replace(tzinfo=None)
                if dt_utc <= datetime.utcnow():
                    return jsonify({"error": "scheduled_at must be in the future"}), 400
                pub.scheduled_at = dt_utc
            else:
                pub.scheduled_at = None
        if "status" in data:
            st = str(data.get("status") or "").strip().lower()
            if st not in {"draft", "ready", "cancelled"}:
                return jsonify({"error": "status can only be set to draft, ready or cancelled here"}), 400
            pub.status = st
        pub.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(pub)
        return jsonify({"publication": _pub_dict(pub)})
    finally:
        db.close()


@publications_api.route("/publications/<int:pub_id>/manual-complete", methods=["POST"])
@require_auth
def manual_complete(pub_id: int):
    """Manual-first flow: the owner uploaded the MP4 by hand and records the
    resulting YouTube video ID / URL."""
    data = request.get_json(silent=True) or {}
    raw = str(data.get("youtube_video_id") or data.get("youtube_url") or "").strip()
    if not raw:
        return jsonify({"error": "youtube_video_id or youtube_url is required"}), 400
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", raw)
    video_id = m.group(1) if m else raw
    if not _YT_VIDEO_ID_RE.match(video_id):
        return jsonify({"error": "Invalid YouTube video ID"}), 400
    db = SessionLocal()
    try:
        pub = _own_publication(db, pub_id)
        if not pub:
            return jsonify({"error": "Publication not found"}), 404
        if pub.status == "published":
            return jsonify({"error": "Publication is already published"}), 409
        if pub.status == "uploading":
            return jsonify({"error": "Automatic upload is in progress"}), 409
        dup = (
            db.query(Publication)
            .join(Channel, Channel.id == Publication.channel_id)
            .filter(Publication.youtube_video_id == video_id,
                    Channel.owner_user_id == g.current_user.id,
                    Publication.id != pub.id)
            .first()
        )
        if dup:
            return jsonify({"error": f"This YouTube video is already recorded in publication #{dup.id}"}), 409
        pub.youtube_video_id = video_id
        pub.youtube_url = f"https://www.youtube.com/shorts/{video_id}"
        pub.status = "published"
        pub.publish_mode = "manual"
        pub.published_at = datetime.utcnow()
        pub.last_error = None
        pub.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(pub)
        return jsonify({"publication": _pub_dict(pub)})
    finally:
        db.close()


# ------------------------------------------------------------- auto upload

_YT_PLAYLIST_ITEMS = "https://www.googleapis.com/youtube/v3/playlistItems"


def _add_video_to_playlist(db, project, video_id: str, token: str) -> str:
    """Add a just-published video to its content pillar's YouTube playlist.
    Idempotent (skips when already present or already recorded). Best-effort —
    never raises; publishing is never failed because of a playlist add."""
    try:
        from saas_models import ContentPillar
        if not project or not getattr(project, "content_pillar_id", None):
            return "no_playlist"
        if (getattr(project, "playlist_status", "") or "") == "added":
            return "added"
        pillar = db.query(ContentPillar).filter_by(id=project.content_pillar_id).first()
        plid = ((pillar.youtube_playlist_id or "").strip() if pillar else "")
        if not plid:
            project.playlist_status = "no_playlist"
            db.commit()
            return "no_playlist"
        # idempotency: already in the playlist?
        chk = requests.get(_YT_PLAYLIST_ITEMS,
                           params={"part": "snippet", "playlistId": plid,
                                   "videoId": video_id, "maxResults": 1},
                           headers={"Authorization": f"Bearer {token}"}, timeout=20)
        if chk.ok and (chk.json().get("items")):
            project.playlist_status = "added"
            db.commit()
            return "added"
        body = {"snippet": {"playlistId": plid,
                            "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
        r = requests.post(_YT_PLAYLIST_ITEMS, params={"part": "snippet"}, json=body,
                          headers={"Authorization": f"Bearer {token}"}, timeout=20)
        if r.ok:
            project.playlist_status = "added"
            db.commit()
            return "added"
        project.playlist_status = "failed"
        db.commit()
        return f"failed:{r.status_code}"
    except Exception as exc:
        try:
            project.playlist_status = "failed"
            db.commit()
        except Exception:
            pass
        return f"error:{str(exc)[:120]}"


def run_upload_job(pub_id: int) -> None:
    """Uploads the project MP4 to YouTube. Only runs when explicitly enqueued.
    Status flips to published only after the API confirms a video id."""
    db = SessionLocal()
    try:
        pub = db.query(Publication).filter_by(id=pub_id).first()
        if not pub or pub.status != "uploading":
            return
        pub.attempts = (pub.attempts or 0) + 1
        db.commit()
        project = db.query(VideoProject).filter_by(id=pub.project_id).first()
        channel = db.query(Channel).filter_by(id=pub.channel_id).first()
        try:
            out_file = _project_output_file(project) if project else None
            if not out_file:
                raise RuntimeError("mp4_missing")
            if out_file.stat().st_size > YT_MAX_FILE_BYTES:
                raise RuntimeError("file_too_large")
            acc = db.query(SocialAccount).filter_by(id=channel.youtube_social_account_id).first() if channel and channel.youtube_social_account_id else None
            token = _valid_account_token(db, acc) if acc else None
            if not token:
                raise RuntimeError("youtube_token_unavailable: reconnect the channel")

            tags = json.loads(pub.tags_json) if pub.tags_json else []
            body = {
                "snippet": {
                    "title": pub.title,
                    "description": pub.description or "",
                    "tags": tags,
                    "categoryId": "24",
                },
                "status": {"privacyStatus": pub.privacy_status, "selfDeclaredMadeForKids": False},
            }
            if pub.publish_mode == "scheduled" and pub.scheduled_at:
                body["status"]["privacyStatus"] = "private"
                body["status"]["publishAt"] = pub.scheduled_at.isoformat() + "Z"

            init = requests.post(
                "https://www.googleapis.com/upload/youtube/v3/videos",
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": "video/mp4",
                    "X-Upload-Content-Length": str(out_file.stat().st_size),
                },
                json=body,
                timeout=30,
            )
            if init.status_code == 403:
                detail = ""
                try:
                    detail = str(((init.json() or {}).get("error") or {}).get("message") or "")[:300]
                except Exception:
                    pass
                if "quota" in detail.lower():
                    raise RuntimeError(f"quota_exceeded: {detail}")
                raise RuntimeError(f"forbidden: {detail or 'upload scope missing?'}")
            if not init.ok or "Location" not in init.headers:
                raise RuntimeError(f"upload_init_failed: HTTP {init.status_code}")
            upload_url = init.headers["Location"]
            with out_file.open("rb") as fh:
                up = requests.put(
                    upload_url,
                    data=fh,
                    headers={"Content-Type": "video/mp4"},
                    timeout=1800,
                )
            if not up.ok:
                raise RuntimeError(f"upload_failed: HTTP {up.status_code}")
            video_id = str((up.json() or {}).get("id") or "").strip()
            if not _YT_VIDEO_ID_RE.match(video_id):
                raise RuntimeError("upload_no_video_id")
            pub.youtube_video_id = video_id
            pub.youtube_url = f"https://www.youtube.com/shorts/{video_id}"
            pub.status = "published"
            pub.published_at = datetime.utcnow()
            pub.last_error = None
            pub.updated_at = datetime.utcnow()
            # Content Factory: mark the publish station done.
            _proj = db.query(VideoProject).filter_by(id=pub.project_id).first()
            if _proj:
                _proj.pipeline_stage = "publish"
                _proj.pipeline_state = "done"
                _proj.pipeline_error = None
            db.commit()
            from ai_pricing import record_cost
            record_cost(provider="google", model="youtube-data-api", operation_type="YouTube upload",
                        channel_id=pub.channel_id, project_id=pub.project_id,
                        request_id=f"upload:{pub.id}:{video_id}", db=db)
            # Sort the published video into its pillar's playlist (best-effort).
            try:
                _add_video_to_playlist(db, _proj, video_id, token)
            except Exception:
                pass
        except Exception as exc:
            pub = db.query(Publication).filter_by(id=pub_id).first()
            if pub and pub.status == "uploading":
                pub.status = "failed"
                pub.last_error = str(exc)[:1000]
                pub.updated_at = datetime.utcnow()
                # Content Factory: a failed publish needs a human — never auto-retry
                # in a way that could duplicate the upload.
                _proj = db.query(VideoProject).filter_by(id=pub.project_id).first()
                if _proj:
                    _proj.pipeline_stage = "publish"
                    _proj.pipeline_state = "needs_review"
                    _proj.pipeline_error = f"Публикация не удалась: {str(exc)[:200]}"
                db.commit()
    finally:
        db.close()


def _enqueue_upload(pub_id: int):
    if settings.SYNC_JOBS:
        run_upload_job(pub_id)
        return "sync"
    try:
        from redis import Redis
        from rq import Queue
        conn = Redis.from_url(settings.REDIS_URL)
        conn.ping()
        Queue("render", connection=conn).enqueue(run_upload_job, pub_id, job_timeout=3600)
        return "rq"
    except Exception:
        t = threading.Thread(target=run_upload_job, args=(pub_id,), daemon=True)
        t.start()
        return "thread"


@publications_api.route("/publications/<int:pub_id>/upload", methods=["POST"])
@require_auth
def start_upload(pub_id: int):
    db = SessionLocal()
    try:
        pub = _own_publication(db, pub_id)
        if not pub:
            return jsonify({"error": "Publication not found"}), 404
        if pub.status == "published":
            return jsonify({"error": "Already published"}), 409
        if pub.status == "uploading":
            return jsonify({"error": "Upload already in progress"}), 409
        if pub.youtube_video_id:
            return jsonify({"error": "A YouTube video is already recorded for this publication"}), 409
        project = db.query(VideoProject).filter_by(id=pub.project_id).first()
        if not project or project.status != "rendered" or not _project_output_file(project):
            return jsonify({"error": "Rendered MP4 is missing"}), 409
        channel = db.query(Channel).filter_by(id=pub.channel_id).first()
        if not channel or not channel.youtube_channel_id or channel.youtube_connection_status != "connected":
            return jsonify({"error": "Channel has no connected YouTube channel"}), 409
        if not channel.automatic_publishing_enabled:
            return jsonify({"error": "Automatic publishing is disabled for this channel"}), 409
        if project.channel_id != pub.channel_id:
            return jsonify({"error": "Project belongs to a different channel; publishing forbidden"}), 409
        if pub.publish_mode == "scheduled":
            if not pub.scheduled_at:
                return jsonify({"error": "scheduled_at is required for scheduled mode"}), 400
            if pub.scheduled_at <= datetime.utcnow():
                return jsonify({"error": "scheduled_at must be in the future"}), 400
        pub.status = "uploading"
        pub.updated_at = datetime.utcnow()
        db.commit()
        pid = pub.id
        payload = _pub_dict(pub)
    finally:
        db.close()
    mode = _enqueue_upload(pid)
    payload["queue_mode"] = mode
    return jsonify({"publication": payload}), 202


@publications_api.route("/video-projects/<int:project_id>/pipeline/publish", methods=["POST"])
@require_auth
def factory_publish(project_id: int):
    """Content Factory publish station. Builds a Publication from the AI Publisher
    selected metadata and uploads to YouTube. Explicit publish is allowed in both
    modes (the mode + confirmation dialog already govern autonomy). Idempotent:
    never double-publishes. Pass dry_run=true to preview without uploading."""
    data = request.get_json(silent=True) or {}
    dry_run = bool(data.get("dry_run"))
    db = SessionLocal()
    try:
        p = _own_project(db, project_id)
        if not p:
            return jsonify({"error": "Project not found"}), 404
        channel = db.query(Channel).filter_by(id=p.channel_id).first()
        # safety gate: AI Publisher package present
        if not (p.youtube_meta_json or "").strip():
            return jsonify({"error": "Нет пакета публикации — сначала запустите AI Publisher."}), 409
        try:
            meta = json.loads(p.youtube_meta_json)
        except Exception:
            meta = {}
        titles = meta.get("title_options") or []
        descs = meta.get("description_options") or []
        ti = min(max(int(meta.get("selected_title") or 0), 0), max(0, len(titles) - 1))
        di = min(max(int(meta.get("selected_description") or 0), 0), max(0, len(descs) - 1))
        title = (titles[ti] if titles else p.title).strip()[:100]
        description = (descs[di] if descs else (p.script_text or "")).strip()
        hashtags = [h for h in (meta.get("hashtags") or []) if str(h).strip()]
        if hashtags:
            description = (description + "\n\n" + " ".join(hashtags))
        description = description[:4900]
        tags = [str(t).strip() for t in (meta.get("tags") or []) if str(t).strip()][:15]
        privacy = (meta.get("privacy") or getattr(channel, "default_visibility", None) or "private")
        if privacy not in ("public", "unlisted", "private"):
            privacy = "private"
        # safety gate: required metadata
        if not title:
            return jsonify({"error": "Нет заголовка — выберите заголовок в AI Publisher."}), 409
        # safety gate: rendered video present
        if p.status != "rendered" or not _project_output_file(p):
            return jsonify({"error": "Готовое видео отсутствует."}), 409
        # safety gate: YouTube connection valid
        if not channel or not channel.youtube_channel_id or channel.youtube_connection_status != "connected":
            return jsonify({"error": "YouTube-канал не подключён."}), 409
        # idempotency: already published?
        published = (db.query(Publication)
                     .filter(Publication.project_id == p.id, Publication.status == "published")
                     .first())
        if published:
            return jsonify({"error": "Это видео уже опубликовано.", "publication": _pub_dict(published)}), 409

        # ---- Content Factory auto-publish safety gates ---------------------
        # Any failure here leaves the project at needs_review with a precise
        # reason and never uploads. These protect both manual and automatic
        # publishing; automatic (public) publishing must clear all of them.
        def _gate_fail(msg: str, code: int = 409):
            p.pipeline_stage = "publish"
            p.pipeline_state = "needs_review"
            p.pipeline_error = msg
            db.commit()
            return jsonify({"error": msg, "gate": True}), code

        # gate: every scene has media, none left for review
        scenes = db.query(VideoScene).filter_by(project_id=p.id).all()
        if not scenes or any(not (s.selected_media_path or "").strip() for s in scenes):
            return _gate_fail("Не у всех сцен подобран видеоряд — публикация запрещена.")

        # gate: final duration within target tolerance (e.g. 27–33s for 30s)
        out_file = _project_output_file(p)
        target = int(p.duration_target_seconds
                     or getattr(channel, "default_video_duration_seconds", 0) or 0)
        if target and out_file:
            try:
                from footage_library import probe_media
                actual = float((probe_media(out_file) or {}).get("duration") or 0.0)
            except Exception:
                actual = 0.0
            tol = 3 if target <= 60 else round(target * 0.15)  # Shorts tight, long-form ±15%
            lo, hi = target - tol, target + tol
            if not (lo <= actual <= hi):
                return _gate_fail(
                    f"Длительность {actual:.1f}s вне диапазона {lo}–{hi}s — публикация запрещена.")

        # gate: final MP4 must carry an audio track (voiceover) spanning the video.
        # A broken/cut voiceover → needs_review (never publish silent/truncated).
        if out_file:
            try:
                from music_mix import _probe_dims
                dims = _probe_dims(out_file)
            except Exception:
                dims = {"has_audio": False, "audio_duration": 0.0, "duration": 0.0}
            if not dims.get("has_audio"):
                return _gate_fail("В итоговом видео нет звуковой дорожки — публикация запрещена.")
            if dims.get("audio_duration", 0.0) < (dims.get("duration", 0.0) - 1.0):
                return _gate_fail("Звук короче видео (голос обрезан) — публикация запрещена.")

        # gate: description must be non-empty
        if not (description or "").strip():
            return _gate_fail("Пустое описание — публикация запрещена.")

        # gate: automatic publishing must be explicitly public
        from factory_pipeline import effective_mode
        if effective_mode(p, channel) == "automatic" and privacy != "public":
            return _gate_fail(
                f"Автопубликация разрешена только как public (privacy={privacy}).")
        # -------------------------------------------------------------------

        if dry_run:
            return jsonify({"dry_run": True, "would_publish": {
                "title": title, "description_chars": len(description),
                "tags": tags, "privacy": privacy}}), 200
        # reuse an inactive publication if any, else create
        pub = (db.query(Publication)
               .filter(Publication.project_id == p.id,
                       Publication.status.in_(("draft", "ready", "failed", "needs_review")))
               .order_by(Publication.id.desc()).first())
        active = (db.query(Publication)
                  .filter(Publication.project_id == p.id, Publication.status == "uploading").first())
        if active:
            return jsonify({"error": "Загрузка уже идёт."}), 409
        if not pub:
            pub = Publication(channel_id=p.channel_id, project_id=p.id, status="draft")
            db.add(pub)
        pub.title = title
        pub.description = description
        pub.tags_json = json.dumps(tags, ensure_ascii=False)
        pub.privacy_status = privacy
        pub.publish_mode = "immediate"
        pub.last_error = None
        pub.status = "uploading"  # atomic claim
        pub.updated_at = datetime.utcnow()
        p.pipeline_stage = "publish"
        p.pipeline_state = "running"
        p.pipeline_error = None
        db.commit()
        db.refresh(pub)
        pub_id = pub.id
        payload = _pub_dict(pub)
    finally:
        db.close()
    mode = _enqueue_upload(pub_id)
    payload["queue_mode"] = mode
    return jsonify({"publication": payload}), 202


@publications_api.route("/publications/<int:pub_id>/retry", methods=["POST"])
@require_auth
def retry_upload(pub_id: int):
    db = SessionLocal()
    try:
        pub = _own_publication(db, pub_id)
        if not pub:
            return jsonify({"error": "Publication not found"}), 404
        if pub.status != "failed":
            return jsonify({"error": f"Only failed publications can be retried (status={pub.status})"}), 409
        if pub.youtube_video_id:
            return jsonify({"error": "A YouTube video is already recorded; retry is not allowed"}), 409
        pub.status = "uploading"
        pub.updated_at = datetime.utcnow()
        db.commit()
        pid = pub.id
        payload = _pub_dict(pub)
    finally:
        db.close()
    mode = _enqueue_upload(pid)
    payload["queue_mode"] = mode
    return jsonify({"publication": payload}), 202
