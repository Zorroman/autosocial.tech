"""Channel analytics + AI cost API (private factory mode).

Manual-first: snapshots can be entered by hand (data_source='manual') without
any YouTube Analytics OAuth. API sync uses the already-granted
youtube.readonly scope and the YouTube Data API (views/likes/comments only);
watch time / revenue stay nullable until entered manually — never fabricated.
"""
import json
import math
import re
import statistics
from datetime import datetime, timedelta

import requests
from flask import Blueprint, g, jsonify, request

from ai_pricing import budgets, record_cost, spent_summary
from database import SessionLocal
from auth import require_auth
from app_models import AICostRecord, Channel, Publication, VideoAnalyticsSnapshot
from publications_api import _valid_account_token, _user_youtube_account

analytics_api = Blueprint("analytics_api", __name__, url_prefix="/api")

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_MAX_COUNT = 10**12
_NUMERIC_FIELDS = {
    "views": int, "likes": int, "comments": int, "shares": int,
    "subscribers_gained": int, "watch_time_minutes": float,
    "average_view_duration": float, "average_view_percentage": float,
    "impressions": int, "click_through_rate": float, "estimated_revenue": float,
}


def _own_channel(db, channel_id: int) -> Channel | None:
    return (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.owner_user_id == g.current_user.id)
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


def _snap_dict(s: VideoAnalyticsSnapshot) -> dict:
    return {
        "id": s.id,
        "channel_id": s.channel_id,
        "publication_id": s.publication_id,
        "youtube_video_id": s.youtube_video_id,
        "data_source": s.data_source,
        "captured_at": _iso(s.captured_at),
        "views": s.views,
        "likes": s.likes,
        "comments": s.comments,
        "shares": s.shares,
        "subscribers_gained": s.subscribers_gained,
        "watch_time_minutes": s.watch_time_minutes,
        "average_view_duration": s.average_view_duration,
        "average_view_percentage": s.average_view_percentage,
        "impressions": s.impressions,
        "click_through_rate": s.click_through_rate,
        "estimated_revenue": s.estimated_revenue,
        "currency": s.currency,
        "created_at": _iso(s.created_at),
    }


def _validate_metrics(data: dict) -> tuple[dict, str | None]:
    out = {}
    for field, cast in _NUMERIC_FIELDS.items():
        if field not in data:
            continue
        raw = data.get(field)
        if raw is None or raw == "":
            out[field] = None
            continue
        try:
            val = cast(float(raw))
        except (TypeError, ValueError):
            return {}, f"{field} must be a number"
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return {}, f"{field} must be finite"
        if val < 0:
            return {}, f"{field} cannot be negative"
        if val > _MAX_COUNT:
            return {}, f"{field} is out of range"
        if field == "average_view_percentage" and val > 100:
            return {}, "average_view_percentage cannot exceed 100"
        out[field] = val
    if "currency" in data:
        cur = str(data.get("currency") or "").strip().upper()
        if cur and not _CURRENCY_RE.match(cur):
            return {}, "currency must be a 3-letter code"
        out["currency"] = cur or None
    return out, None


# ----------------------------------------------------------- manual snapshots

@analytics_api.route("/publications/<int:pub_id>/analytics", methods=["POST"])
@require_auth
def create_snapshot(pub_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        pub = _own_publication(db, pub_id)
        if not pub:
            return jsonify({"error": "Publication not found"}), 404
        metrics, err = _validate_metrics(data)
        if err:
            return jsonify({"error": err}), 400
        if not any(v is not None for k, v in metrics.items() if k != "currency"):
            return jsonify({"error": "At least one metric is required"}), 400
        captured_raw = str(data.get("captured_at") or "").strip()
        if captured_raw:
            try:
                captured = datetime.fromisoformat(captured_raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return jsonify({"error": "captured_at must be ISO datetime"}), 400
        else:
            captured = datetime.utcnow().replace(microsecond=0)
        dup = (
            db.query(VideoAnalyticsSnapshot)
            .filter_by(publication_id=pub.id, captured_at=captured, data_source="manual")
            .first()
        )
        if dup:
            return jsonify({"error": "A manual snapshot for this timestamp already exists", "snapshot": _snap_dict(dup)}), 409
        snap = VideoAnalyticsSnapshot(
            channel_id=pub.channel_id,
            publication_id=pub.id,
            youtube_video_id=pub.youtube_video_id,
            data_source="manual",
            captured_at=captured,
            **metrics,
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        return jsonify({"snapshot": _snap_dict(snap)}), 201
    finally:
        db.close()


@analytics_api.route("/analytics/snapshots", methods=["GET"])
@require_auth
def list_snapshots():
    db = SessionLocal()
    try:
        q = (
            db.query(VideoAnalyticsSnapshot)
            .join(Channel, Channel.id == VideoAnalyticsSnapshot.channel_id)
            .filter(Channel.owner_user_id == g.current_user.id)
        )
        channel_id = request.args.get("channel_id", type=int)
        if channel_id:
            q = q.filter(VideoAnalyticsSnapshot.channel_id == channel_id)
        publication_id = request.args.get("publication_id", type=int)
        if publication_id:
            q = q.filter(VideoAnalyticsSnapshot.publication_id == publication_id)
        rows = q.order_by(VideoAnalyticsSnapshot.captured_at.desc()).limit(200).all()
        return jsonify({"snapshots": [_snap_dict(s) for s in rows]})
    finally:
        db.close()


def _own_snapshot(db, snap_id: int) -> VideoAnalyticsSnapshot | None:
    return (
        db.query(VideoAnalyticsSnapshot)
        .join(Channel, Channel.id == VideoAnalyticsSnapshot.channel_id)
        .filter(VideoAnalyticsSnapshot.id == snap_id, Channel.owner_user_id == g.current_user.id)
        .first()
    )


@analytics_api.route("/analytics/snapshots/<int:snap_id>", methods=["PATCH"])
@require_auth
def update_snapshot(snap_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        snap = _own_snapshot(db, snap_id)
        if not snap:
            return jsonify({"error": "Snapshot not found"}), 404
        if snap.data_source != "manual":
            return jsonify({"error": "Only manual snapshots can be edited"}), 409
        metrics, err = _validate_metrics(data)
        if err:
            return jsonify({"error": err}), 400
        for k, v in metrics.items():
            setattr(snap, k, v)
        db.commit()
        db.refresh(snap)
        return jsonify({"snapshot": _snap_dict(snap)})
    finally:
        db.close()


@analytics_api.route("/analytics/snapshots/<int:snap_id>", methods=["DELETE"])
@require_auth
def delete_snapshot(snap_id: int):
    db = SessionLocal()
    try:
        snap = _own_snapshot(db, snap_id)
        if not snap:
            return jsonify({"error": "Snapshot not found"}), 404
        if snap.data_source != "manual":
            return jsonify({"error": "Only manual snapshots can be deleted"}), 409
        db.delete(snap)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


# ----------------------------------------------------------------- API sync

def _fetch_subscribers_by_video(token: str, video_ids: list[str]) -> dict:
    """Lifetime-to-date subscribersGained per video via the YouTube Analytics
    API (scope yt-analytics.readonly -- already requested at OAuth time, see
    api.py's youtube oauth_url, but the underlying Google Cloud API also
    needs a one-time manual "Enable" in Cloud Console, a project-level
    toggle separate from the OAuth scope; confirmed live 2026-08-09).
    subscribers_gained on VideoAnalyticsSnapshot is a cumulative per-video
    total re-fetched on every sync (same as views/likes/comments), not a
    delta -- _channel_stats() only ever sums the LATEST snapshot per video.
    Never raises: an API-disabled/quota/network failure just leaves
    subscribers_gained None, the same manual-first fallback already used for
    watch time/revenue."""
    if not video_ids:
        return {}
    try:
        resp = requests.get(
            "https://youtubeanalytics.googleapis.com/v2/reports",
            params={
                "ids": "channel==MINE",
                "startDate": "2020-01-01",
                "endDate": datetime.utcnow().strftime("%Y-%m-%d"),
                "metrics": "subscribersGained",
                "dimensions": "video",
                "filters": "video==" + ",".join(video_ids[:50]),
                "maxResults": 50,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if not resp.ok:
            return {}
        rows = (resp.json() or {}).get("rows") or []
        return {r[0]: int(r[1]) for r in rows if len(r) >= 2}
    except Exception:
        return {}


@analytics_api.route("/channels/<int:channel_id>/analytics/sync", methods=["POST"])
@require_auth
def sync_channel_analytics(channel_id: int):
    """Pull views/likes/comments for this channel's published videos via the
    YouTube Data API (scope youtube.readonly, already granted), plus
    subscribers_gained per video via the YouTube Analytics API. Creates new
    snapshots (data_source='youtube_api'); never touches manual records."""
    db = SessionLocal()
    try:
        c = _own_channel(db, channel_id)
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        if not c.youtube_channel_id or c.youtube_connection_status != "connected":
            return jsonify({"error": "Channel has no connected YouTube channel"}), 409
        pubs = (
            db.query(Publication)
            .filter(Publication.channel_id == c.id,
                    Publication.status == "published",
                    Publication.youtube_video_id.isnot(None))
            # Most-recent-first: the YouTube Data API call below only takes
            # the first 50 (its own hard limit). Without this ordering, a
            # channel with >50 published videos gets an arbitrary DB-order
            # slice -- in practice that stayed pinned to the OLDEST 50
            # forever once the channel grew past 50, so newer videos never
            # synced (real bug found 2026-08-21 while investigating a
            # subscriber-drop report).
            .order_by(Publication.published_at.desc())
            .all()
        )
        if not pubs:
            return jsonify({"error": "No published videos with YouTube IDs on this channel"}), 409
        from app_models import SocialAccount
        acc = db.query(SocialAccount).filter_by(id=c.youtube_social_account_id).first() if c.youtube_social_account_id else _user_youtube_account(db)
        token = _valid_account_token(db, acc) if acc else None
        if not token:
            return jsonify({"error": "YouTube token unavailable or revoked; reconnect the channel"}), 409

        ids = [p.youtube_video_id for p in pubs]
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics", "id": ",".join(ids[:50]), "maxResults": 50},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
        except requests.RequestException as exc:
            return jsonify({"error": f"network_error: {str(exc)[:200]}"}), 502
        if resp.status_code in (401,):
            return jsonify({"error": "YouTube token revoked or expired; reconnect the channel"}), 409
        if resp.status_code == 403:
            detail = ""
            try:
                detail = str(((resp.json() or {}).get("error") or {}).get("message") or "")[:200]
            except Exception:
                pass
            if "quota" in detail.lower():
                return jsonify({"error": f"quota_exceeded: {detail}"}), 429
            return jsonify({"error": f"forbidden: {detail}"}), 502
        if not resp.ok:
            return jsonify({"error": f"youtube_api_{resp.status_code}"}), 502

        items = {str(it.get("id")): it.get("statistics") or {} for it in (resp.json() or {}).get("items") or []}
        subs_by_video = _fetch_subscribers_by_video(token, ids)
        captured = datetime.utcnow().replace(microsecond=0)
        created = []
        for p in pubs:
            stats = items.get(p.youtube_video_id)
            if stats is None:
                continue
            def _n(key):
                raw = stats.get(key)
                try:
                    return int(raw) if raw is not None else None
                except (TypeError, ValueError):
                    return None
            snap = VideoAnalyticsSnapshot(
                channel_id=c.id,
                publication_id=p.id,
                youtube_video_id=p.youtube_video_id,
                data_source="youtube_api",
                captured_at=captured,
                views=_n("viewCount"),
                likes=_n("likeCount"),
                comments=_n("commentCount"),
                subscribers_gained=subs_by_video.get(p.youtube_video_id),
                raw_data_json=json.dumps(stats, ensure_ascii=False)[:4000],
            )
            db.add(snap)
            created.append(p.youtube_video_id)
        c.youtube_last_verified_at = captured
        db.commit()
        record_cost(provider="google", model="youtube-data-api", operation_type="analytics_sync",
                    channel_id=c.id, request_id=f"sync:{c.id}:{captured.isoformat()}", db=db)
        return jsonify({"synced": len(created), "captured_at": _iso(captured), "video_ids": created})
    finally:
        db.close()


# ------------------------------------------------------------- aggregation

def _period_start(period: str):
    days = {"7": 7, "30": 30, "90": 90}.get(str(period))
    return (datetime.utcnow() - timedelta(days=days)) if days else None


def _latest_snapshots_per_publication(db, channel_id: int, since):
    q = db.query(VideoAnalyticsSnapshot).filter(VideoAnalyticsSnapshot.channel_id == channel_id)
    if since:
        q = q.filter(VideoAnalyticsSnapshot.captured_at >= since)
    rows = q.order_by(VideoAnalyticsSnapshot.captured_at.asc()).all()
    latest = {}
    for r in rows:
        latest[r.publication_id] = r  # ascending order -> last wins
    return list(latest.values())


def _channel_stats(db, c: Channel, period: str) -> dict:
    since = _period_start(period)
    pubs_q = db.query(Publication).filter(Publication.channel_id == c.id)
    if since:
        pubs_q = pubs_q.filter(Publication.created_at >= since)
    pubs = pubs_q.all()
    published = [p for p in pubs if p.status == "published"]
    last_pub = max((p.published_at for p in published if p.published_at), default=None)

    snaps = _latest_snapshots_per_publication(db, c.id, since)
    views = [s.views for s in snaps if s.views is not None]
    likes = [s.likes for s in snaps if s.likes is not None]
    comments = [s.comments for s in snaps if s.comments is not None]
    subs = [s.subscribers_gained for s in snaps if s.subscribers_gained is not None]
    watch = [s.watch_time_minutes for s in snaps if s.watch_time_minutes is not None]
    avp = [s.average_view_percentage for s in snaps if s.average_view_percentage is not None]
    revenue = [s.estimated_revenue for s in snaps if s.estimated_revenue is not None]

    cost_q = db.query(AICostRecord).filter(AICostRecord.channel_id == c.id, AICostRecord.status == "success")
    if since:
        cost_q = cost_q.filter(AICostRecord.created_at >= since)
    cost_rows = cost_q.all()
    known_costs = [(r.actual_cost if r.actual_cost is not None else r.estimated_cost) for r in cost_rows]
    known_costs = [x for x in known_costs if x is not None]
    ai_cost = round(sum(known_costs), 4) if known_costs else (0.0 if cost_rows else None)

    total_views = sum(views) if views else None
    n_videos = len(published)
    engagement = None
    if total_views and views and (likes or comments):
        inter = sum(likes) + sum(comments)
        engagement = round(inter / total_views * 100, 2)
    best = max(snaps, key=lambda s: (s.views or -1), default=None)
    worst = min([s for s in snaps if s.views is not None], key=lambda s: s.views, default=None)

    def _per_video(total):
        return round(total / n_videos, 2) if (total is not None and n_videos) else None

    total_revenue = round(sum(revenue), 2) if revenue else None
    return {
        "channel_id": c.id,
        "name": c.name,
        "niche": c.niche,
        "status": c.status,
        "period": period,
        "publications": len(pubs),
        "published_videos": n_videos,
        "last_published_at": _iso(last_pub),
        "videos_with_data": len(snaps),
        "total_views": total_views,
        "avg_views": round(statistics.mean(views), 1) if views else None,
        "median_views": statistics.median(views) if views else None,
        "max_views": max(views) if views else None,
        "min_views": min(views) if views else None,
        "likes": sum(likes) if likes else None,
        "comments": sum(comments) if comments else None,
        "engagement_rate": engagement,
        "subscribers_gained": sum(subs) if subs else None,
        "watch_time_minutes": round(sum(watch), 1) if watch else None,
        "avg_view_percentage": round(statistics.mean(avp), 1) if avp else None,
        "estimated_revenue": total_revenue,
        "ai_cost": ai_cost,
        "views_per_video": _per_video(total_views),
        "subscribers_per_video": _per_video(sum(subs) if subs else None),
        "cost_per_video": _per_video(ai_cost),
        "cost_per_1k_views": round(ai_cost / total_views * 1000, 4) if (ai_cost is not None and total_views) else None,
        "views_per_dollar": round(total_views / ai_cost, 1) if (total_views is not None and ai_cost) else None,
        "revenue_per_video": _per_video(total_revenue),
        "net_result": round((total_revenue or 0) - ai_cost, 2) if (total_revenue is not None and ai_cost is not None) else None,
        "best_video": {"publication_id": best.publication_id, "views": best.views, "youtube_video_id": best.youtube_video_id} if best and best.views is not None else None,
        "worst_video": {"publication_id": worst.publication_id, "views": worst.views, "youtube_video_id": worst.youtube_video_id} if worst else None,
    }


@analytics_api.route("/analytics/channels", methods=["GET"])
@require_auth
def channels_comparison():
    period = str(request.args.get("period") or "all")
    if period not in {"7", "30", "90", "all"}:
        return jsonify({"error": "period must be 7, 30, 90 or all"}), 400
    db = SessionLocal()
    try:
        channels = (
            db.query(Channel)
            .filter(Channel.owner_user_id == g.current_user.id, Channel.status != "archived")
            .order_by(Channel.created_at.asc())
            .limit(10)
            .all()
        )
        return jsonify({"period": period, "channels": [_channel_stats(db, c, period) for c in channels]})
    finally:
        db.close()


# ------------------------------------------------------------------- costs

@analytics_api.route("/analytics/costs", methods=["GET"])
@require_auth
def costs_overview():
    db = SessionLocal()
    try:
        summary = spent_summary(db)
        q = (
            db.query(AICostRecord)
            .order_by(AICostRecord.created_at.desc())
            .limit(100)
        )
        channel_id = request.args.get("channel_id", type=int)
        if channel_id:
            q = q.filter(AICostRecord.channel_id == channel_id)
        rows = q.all()
        records = [{
            "id": r.id,
            "channel_id": r.channel_id,
            "project_id": r.project_id,
            "provider": r.provider,
            "model": r.model,
            "operation_type": r.operation_type,
            "input_units": r.input_units,
            "output_units": r.output_units,
            "estimated_cost": r.estimated_cost,
            "actual_cost": r.actual_cost,
            "currency": r.currency,
            "status": r.status,
            "error": (r.error or "")[:200] or None,
            "created_at": _iso(r.created_at),
        } for r in rows]
        failed = sum(1 for r in rows if r.status == "failed")
        return jsonify({"summary": summary, "budgets": budgets(), "failed_recent": failed, "records": records})
    finally:
        db.close()
