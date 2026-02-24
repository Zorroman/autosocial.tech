from __future__ import annotations

import json
import math
import statistics
from datetime import date, datetime, timedelta
from typing import Any

import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from facebook_api import list_pages
from saas_models import (
    AiScoreDaily,
    AiScoreDailyV2,
    Campaign,
    ConnectedAccount,
    Forecast,
    ContentBrief,
    ContentDraft,
    ContentItem,
    ContentMetricDaily,
    ContentPlan,
    Post,
    SocialAccount,
)
from saas_services import decrypt_meta_token


def _utcnow() -> datetime:
    return datetime.utcnow()


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo:
            return parsed.astimezone(tz=None).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return 0
        try:
            return int(float(txt))
        except Exception:
            return 0
    return 0


def _parse_yt_duration_seconds(duration: str) -> int:
    # ISO8601 duration like PT1H2M3S
    txt = str(duration or "").strip().upper()
    if not txt.startswith("PT"):
        return 0
    txt = txt[2:]
    cur = ""
    total = 0
    for ch in txt:
        if ch.isdigit():
            cur += ch
            continue
        value = _to_int(cur)
        cur = ""
        if ch == "H":
            total += value * 3600
        elif ch == "M":
            total += value * 60
        elif ch == "S":
            total += value
    return total


def _upsert_connected_account(
    db: Session,
    *,
    user_id: int,
    platform: str,
    external_id: str,
    display_name: str | None,
    access_token: str | None,
    refresh_token: str | None,
    token_expires_at: datetime | None,
) -> ConnectedAccount:
    row = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.platform == platform,
            ConnectedAccount.external_id == external_id,
        )
        .first()
    )
    if not row:
        row = ConnectedAccount(
            user_id=user_id,
            platform=platform,
            external_id=external_id,
        )
        db.add(row)
        db.flush()
    row.display_name = display_name
    row.access_token = access_token
    row.refresh_token = refresh_token
    row.token_expires_at = token_expires_at
    row.updated_at = _utcnow()
    return row


def _upsert_content_item(
    db: Session,
    *,
    user_id: int,
    platform: str,
    external_id: str,
    account_id: int,
    content_type: str,
    title: str | None,
    message: str | None,
    url: str | None,
    published_at: datetime | None,
) -> ContentItem:
    row = (
        db.query(ContentItem)
        .filter(
            ContentItem.user_id == user_id,
            ContentItem.platform == platform,
            ContentItem.external_id == external_id,
        )
        .first()
    )
    if not row:
        row = ContentItem(
            user_id=user_id,
            platform=platform,
            external_id=external_id,
            account_id=account_id,
        )
        db.add(row)
        db.flush()
    row.account_id = account_id
    row.content_type = content_type or "post"
    row.title = (title or "")[:500] or None
    row.message = message
    row.url = url
    row.published_at = published_at
    row.updated_at = _utcnow()
    return row


def _upsert_daily_metric(db: Session, *, content_item_id: int, day: date, metrics: dict[str, int]) -> ContentMetricDaily:
    row = (
        db.query(ContentMetricDaily)
        .filter(ContentMetricDaily.content_item_id == content_item_id, ContentMetricDaily.day == day)
        .first()
    )
    if not row:
        row = ContentMetricDaily(content_item_id=content_item_id, day=day)
        db.add(row)
        db.flush()
    row.impressions = _to_int(metrics.get("impressions"))
    row.reach = _to_int(metrics.get("reach"))
    row.views = _to_int(metrics.get("views"))
    row.clicks = _to_int(metrics.get("clicks"))
    row.likes = _to_int(metrics.get("likes"))
    row.comments = _to_int(metrics.get("comments"))
    row.shares = _to_int(metrics.get("shares"))
    row.watch_time_seconds = _to_int(metrics.get("watch_time_seconds"))
    row.updated_at = _utcnow()
    return row


def _meta_post_metrics(post_id: str, page_access_token: str) -> dict[str, int]:
    metrics = {
        "impressions": 0,
        "reach": 0,
        "views": 0,
        "clicks": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "watch_time_seconds": 0,
    }
    insight_names = ",".join(
        [
            "post_impressions",
            "post_impressions_unique",
            "post_clicks",
            "post_reactions_like_total",
            "post_comments",
            "post_shares",
            "post_video_views",
        ]
    )
    resp = requests.get(
        f"https://graph.facebook.com/v20.0/{post_id}/insights",
        params={"metric": insight_names, "access_token": page_access_token},
        timeout=20,
    )
    if resp.ok:
        payload = resp.json() if resp.content else {}
        for item in payload.get("data") or []:
            name = str(item.get("name") or "")
            values = item.get("values") or []
            value = 0
            if values and isinstance(values[0], dict):
                raw = values[0].get("value")
                if isinstance(raw, dict):
                    value = sum(_to_int(v) for v in raw.values())
                else:
                    value = _to_int(raw)
            if name == "post_impressions":
                metrics["impressions"] = value
            elif name == "post_impressions_unique":
                metrics["reach"] = value
            elif name == "post_clicks":
                metrics["clicks"] = value
            elif name == "post_reactions_like_total":
                metrics["likes"] = value
            elif name == "post_comments":
                metrics["comments"] = value
            elif name == "post_shares":
                metrics["shares"] = value
            elif name == "post_video_views":
                metrics["views"] = value

    fallback = requests.get(
        f"https://graph.facebook.com/v20.0/{post_id}",
        params={
            "fields": "reactions.summary(true),comments.summary(true),shares",
            "access_token": page_access_token,
        },
        timeout=20,
    )
    if fallback.ok:
        data = fallback.json() if fallback.content else {}
        if metrics["likes"] <= 0:
            metrics["likes"] = _to_int(((data.get("reactions") or {}).get("summary") or {}).get("total_count"))
        if metrics["comments"] <= 0:
            metrics["comments"] = _to_int(((data.get("comments") or {}).get("summary") or {}).get("total_count"))
        if metrics["shares"] <= 0:
            metrics["shares"] = _to_int((data.get("shares") or {}).get("count"))

    if metrics["views"] <= 0:
        metrics["views"] = max(metrics["impressions"], metrics["reach"])
    if metrics["reach"] <= 0:
        metrics["reach"] = max(metrics["impressions"], metrics["views"])
    return metrics


def _sync_meta_account(db: Session, row: SocialAccount, *, max_items: int) -> int:
    if not row.token_encrypted:
        return 0
    user_token = decrypt_meta_token(row.token_encrypted)
    pages = list_pages(user_token, include_page_access_token=True)
    if pages.get("error"):
        raise RuntimeError(str((pages.get("error") or {}).get("message") or "Meta pages read failed"))
    pages_data = pages.get("data") or []
    if not pages_data:
        return 0
    selected = next((p for p in pages_data if str(p.get("id") or "") == str(row.page_id or "")), pages_data[0])
    page_id = str(selected.get("id") or row.page_id or "").strip()
    if not page_id:
        return 0
    page_name = str(selected.get("name") or row.page_name or "Meta Page")
    page_access_token = str(selected.get("access_token") or user_token).strip()

    account = _upsert_connected_account(
        db,
        user_id=row.user_id,
        platform="meta",
        external_id=page_id,
        display_name=page_name,
        access_token=row.token_encrypted,
        refresh_token=None,
        token_expires_at=row.token_expires_at,
    )

    feed_resp = requests.get(
        f"https://graph.facebook.com/v20.0/{page_id}/posts",
        params={
            "fields": "id,message,created_time,permalink_url,attachments{media_type,type}",
            "limit": max_items,
            "access_token": page_access_token,
        },
        timeout=20,
    )
    if not feed_resp.ok:
        details = ""
        try:
            details = str((feed_resp.json() or {}).get("error", {}).get("message") or "")
        except Exception:
            details = feed_resp.text[:300]
        raise RuntimeError(f"Meta feed read failed: {details}")
    feed = feed_resp.json() if feed_resp.content else {}
    items = feed.get("data") or []
    stored = 0
    today = _utcnow().date()
    for item in items:
        post_id = str(item.get("id") or "").strip()
        if not post_id:
            continue
        message = str(item.get("message") or "").strip()
        attachment = ((item.get("attachments") or {}).get("data") or [{}])[0]
        attachment_type = str(attachment.get("media_type") or attachment.get("type") or "").lower()
        content_type = "video" if "video" in attachment_type else "post"
        title = message.splitlines()[0].strip() if message else "Meta post"
        post = _upsert_content_item(
            db,
            user_id=row.user_id,
            platform="meta",
            external_id=post_id,
            account_id=account.id,
            content_type=content_type,
            title=title,
            message=message,
            url=str(item.get("permalink_url") or ""),
            published_at=_parse_dt(item.get("created_time")),
        )
        metrics = _meta_post_metrics(post_id, page_access_token)
        _upsert_daily_metric(db, content_item_id=post.id, day=today, metrics=metrics)
        stored += 1
    return stored


def _sync_youtube_account(db: Session, row: SocialAccount, *, max_items: int) -> int:
    if not row.token_encrypted:
        return 0
    access_token = decrypt_meta_token(row.token_encrypted)
    headers = {"Authorization": f"Bearer {access_token}"}
    channel_resp = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "snippet,contentDetails", "mine": "true", "maxResults": 1},
        headers=headers,
        timeout=20,
    )
    if not channel_resp.ok:
        details = ""
        try:
            details = str((channel_resp.json() or {}).get("error", {}).get("message") or "")
        except Exception:
            details = channel_resp.text[:300]
        raise RuntimeError(f"YouTube channel read failed: {details}")
    channel_payload = channel_resp.json() if channel_resp.content else {}
    channels = channel_payload.get("items") or []
    if not channels:
        return 0
    channel = channels[0]
    channel_id = str(channel.get("id") or row.page_id or "").strip()
    snippet = channel.get("snippet") or {}
    channel_name = str(snippet.get("title") or row.page_name or "YouTube channel")
    uploads_playlist = str(((channel.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads") or "").strip()
    if not uploads_playlist:
        return 0

    account = _upsert_connected_account(
        db,
        user_id=row.user_id,
        platform="youtube",
        external_id=channel_id or f"yt-{row.user_id}",
        display_name=channel_name,
        access_token=row.token_encrypted,
        refresh_token=None,
        token_expires_at=row.token_expires_at,
    )

    playlist_resp = requests.get(
        "https://www.googleapis.com/youtube/v3/playlistItems",
        params={"part": "snippet,contentDetails", "playlistId": uploads_playlist, "maxResults": min(max_items, 50)},
        headers=headers,
        timeout=20,
    )
    if not playlist_resp.ok:
        return 0
    playlist_payload = playlist_resp.json() if playlist_resp.content else {}
    playlist_items = playlist_payload.get("items") or []
    video_ids = []
    for item in playlist_items:
        video_id = str(((item.get("contentDetails") or {}).get("videoId") or "").strip())
        if video_id:
            video_ids.append(video_id)
    if not video_ids:
        return 0

    videos_resp = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,statistics,contentDetails", "id": ",".join(video_ids)},
        headers=headers,
        timeout=20,
    )
    if not videos_resp.ok:
        return 0
    videos_payload = videos_resp.json() if videos_resp.content else {}
    videos = videos_payload.get("items") or []
    today = _utcnow().date()
    stored = 0
    for video in videos:
        video_id = str(video.get("id") or "").strip()
        if not video_id:
            continue
        snippet = video.get("snippet") or {}
        stats = video.get("statistics") or {}
        details = video.get("contentDetails") or {}
        duration_seconds = _parse_yt_duration_seconds(str(details.get("duration") or ""))
        content_type = "video" if duration_seconds > 65 else "reel"
        published_at = _parse_dt(snippet.get("publishedAt"))
        title = str(snippet.get("title") or "YouTube video")
        message = str(snippet.get("description") or "")
        url = f"https://www.youtube.com/watch?v={video_id}"
        item = _upsert_content_item(
            db,
            user_id=row.user_id,
            platform="youtube",
            external_id=video_id,
            account_id=account.id,
            content_type=content_type,
            title=title,
            message=message,
            url=url,
            published_at=published_at,
        )
        view_count = _to_int(stats.get("viewCount"))
        metrics = {
            "impressions": 0,
            "reach": view_count,
            "views": view_count,
            "clicks": 0,
            "likes": _to_int(stats.get("likeCount")),
            "comments": _to_int(stats.get("commentCount")),
            "shares": 0,
            "watch_time_seconds": 0,
        }
        _upsert_daily_metric(db, content_item_id=item.id, day=today, metrics=metrics)
        stored += 1
    return stored


def sync_dashboard_metrics_for_user(db: Session, user_id: int, *, max_items_per_account: int = 25) -> dict[str, Any]:
    rows = (
        db.query(SocialAccount)
        .filter(SocialAccount.user_id == user_id, SocialAccount.status.in_(["connected", "connected_ready"]))
        .order_by(SocialAccount.updated_at.desc(), SocialAccount.created_at.desc())
        .all()
    )
    meta_items = 0
    youtube_items = 0
    errors: list[str] = []

    for row in rows:
        provider = str(row.provider or "").strip().lower()
        try:
            if provider == "meta":
                meta_items += _sync_meta_account(db, row, max_items=max_items_per_account)
            elif provider == "youtube":
                youtube_items += _sync_youtube_account(db, row, max_items=max_items_per_account)
        except Exception as exc:
            errors.append(f"{provider}: {str(exc)}")

    # Persist fresh analytics snapshots right after sync.
    try:
        ai_payload = dashboard_ai_score(db, user_id, days=30, persist=True)
        forecast_7 = dashboard_forecast(db, user_id, horizon=7, days=90, persist=True)
        forecast_30 = dashboard_forecast(db, user_id, horizon=30, days=90, persist=True)
    except Exception as exc:
        errors.append(f"analytics: {str(exc)}")
        ai_payload = {"current": 0}
        forecast_7 = {"totals": {"reach": 0, "views": 0, "engagement_rate_avg": 0}}
        forecast_30 = {"totals": {"reach": 0, "views": 0, "engagement_rate_avg": 0}}

    db.commit()
    return {
        "meta_items": meta_items,
        "youtube_items": youtube_items,
        "errors": errors,
        "ai_score": ai_payload.get("current", 0),
        "forecast_7d_reach": (forecast_7.get("totals") or {}).get("reach", 0),
        "forecast_30d_reach": (forecast_30.get("totals") or {}).get("reach", 0),
    }


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _score_by_curve(value: float, points: list[tuple[float, float]]) -> float:
    x = float(value)
    if not points:
        return 0.0
    if x <= points[0][0]:
        return float(points[0][1])
    for idx in range(1, len(points)):
        x0, y0 = points[idx - 1]
        x1, y1 = points[idx]
        if x <= x1:
            if x1 <= x0:
                return float(y1)
            ratio = (x - x0) / (x1 - x0)
            return float(y0 + ratio * (y1 - y0))
    return float(points[-1][1])


def _window_totals(db: Session, user_id: int, start_day: date, end_day: date) -> dict[str, int]:
    row = (
        db.query(
            func.coalesce(func.sum(ContentMetricDaily.reach), 0),
            func.coalesce(func.sum(ContentMetricDaily.views), 0),
            func.coalesce(func.sum(ContentMetricDaily.clicks), 0),
            func.coalesce(func.sum(ContentMetricDaily.likes), 0),
            func.coalesce(func.sum(ContentMetricDaily.comments), 0),
            func.coalesce(func.sum(ContentMetricDaily.shares), 0),
            func.coalesce(func.sum(ContentMetricDaily.impressions), 0),
        )
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(
            ContentItem.user_id == user_id,
            ContentMetricDaily.day >= start_day,
            ContentMetricDaily.day <= end_day,
        )
        .first()
    )
    return {
        "reach": _to_int(row[0] if row else 0),
        "views": _to_int(row[1] if row else 0),
        "clicks": _to_int(row[2] if row else 0),
        "likes": _to_int(row[3] if row else 0),
        "comments": _to_int(row[4] if row else 0),
        "shares": _to_int(row[5] if row else 0),
        "impressions": _to_int(row[6] if row else 0),
    }


def _daily_series(db: Session, user_id: int, start_day: date, end_day: date) -> dict[str, dict[str, int]]:
    rows = (
        db.query(
            ContentMetricDaily.day,
            func.coalesce(func.sum(ContentMetricDaily.reach), 0),
            func.coalesce(func.sum(ContentMetricDaily.views), 0),
            func.coalesce(func.sum(ContentMetricDaily.clicks), 0),
            func.coalesce(func.sum(ContentMetricDaily.likes), 0),
            func.coalesce(func.sum(ContentMetricDaily.comments), 0),
            func.coalesce(func.sum(ContentMetricDaily.shares), 0),
        )
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(
            ContentItem.user_id == user_id,
            ContentMetricDaily.day >= start_day,
            ContentMetricDaily.day <= end_day,
        )
        .group_by(ContentMetricDaily.day)
        .order_by(ContentMetricDaily.day.asc())
        .all()
    )
    out: dict[str, dict[str, int]] = {}
    for day, reach, views, clicks, likes, comments, shares in rows:
        out[day.isoformat()] = {
            "reach": _to_int(reach),
            "views": _to_int(views),
            "clicks": _to_int(clicks),
            "likes": _to_int(likes),
            "comments": _to_int(comments),
            "shares": _to_int(shares),
        }
    return out


def _performance_score(totals: dict[str, int]) -> tuple[float, dict[str, float]]:
    reach = max(_to_int(totals.get("reach")), 1)
    interactions = _to_int(totals.get("likes")) + _to_int(totals.get("comments")) + _to_int(totals.get("shares"))
    engagement_rate = interactions / reach
    ctr_raw = _to_int(totals.get("clicks")) / reach
    views_rate = _to_int(totals.get("views")) / reach

    eng_score = _score_by_curve(engagement_rate, [(0.0, 0.0), (0.02, 50.0), (0.05, 80.0), (0.10, 100.0)])
    ctr_score = _score_by_curve(ctr_raw, [(0.0, 0.0), (0.005, 50.0), (0.015, 80.0), (0.03, 100.0)])
    views_score = _score_by_curve(views_rate, [(0.0, 0.0), (0.3, 50.0), (0.7, 80.0), (1.2, 100.0)])

    clicks_available = _to_int(totals.get("clicks")) > 0
    if clicks_available:
        score = 0.55 * eng_score + 0.25 * ctr_score + 0.20 * views_score
    else:
        # Redistribute CTR weight proportionally to engagement/views weights.
        eng_weight = 0.55 / 0.75
        views_weight = 0.20 / 0.75
        score = eng_weight * eng_score + views_weight * views_score
    return (
        _clamp(score, 0.0, 100.0),
        {
            "engagement_rate": engagement_rate,
            "ctr": ctr_raw,
            "views_rate": views_rate,
            "engagement_score": _clamp(eng_score, 0.0, 100.0),
            "ctr_score": _clamp(ctr_score, 0.0, 100.0),
            "views_rate_score": _clamp(views_score, 0.0, 100.0),
            "ctr_available": clicks_available,
        },
    )


def _consistency_score(series: dict[str, dict[str, int]]) -> tuple[float, dict[str, int]]:
    active_days = 0
    for row in series.values():
        interactions = _to_int(row.get("likes")) + _to_int(row.get("comments")) + _to_int(row.get("shares"))
        if _to_int(row.get("reach")) > 0 or _to_int(row.get("views")) > 0 or interactions > 0:
            active_days += 1
    if active_days <= 2:
        score = 10.0
    elif active_days <= 5:
        score = 30.0
    elif active_days <= 9:
        score = 55.0
    elif active_days <= 14:
        score = 75.0
    else:
        score = 100.0
    return score, {"active_days": active_days}


def _growth_score(db: Session, user_id: int, reference_day: date) -> tuple[float, dict[str, Any]]:
    start_14 = reference_day - timedelta(days=13)
    series = _daily_series(db, user_id, start_14, reference_day)
    available_days = len(series.keys())
    if available_days < 14:
        return 50.0, {"growth_ratio": 0.0, "needs_more_data": True, "available_days": available_days, "driver": "reach"}

    ordered_days = [(start_14 + timedelta(days=i)).isoformat() for i in range(14)]
    day_rows = [series.get(k, {"reach": 0, "views": 0}) for k in ordered_days]
    use_views = sum(_to_int(r.get("reach")) for r in day_rows) <= 0
    metric_key = "views" if use_views else "reach"
    prev = sum(_to_int(r.get(metric_key)) for r in day_rows[:7]) / 7.0
    last = sum(_to_int(r.get(metric_key)) for r in day_rows[7:]) / 7.0
    growth_ratio = (last - prev) / max(prev, 1.0)
    if growth_ratio <= -0.2:
        score = 10.0
    elif growth_ratio < 0.0:
        score = 40.0
    elif growth_ratio < 0.2:
        score = 70.0
    elif growth_ratio < 0.6:
        score = 90.0
    else:
        score = 100.0
    return score, {
        "growth_ratio": growth_ratio,
        "needs_more_data": False,
        "available_days": available_days,
        "driver": metric_key,
        "avg_prev_7": prev,
        "avg_last_7": last,
    }


def _optimization_score(db: Session, user_id: int) -> tuple[float, dict[str, Any]]:
    tone_present = (
        db.query(func.count(ContentBrief.id))
        .filter(ContentBrief.user_id == user_id, ContentBrief.tone.isnot(None), func.length(func.trim(ContentBrief.tone)) > 0)
        .scalar()
        or 0
    ) > 0
    niche_present = (
        (db.query(func.count(ContentPlan.id)).filter(ContentPlan.user_id == user_id, ContentPlan.business_type.isnot(None), func.length(func.trim(ContentPlan.business_type)) > 0).scalar() or 0)
        + (db.query(func.count(Post.id)).filter(Post.user_id == user_id, Post.category.isnot(None), func.length(func.trim(Post.category)) > 0).scalar() or 0)
    ) > 0
    audience_present = (
        (db.query(func.count(Campaign.id)).filter(Campaign.user_id == user_id, Campaign.objective.isnot(None), func.length(func.trim(Campaign.objective)) > 0).scalar() or 0)
        + (db.query(func.count(ContentPlan.id)).filter(ContentPlan.user_id == user_id, ContentPlan.goal.isnot(None), func.length(func.trim(ContentPlan.goal)) > 0).scalar() or 0)
    ) > 0
    offer_present = (
        (db.query(func.count(ContentBrief.id)).filter(ContentBrief.user_id == user_id, ContentBrief.offer.isnot(None), func.length(func.trim(ContentBrief.offer)) > 0).scalar() or 0)
        + (db.query(func.count(Campaign.id)).filter(Campaign.user_id == user_id, Campaign.offer.isnot(None), func.length(func.trim(Campaign.offer)) > 0).scalar() or 0)
    ) > 0
    profile_fields = [tone_present, niche_present, audience_present, offer_present]
    profile_score = (sum(1 for v in profile_fields if v) / 4.0) * 100.0

    connected_platforms = (
        db.query(func.count(func.distinct(SocialAccount.provider)))
        .filter(SocialAccount.user_id == user_id, SocialAccount.status.in_(["connected", "connected_ready"]))
        .scalar()
        or 0
    )
    if connected_platforms <= 0:
        platform_score = 0.0
    elif connected_platforms == 1:
        platform_score = 60.0
    else:
        platform_score = 100.0

    scheduled_count = (
        db.query(func.count(Post.id))
        .filter(
            Post.user_id == user_id,
            (Post.status == "scheduled") | (Post.schedule_at.isnot(None)),
        )
        .scalar()
        or 0
    )
    schedule_score = _clamp((scheduled_count / 5.0) * 100.0, 0.0, 100.0)

    drafts_total = (
        db.query(func.count(ContentDraft.id))
        .join(ContentBrief, ContentBrief.id == ContentDraft.brief_id)
        .filter(ContentBrief.user_id == user_id)
        .scalar()
        or 0
    )
    drafts_with_cta = (
        db.query(func.count(ContentDraft.id))
        .join(ContentBrief, ContentBrief.id == ContentDraft.brief_id)
        .filter(ContentBrief.user_id == user_id, ContentDraft.cta.isnot(None), func.length(func.trim(ContentDraft.cta)) > 0)
        .scalar()
        or 0
    )
    plan_total = db.query(func.count(ContentPlan.id)).filter(ContentPlan.user_id == user_id).scalar() or 0
    plan_with_cta = (
        db.query(func.count(ContentPlan.id))
        .filter(ContentPlan.user_id == user_id, ContentPlan.cta.isnot(None), func.length(func.trim(ContentPlan.cta)) > 0)
        .scalar()
        or 0
    )
    post_total = db.query(func.count(Post.id)).filter(Post.user_id == user_id).scalar() or 0
    cta_patterns = ["%напиш%", "%перейд%", "%закаж%", "%куп%", "%узнай%", "%click%", "%subscribe%", "%book%"]
    post_with_cta = (
        db.query(func.count(Post.id))
        .filter(
            Post.user_id == user_id,
            Post.generated_text.isnot(None),
            (
                Post.generated_text.ilike(cta_patterns[0])
                | Post.generated_text.ilike(cta_patterns[1])
                | Post.generated_text.ilike(cta_patterns[2])
                | Post.generated_text.ilike(cta_patterns[3])
                | Post.generated_text.ilike(cta_patterns[4])
                | Post.generated_text.ilike(cta_patterns[5])
                | Post.generated_text.ilike(cta_patterns[6])
                | Post.generated_text.ilike(cta_patterns[7])
            ),
        )
        .scalar()
        or 0
    )
    cta_total = drafts_total + plan_total + post_total
    cta_with = drafts_with_cta + plan_with_cta + post_with_cta
    cta_share = (cta_with / cta_total) if cta_total > 0 else 0.0
    cta_score = _clamp((cta_share / 0.70) * 100.0, 0.0, 100.0)

    score = (profile_score + platform_score + schedule_score + cta_score) / 4.0
    return _clamp(score, 0.0, 100.0), {
        "profile_completion": _clamp(profile_score, 0.0, 100.0),
        "profile_fields": {
            "tone": tone_present,
            "niche": niche_present,
            "audience": audience_present,
            "offer": offer_present,
        },
        "connected_platforms": int(connected_platforms),
        "platform_score": _clamp(platform_score, 0.0, 100.0),
        "scheduled_count": int(scheduled_count),
        "schedule_score": _clamp(schedule_score, 0.0, 100.0),
        "cta_coverage": cta_share,
        "cta_score": _clamp(cta_score, 0.0, 100.0),
    }


def _upsert_ai_score_daily(db: Session, user_id: int, snapshot_day: date, snapshot: dict[str, Any]) -> None:
    row = db.query(AiScoreDaily).filter(AiScoreDaily.user_id == user_id, AiScoreDaily.day == snapshot_day).first()
    if not row:
        row = AiScoreDaily(user_id=user_id, day=snapshot_day)
        db.add(row)
        db.flush()
    row.ai_score = float(snapshot.get("ai_score") or 0.0)
    row.performance = float(snapshot.get("performance") or 0.0)
    row.consistency = float(snapshot.get("consistency") or 0.0)
    row.growth = float(snapshot.get("growth") or 0.0)
    row.optimization = float(snapshot.get("optimization") or 0.0)


def _compute_ai_score_snapshot(
    db: Session,
    user_id: int,
    *,
    reference_day: date,
    window_days: int = 30,
    persist: bool = False,
) -> dict[str, Any]:
    window_days = max(7, min(int(window_days or 30), 90))
    start_day = reference_day - timedelta(days=window_days - 1)
    totals = _window_totals(db, user_id, start_day, reference_day)
    series = _daily_series(db, user_id, start_day, reference_day)

    performance, performance_meta = _performance_score(totals)
    consistency, consistency_meta = _consistency_score(series)
    growth, growth_meta = _growth_score(db, user_id, reference_day)
    optimization, optimization_meta = _optimization_score(db, user_id)

    ai_score = _clamp(
        0.40 * performance + 0.25 * consistency + 0.20 * growth + 0.15 * optimization,
        0.0,
        100.0,
    )
    snapshot = {
        "day": reference_day.isoformat(),
        "ai_score": round(ai_score, 2),
        "performance": round(performance, 2),
        "consistency": round(consistency, 2),
        "growth": round(growth, 2),
        "optimization": round(optimization, 2),
        "needs_more_data": bool(growth_meta.get("needs_more_data")),
        "breakdown": {
            "performance": {**performance_meta, "score": round(performance, 2)},
            "consistency": {**consistency_meta, "score": round(consistency, 2)},
            "growth": {**growth_meta, "score": round(growth, 2)},
            "optimization": {**optimization_meta, "score": round(optimization, 2)},
        },
    }
    if persist:
        _upsert_ai_score_daily(db, user_id, reference_day, snapshot)
    return snapshot


def dashboard_ai_score(db: Session, user_id: int, days: int, *, persist: bool = True) -> dict[str, Any]:
    days = max(7, min(int(days or 30), 120))
    today = _utcnow().date()
    current = _compute_ai_score_snapshot(db, user_id, reference_day=today, window_days=30, persist=persist)
    prev = _compute_ai_score_snapshot(db, user_id, reference_day=(today - timedelta(days=7)), window_days=30, persist=persist)
    delta_7d = round(float(current["ai_score"]) - float(prev["ai_score"]), 2)

    start_day = today - timedelta(days=days - 1)
    existing = (
        db.query(AiScoreDaily)
        .filter(AiScoreDaily.user_id == user_id, AiScoreDaily.day >= start_day, AiScoreDaily.day <= today)
        .order_by(AiScoreDaily.day.asc())
        .all()
    )
    existing_map = {r.day.isoformat(): r for r in existing}
    points = []
    for i in range(days):
        cur_day = start_day + timedelta(days=i)
        key = cur_day.isoformat()
        row = existing_map.get(key)
        if row:
            points.append(
                {
                    "day": key,
                    "ai_score": round(float(row.ai_score or 0.0), 2),
                    "performance": round(float(row.performance or 0.0), 2),
                    "consistency": round(float(row.consistency or 0.0), 2),
                    "growth": round(float(row.growth or 0.0), 2),
                    "optimization": round(float(row.optimization or 0.0), 2),
                }
            )
            continue
        snapshot = _compute_ai_score_snapshot(db, user_id, reference_day=cur_day, window_days=30, persist=persist)
        points.append(
            {
                "day": key,
                "ai_score": snapshot["ai_score"],
                "performance": snapshot["performance"],
                "consistency": snapshot["consistency"],
                "growth": snapshot["growth"],
                "optimization": snapshot["optimization"],
            }
        )

    return {
        "days": days,
        "current": current["ai_score"],
        "delta_7d": delta_7d,
        "needs_more_data": current["needs_more_data"],
        "breakdown": current["breakdown"],
        "timeseries": points,
    }


def dashboard_summary(db: Session, user_id: int, days: int) -> dict[str, Any]:
    days = max(1, min(int(days or 30), 120))
    start_day = (_utcnow().date() - timedelta(days=days - 1))
    row = (
        db.query(
            func.coalesce(func.sum(ContentMetricDaily.impressions), 0),
            func.coalesce(func.sum(ContentMetricDaily.reach), 0),
            func.coalesce(func.sum(ContentMetricDaily.views), 0),
            func.coalesce(func.sum(ContentMetricDaily.clicks), 0),
            func.coalesce(func.sum(ContentMetricDaily.likes), 0),
            func.coalesce(func.sum(ContentMetricDaily.comments), 0),
            func.coalesce(func.sum(ContentMetricDaily.shares), 0),
            func.coalesce(func.count(func.distinct(ContentMetricDaily.content_item_id)), 0),
        )
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(ContentItem.user_id == user_id, ContentMetricDaily.day >= start_day)
        .first()
    )
    by_platform_rows = (
        db.query(
            ContentItem.platform,
            func.coalesce(func.sum(ContentMetricDaily.reach), 0),
            func.coalesce(func.sum(ContentMetricDaily.views), 0),
            func.coalesce(func.sum(ContentMetricDaily.clicks), 0),
            func.coalesce(func.sum(ContentMetricDaily.likes), 0),
            func.coalesce(func.sum(ContentMetricDaily.comments), 0),
            func.coalesce(func.sum(ContentMetricDaily.shares), 0),
            func.coalesce(func.count(func.distinct(ContentMetricDaily.content_item_id)), 0),
        )
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(ContentItem.user_id == user_id, ContentMetricDaily.day >= start_day)
        .group_by(ContentItem.platform)
        .all()
    )
    by_platform: dict[str, dict[str, int]] = {
        "meta": {"reach": 0, "views": 0, "clicks": 0, "likes": 0, "comments": 0, "shares": 0, "items": 0},
        "youtube": {"reach": 0, "views": 0, "clicks": 0, "likes": 0, "comments": 0, "shares": 0, "items": 0},
    }
    for platform, reach, views, clicks, likes, comments, shares, items in by_platform_rows:
        key = "youtube" if str(platform or "").lower() == "youtube" else "meta"
        by_platform[key] = {
            "reach": _to_int(reach),
            "views": _to_int(views),
            "clicks": _to_int(clicks),
            "likes": _to_int(likes),
            "comments": _to_int(comments),
            "shares": _to_int(shares),
            "items": _to_int(items),
        }

    reach_total = _to_int(row[1] if row else 0)
    interactions_total = _to_int(row[4] if row else 0) + _to_int(row[5] if row else 0) + _to_int(row[6] if row else 0)
    engagement_rate = (interactions_total / max(reach_total, 1)) if reach_total > 0 else 0.0
    ai_score = dashboard_ai_score(db, user_id, days=min(days, 30), persist=False)

    return {
        "days": days,
        "from_day": start_day.isoformat(),
        "to_day": _utcnow().date().isoformat(),
        "impressions": _to_int(row[0] if row else 0),
        "reach": reach_total,
        "views": _to_int(row[2] if row else 0),
        "clicks": _to_int(row[3] if row else 0),
        "likes": _to_int(row[4] if row else 0),
        "comments": _to_int(row[5] if row else 0),
        "shares": _to_int(row[6] if row else 0),
        "items": _to_int(row[7] if row else 0),
        "engagement_rate": engagement_rate,
        "ai_score": ai_score.get("current", 0),
        "ai_score_delta_7d": ai_score.get("delta_7d", 0),
        "by_platform": by_platform,
    }


def dashboard_timeseries(db: Session, user_id: int, days: int) -> dict[str, Any]:
    days = max(1, min(int(days or 30), 120))
    start_day = (_utcnow().date() - timedelta(days=days - 1))
    points = {
        (start_day + timedelta(days=i)).isoformat(): {
            "day": (start_day + timedelta(days=i)).isoformat(),
            "reach": 0,
            "views": 0,
            "impressions": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "engagement_rate": 0.0,
            "meta_reach": 0,
            "meta_views": 0,
            "youtube_reach": 0,
            "youtube_views": 0,
        }
        for i in range(days)
    }
    rows = (
        db.query(
            ContentMetricDaily.day,
            func.coalesce(func.sum(ContentMetricDaily.reach), 0),
            func.coalesce(func.sum(ContentMetricDaily.views), 0),
            func.coalesce(func.sum(ContentMetricDaily.impressions), 0),
            func.coalesce(func.sum(ContentMetricDaily.likes), 0),
            func.coalesce(func.sum(ContentMetricDaily.comments), 0),
            func.coalesce(func.sum(ContentMetricDaily.shares), 0),
        )
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(ContentItem.user_id == user_id, ContentMetricDaily.day >= start_day)
        .group_by(ContentMetricDaily.day)
        .order_by(ContentMetricDaily.day.asc())
        .all()
    )
    for day, reach, views, impressions, likes, comments, shares in rows:
        key = day.isoformat()
        reach_val = _to_int(reach)
        likes_val = _to_int(likes)
        comments_val = _to_int(comments)
        shares_val = _to_int(shares)
        engagement_rate = (likes_val + comments_val + shares_val) / max(reach_val, 1) if reach_val > 0 else 0.0
        points[key] = {
            "day": key,
            "reach": reach_val,
            "views": _to_int(views),
            "impressions": _to_int(impressions),
            "likes": likes_val,
            "comments": comments_val,
            "shares": shares_val,
            "engagement_rate": engagement_rate,
            "meta_reach": points.get(key, {}).get("meta_reach", 0),
            "meta_views": points.get(key, {}).get("meta_views", 0),
            "youtube_reach": points.get(key, {}).get("youtube_reach", 0),
            "youtube_views": points.get(key, {}).get("youtube_views", 0),
        }

    by_platform_rows = (
        db.query(
            ContentMetricDaily.day,
            ContentItem.platform,
            func.coalesce(func.sum(ContentMetricDaily.reach), 0),
            func.coalesce(func.sum(ContentMetricDaily.views), 0),
        )
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(ContentItem.user_id == user_id, ContentMetricDaily.day >= start_day)
        .group_by(ContentMetricDaily.day, ContentItem.platform)
        .order_by(ContentMetricDaily.day.asc())
        .all()
    )
    for day, platform, reach, views in by_platform_rows:
        key = day.isoformat()
        point = points.get(key)
        if not point:
            continue
        if str(platform or "").lower() == "youtube":
            point["youtube_reach"] = _to_int(reach)
            point["youtube_views"] = _to_int(views)
        else:
            point["meta_reach"] = _to_int(reach)
            point["meta_views"] = _to_int(views)

    return {"days": days, "points": [points[k] for k in sorted(points.keys())]}


def dashboard_recent(db: Session, user_id: int, limit: int) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    rows = (
        db.query(ContentItem)
        .filter(ContentItem.user_id == user_id)
        .order_by(ContentItem.published_at.desc().nullslast(), ContentItem.updated_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    for row in rows:
        latest = (
            db.query(ContentMetricDaily)
            .filter(ContentMetricDaily.content_item_id == row.id)
            .order_by(ContentMetricDaily.day.desc())
            .first()
        )
        metrics = {
            "day": latest.day.isoformat() if latest else None,
            "impressions": _to_int(latest.impressions if latest else 0),
            "reach": _to_int(latest.reach if latest else 0),
            "views": _to_int(latest.views if latest else 0),
            "clicks": _to_int(latest.clicks if latest else 0),
            "likes": _to_int(latest.likes if latest else 0),
            "comments": _to_int(latest.comments if latest else 0),
            "shares": _to_int(latest.shares if latest else 0),
        }
        engagement_rate = (
            (metrics["likes"] + metrics["comments"] + metrics["shares"]) / max(metrics["reach"], 1)
            if metrics["reach"] > 0
            else 0.0
        )
        items.append(
            {
                "id": row.id,
                "platform": row.platform,
                "content_type": row.content_type,
                "title": row.title,
                "message": row.message,
                "url": row.url,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "engagement_rate": engagement_rate,
                "metrics": metrics,
            }
        )
    return {"items": items, "limit": limit}


def dashboard_insights(db: Session, user_id: int, days: int) -> dict[str, Any]:
    days = max(1, min(int(days or 30), 120))
    start_day = (_utcnow().date() - timedelta(days=days - 1))

    metric_rows = (
        db.query(ContentMetricDaily, ContentItem)
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(ContentItem.user_id == user_id, ContentMetricDaily.day >= start_day)
        .all()
    )
    if not metric_rows:
        return {
            "days": days,
            "insights": [
                {
                    "impact": "low",
                    "title": "Недостаточно данных",
                    "text": "Недостаточно данных: нажмите «Синхронизировать метрики» и опубликуйте контент.",
                }
            ],
        }

    by_day: dict[str, dict[str, int]] = {}
    by_format: dict[str, dict[str, int]] = {}
    by_item: dict[int, dict[str, Any]] = {}

    for metric, item in metric_rows:
        d = metric.day.isoformat()
        day_row = by_day.setdefault(d, {"reach": 0, "likes": 0, "comments": 0, "shares": 0, "clicks": 0, "views": 0})
        day_row["reach"] += _to_int(metric.reach)
        day_row["likes"] += _to_int(metric.likes)
        day_row["comments"] += _to_int(metric.comments)
        day_row["shares"] += _to_int(metric.shares)
        day_row["clicks"] += _to_int(metric.clicks)
        day_row["views"] += _to_int(metric.views)

        fmt = str(item.content_type or "post").lower()
        fmt_row = by_format.setdefault(fmt, {"reach": 0, "likes": 0, "comments": 0, "shares": 0, "count": 0})
        fmt_row["reach"] += _to_int(metric.reach)
        fmt_row["likes"] += _to_int(metric.likes)
        fmt_row["comments"] += _to_int(metric.comments)
        fmt_row["shares"] += _to_int(metric.shares)
        fmt_row["count"] += 1

        item_row = by_item.setdefault(
            item.id,
            {"title": item.title or "Публикация", "url": item.url, "reach": 0, "likes": 0, "comments": 0, "shares": 0, "clicks": 0},
        )
        item_row["reach"] += _to_int(metric.reach)
        item_row["likes"] += _to_int(metric.likes)
        item_row["comments"] += _to_int(metric.comments)
        item_row["shares"] += _to_int(metric.shares)
        item_row["clicks"] += _to_int(metric.clicks)

    def _engagement_rate(row: dict[str, int]) -> float:
        reach = max(_to_int(row.get("reach")), 1)
        return (_to_int(row.get("likes")) + _to_int(row.get("comments")) + _to_int(row.get("shares"))) / reach

    best_day_key = max(by_day.keys(), key=lambda k: _engagement_rate(by_day[k]))
    best_day_row = by_day[best_day_key]
    best_day_rate = _engagement_rate(best_day_row) * 100.0

    best_format_key = max(by_format.keys(), key=lambda k: _engagement_rate(by_format[k]))
    best_format_rate = _engagement_rate(by_format[best_format_key]) * 100.0

    posts_count = (
        db.query(func.count(ContentItem.id))
        .filter(ContentItem.user_id == user_id, ContentItem.published_at.isnot(None), ContentItem.published_at >= datetime.combine(start_day, datetime.min.time()))
        .scalar()
        or 0
    )
    min_target = max(4, int(round(days / 7.0 * 2)))

    top_item = None
    top_score = -1.0
    top_metric_name = "engagement"
    for item_id, row in by_item.items():
        reach = max(_to_int(row["reach"]), 1)
        ctr = _to_int(row["clicks"]) / reach
        engagement = (_to_int(row["likes"]) + _to_int(row["comments"]) + _to_int(row["shares"])) / reach
        score = ctr if _to_int(row["clicks"]) > 0 else engagement
        metric_name = "CTR" if _to_int(row["clicks"]) > 0 else "engagement"
        if score > top_score:
            top_score = score
            top_metric_name = metric_name
            top_item = {"id": item_id, **row}

    insights = [
        {
            "impact": "high",
            "title": "Лучший день по вовлечению",
            "text": f"{best_day_key}: engagement rate {best_day_rate:.1f}% (лайки+комментарии+репосты / reach).",
        },
        {
            "impact": "medium",
            "title": "Лучший формат",
            "text": f"Формат «{best_format_key}» показывает {best_format_rate:.1f}% engagement rate за последние {days} дней.",
        },
        {
            "impact": "medium" if posts_count < min_target else "low",
            "title": "Регулярность публикаций",
            "text": (
                f"За {days} дней опубликовано {posts_count} материалов. Рекомендуем минимум {min_target}."
                if posts_count < min_target
                else f"За {days} дней опубликовано {posts_count} материалов. Регулярность в рабочем диапазоне."
            ),
        },
    ]
    if top_item:
        score_pct = top_score * 100.0
        top_title = str(top_item.get("title") or "Публикация")
        top_url = str(top_item.get("url") or "").strip()
        suffix = f" ({top_url})" if top_url else ""
        insights.append(
            {
                "impact": "high",
                "title": "Топ-контент",
                "text": f"«{top_title}» — лучший по {top_metric_name}: {score_pct:.1f}%{suffix}",
            }
        )

    return {"days": days, "insights": insights[:5]}


def _piecewise_norm(value: float, low: float, mid: float, high: float) -> float:
    v = max(0.0, float(value or 0.0))
    if v <= low:
        return (v / max(low, 1e-9)) * 0.3
    if v <= mid:
        return 0.3 + ((v - low) / max(mid - low, 1e-9)) * 0.4
    if v <= high:
        return 0.7 + ((v - mid) / max(high - mid, 1e-9)) * 0.3
    return 1.0


def _aggregate_period_totals_v2(db: Session, user_id: int, start_day: date, end_day: date) -> dict[str, Any]:
    row = (
        db.query(
            func.coalesce(func.sum(ContentMetricDaily.impressions), 0),
            func.coalesce(func.sum(ContentMetricDaily.reach), 0),
            func.coalesce(func.sum(ContentMetricDaily.views), 0),
            func.coalesce(func.sum(ContentMetricDaily.clicks), 0),
            func.coalesce(func.sum(ContentMetricDaily.likes), 0),
            func.coalesce(func.sum(ContentMetricDaily.comments), 0),
            func.coalesce(func.sum(ContentMetricDaily.shares), 0),
            func.coalesce(func.count(func.distinct(ContentMetricDaily.content_item_id)), 0),
        )
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(
            ContentItem.user_id == user_id,
            ContentMetricDaily.day >= start_day,
            ContentMetricDaily.day <= end_day,
        )
        .first()
    )
    by_platform_rows = (
        db.query(
            ContentItem.platform,
            func.coalesce(func.sum(ContentMetricDaily.reach), 0),
            func.coalesce(func.sum(ContentMetricDaily.views), 0),
            func.coalesce(func.sum(ContentMetricDaily.clicks), 0),
            func.coalesce(func.sum(ContentMetricDaily.likes), 0),
            func.coalesce(func.sum(ContentMetricDaily.comments), 0),
            func.coalesce(func.sum(ContentMetricDaily.shares), 0),
            func.coalesce(func.count(func.distinct(ContentMetricDaily.content_item_id)), 0),
        )
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(
            ContentItem.user_id == user_id,
            ContentMetricDaily.day >= start_day,
            ContentMetricDaily.day <= end_day,
        )
        .group_by(ContentItem.platform)
        .all()
    )
    by_platform: dict[str, dict[str, int]] = {
        "meta": {"reach": 0, "views": 0, "clicks": 0, "likes": 0, "comments": 0, "shares": 0, "items": 0},
        "youtube": {"reach": 0, "views": 0, "clicks": 0, "likes": 0, "comments": 0, "shares": 0, "items": 0},
    }
    for platform, reach, views, clicks, likes, comments, shares, items in by_platform_rows:
        key = "youtube" if str(platform or "").lower() == "youtube" else "meta"
        by_platform[key] = {
            "reach": _to_int(reach),
            "views": _to_int(views),
            "clicks": _to_int(clicks),
            "likes": _to_int(likes),
            "comments": _to_int(comments),
            "shares": _to_int(shares),
            "items": _to_int(items),
        }

    reach_total = _to_int(row[1] if row else 0)
    interactions_total = _to_int(row[4] if row else 0) + _to_int(row[5] if row else 0) + _to_int(row[6] if row else 0)
    engagement_rate = (interactions_total / max(reach_total, 1)) if reach_total > 0 else 0.0
    return {
        "impressions": _to_int(row[0] if row else 0),
        "reach": reach_total,
        "views": _to_int(row[2] if row else 0),
        "clicks": _to_int(row[3] if row else 0),
        "likes": _to_int(row[4] if row else 0),
        "comments": _to_int(row[5] if row else 0),
        "shares": _to_int(row[6] if row else 0),
        "items": _to_int(row[7] if row else 0),
        "engagement_rate": engagement_rate,
        "by_platform": by_platform,
    }


def _build_daily_analytics_series_v2(db: Session, user_id: int, start_day: date, end_day: date) -> list[dict[str, Any]]:
    day_map: dict[str, dict[str, Any]] = {}
    total_days = max((end_day - start_day).days + 1, 1)
    for i in range(total_days):
        d = start_day + timedelta(days=i)
        day_map[d.isoformat()] = {
            "day": d.isoformat(),
            "reach": 0,
            "views": 0,
            "clicks": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "posts": 0,
            "ctr_reach": 0,
            "ctr_clicks": 0,
        }

    metric_rows = (
        db.query(
            ContentMetricDaily.day,
            ContentItem.platform,
            func.coalesce(func.sum(ContentMetricDaily.reach), 0),
            func.coalesce(func.sum(ContentMetricDaily.views), 0),
            func.coalesce(func.sum(ContentMetricDaily.clicks), 0),
            func.coalesce(func.sum(ContentMetricDaily.likes), 0),
            func.coalesce(func.sum(ContentMetricDaily.comments), 0),
            func.coalesce(func.sum(ContentMetricDaily.shares), 0),
        )
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(
            ContentItem.user_id == user_id,
            ContentMetricDaily.day >= start_day,
            ContentMetricDaily.day <= end_day,
        )
        .group_by(ContentMetricDaily.day, ContentItem.platform)
        .all()
    )
    for day, platform, reach, views, clicks, likes, comments, shares in metric_rows:
        key = day.isoformat()
        row = day_map.get(key)
        if not row:
            continue
        reach_v = _to_int(reach)
        clicks_v = _to_int(clicks)
        row["reach"] += reach_v
        row["views"] += _to_int(views)
        row["clicks"] += clicks_v
        row["likes"] += _to_int(likes)
        row["comments"] += _to_int(comments)
        row["shares"] += _to_int(shares)
        if str(platform or "").lower() != "youtube":
            row["ctr_reach"] += reach_v
            row["ctr_clicks"] += clicks_v

    post_rows = (
        db.query(func.date(ContentItem.published_at), func.coalesce(func.count(ContentItem.id), 0))
        .filter(
            ContentItem.user_id == user_id,
            ContentItem.published_at.isnot(None),
            ContentItem.published_at >= datetime.combine(start_day, datetime.min.time()),
            ContentItem.published_at <= datetime.combine(end_day, datetime.max.time()),
        )
        .group_by(func.date(ContentItem.published_at))
        .all()
    )
    for day_key, posts_count in post_rows:
        key = str(day_key)
        if key in day_map:
            day_map[key]["posts"] = _to_int(posts_count)
    return [day_map[k] for k in sorted(day_map.keys())]


def _coverage_confidence_v2(coverage: float) -> str:
    if coverage >= 0.67:
        return "high"
    if coverage >= 0.34:
        return "medium"
    return "low"


def _expected_gain_v2(key: str, score_norm: float) -> str:
    if score_norm >= 0.9:
        return "+0..2"
    if score_norm >= 0.7:
        return "+2..5"
    if key == "engagement_quality":
        return "+6..12"
    if key == "growth_momentum":
        return "+5..10"
    if key == "regularity":
        return "+4..8"
    return "+3..7"


def compute_ai_score(db: Session, user_id: int, days: int = 30, *, reference_day: date | None = None) -> dict[str, Any]:
    days = max(7, min(int(days or 30), 120))
    end_day = reference_day or _utcnow().date()
    start_day = end_day - timedelta(days=days - 1)
    rows = _build_daily_analytics_series_v2(db, user_id, start_day, end_day)
    platforms_used = (
        db.query(func.count(func.distinct(ContentItem.platform)))
        .filter(
            ContentItem.user_id == user_id,
            ContentItem.updated_at >= datetime.combine(start_day, datetime.min.time()),
            ContentItem.updated_at <= datetime.combine(end_day, datetime.max.time()),
        )
        .scalar()
        or 0
    )
    days_with_reach = sum(1 for r in rows if _to_int(r["reach"]) > 0)
    days_with_posts = sum(1 for r in rows if _to_int(r["posts"]) > 0)
    posts_total = sum(_to_int(r["posts"]) for r in rows)

    expected_posts = 3.0 * (days / 7.0)
    regularity_ratio = min(posts_total / max(expected_posts, 1.0), 1.0)
    holes_ratio = sum(1 for r in rows if _to_int(r["posts"]) <= 0) / max(days, 1)
    regularity_norm = _clamp((regularity_ratio * 0.75 + (1.0 - holes_ratio) * 0.25), 0.0, 1.0)
    regularity_score = regularity_norm * 20.0

    er_values = []
    for r in rows:
        reach_v = _to_int(r["reach"])
        if reach_v > 0:
            er_values.append((_to_int(r["likes"]) + _to_int(r["comments"]) + _to_int(r["shares"])) / max(reach_v, 1))
    avg_engagement = sum(er_values) / len(er_values) if er_values else 0.0
    engagement_norm = _piecewise_norm(avg_engagement, low=0.01, mid=0.03, high=0.06)
    engagement_score = engagement_norm * 30.0

    half = max(1, len(rows) // 2)
    first_half = rows[:half]
    second_half = rows[half:]
    reach_first = sum(_to_int(r["reach"]) for r in first_half)
    reach_second = sum(_to_int(r["reach"]) for r in second_half)
    growth_raw = (reach_second - reach_first) / max(reach_first, 1)
    growth_clamped = _clamp(growth_raw, -0.5, 1.0)
    growth_norm = (growth_clamped + 0.5) / 1.5
    growth_score = growth_norm * 25.0
    growth_confidence = "low" if reach_first < 100 else ("medium" if reach_first < 1000 else "high")

    ctr_values = []
    ctr_days = 0
    for r in rows:
        ctr_reach = _to_int(r["ctr_reach"])
        if ctr_reach > 0:
            ctr_days += 1
            ctr_values.append(_to_int(r["ctr_clicks"]) / max(ctr_reach, 1))
    avg_ctr = sum(ctr_values) / len(ctr_values) if ctr_values else 0.0
    ctr_norm = _piecewise_norm(avg_ctr, low=0.002, mid=0.008, high=0.015)
    ctr_coverage = ctr_days / max(days_with_reach, 1) if days_with_reach > 0 else 0.0
    ctr_weighted_norm = (ctr_norm * ctr_coverage) + (0.5 * (1.0 - ctr_coverage))
    ctr_score = ctr_weighted_norm * 15.0
    ctr_confidence = "low" if ctr_days < 5 else _coverage_confidence_v2(ctr_coverage)

    dow_er: dict[int, list[float]] = {}
    dow_posts: dict[int, int] = {}
    for r in rows:
        day_obj = date.fromisoformat(str(r["day"]))
        dow = day_obj.weekday()
        reach_v = _to_int(r["reach"])
        if reach_v > 0:
            er = (_to_int(r["likes"]) + _to_int(r["comments"]) + _to_int(r["shares"])) / max(reach_v, 1)
            dow_er.setdefault(dow, []).append(er)
        dow_posts[dow] = dow_posts.get(dow, 0) + _to_int(r["posts"])
    if posts_total <= 0 or not dow_er:
        timing_score = 5.0
        best_days = []
        timing_confidence = "low"
        publish_on_best_ratio = 0.5
    else:
        avg_by_dow = {k: (sum(v) / len(v)) for k, v in dow_er.items() if v}
        sorted_best = sorted(avg_by_dow.items(), key=lambda x: x[1], reverse=True)
        best_days = [k for k, _ in sorted_best[:2]] if sorted_best else []
        posts_on_best_days = sum(dow_posts.get(d, 0) for d in best_days)
        publish_on_best_ratio = posts_on_best_days / max(posts_total, 1)
        timing_score = _clamp(publish_on_best_ratio, 0.0, 1.0) * 10.0
        timing_confidence = "high" if posts_total >= 12 else ("medium" if posts_total >= 6 else "low")

    factors = [
        {
            "key": "regularity",
            "title": "Регулярность и стабильность",
            "weight": 20,
            "score": round(regularity_score, 2),
            "value": {"posts_total": posts_total, "expected": round(expected_posts, 1), "holes_ratio": round(holes_ratio, 3)},
            "confidence": _coverage_confidence_v2(days_with_posts / max(days, 1)),
            "how_to_improve": "Держите ритм минимум 3 публикации в неделю без длинных пауз.",
            "expected_gain": _expected_gain_v2("regularity", regularity_norm),
        },
        {
            "key": "engagement_quality",
            "title": "Качество вовлечения",
            "weight": 30,
            "score": round(engagement_score, 2),
            "value": {"avg_engagement_rate": round(avg_engagement, 4)},
            "confidence": _coverage_confidence_v2(days_with_reach / max(days, 1)),
            "how_to_improve": "Добавляйте хук в первые 2 строки и вопрос в конце поста.",
            "expected_gain": _expected_gain_v2("engagement_quality", engagement_norm),
        },
        {
            "key": "growth_momentum",
            "title": "Динамика роста",
            "weight": 25,
            "score": round(growth_score, 2),
            "value": {"growth_ratio": round(growth_raw, 4), "reach_first": reach_first, "reach_second": reach_second},
            "confidence": growth_confidence,
            "how_to_improve": "Увеличьте долю форматов, которые уже дают рост охвата.",
            "expected_gain": _expected_gain_v2("growth_momentum", growth_norm),
        },
        {
            "key": "ctr_intent",
            "title": "CTR и намерение к действию",
            "weight": 15,
            "score": round(ctr_score, 2),
            "value": {"avg_ctr": round(avg_ctr, 4), "coverage": round(ctr_coverage, 3), "days_with_ctr": ctr_days},
            "confidence": ctr_confidence,
            "how_to_improve": "Используйте явный CTA и конкретную выгоду в первых абзацах.",
            "expected_gain": _expected_gain_v2("ctr_intent", ctr_weighted_norm),
        },
        {
            "key": "timing_format_fit",
            "title": "Попадание во время и формат",
            "weight": 10,
            "score": round(timing_score, 2),
            "value": {"best_days": best_days, "publish_on_best_ratio": round(publish_on_best_ratio, 3)},
            "confidence": timing_confidence,
            "how_to_improve": "Планируйте публикации в дни, где engagement стабильно выше.",
            "expected_gain": _expected_gain_v2("timing_format_fit", min(1.0, timing_score / 10.0)),
        },
    ]
    total_score = round(sum(float(f["score"]) for f in factors), 1)
    return {
        "total": _clamp(total_score, 0.0, 100.0),
        "factors": factors,
        "period": {"days": days, "from": start_day.isoformat(), "to": end_day.isoformat()},
        "data_coverage": {"days_with_reach": days_with_reach, "days_with_posts": days_with_posts, "platforms_used": int(platforms_used)},
        "needs_more_data": days_with_reach < 7,
    }


def _upsert_ai_score_daily_v2(db: Session, user_id: int, snapshot_day: date, snapshot: dict[str, Any]) -> None:
    legacy = db.query(AiScoreDaily).filter(AiScoreDaily.user_id == user_id, AiScoreDaily.day == snapshot_day).first()
    if not legacy:
        legacy = AiScoreDaily(user_id=user_id, day=snapshot_day)
        db.add(legacy)
        db.flush()
    factor_map = {str(f.get("key")): float(f.get("score") or 0.0) for f in (snapshot.get("factors") or [])}
    legacy.ai_score = float(snapshot.get("total") or 0.0)
    legacy.performance = factor_map.get("engagement_quality", 0.0) + factor_map.get("ctr_intent", 0.0)
    legacy.consistency = factor_map.get("regularity", 0.0)
    legacy.growth = factor_map.get("growth_momentum", 0.0)
    legacy.optimization = factor_map.get("timing_format_fit", 0.0)

    row = db.query(AiScoreDailyV2).filter(AiScoreDailyV2.user_id == user_id, AiScoreDailyV2.day == snapshot_day).first()
    if not row:
        row = AiScoreDailyV2(user_id=user_id, day=snapshot_day)
        db.add(row)
        db.flush()
    row.score_total = float(snapshot.get("total") or 0.0)
    row.score_json = json.dumps(snapshot, ensure_ascii=False)


def compute_forecast(
    db: Session,
    user_id: int,
    *,
    horizon_days: int = 7,
    history_days: int = 90,
    reference_day: date | None = None,
) -> dict[str, Any]:
    horizon_days = 30 if int(horizon_days or 7) >= 30 else 7
    history_days = max(30, min(int(history_days or 90), 180))
    end_day = reference_day or _utcnow().date()
    start_day = end_day - timedelta(days=history_days - 1)
    rows = _build_daily_analytics_series_v2(db, user_id, start_day, end_day)

    def _sma(values: list[float]) -> float:
        return (sum(values) / len(values)) if values else 0.0

    reach_vals = [float(_to_int(r["reach"])) for r in rows]
    views_vals = [float(_to_int(r["views"])) for r in rows]
    posts_vals = [float(_to_int(r["posts"])) for r in rows]
    eng_vals = [
        ((_to_int(r["likes"]) + _to_int(r["comments"]) + _to_int(r["shares"])) / max(_to_int(r["reach"]), 1))
        if _to_int(r["reach"]) > 0
        else 0.0
        for r in rows
    ]
    last7_reach = _sma(reach_vals[-7:])
    prev7_reach = _sma(reach_vals[-14:-7]) if len(reach_vals) >= 14 else _sma(reach_vals[:-7])
    last7_views = _sma(views_vals[-7:])
    prev7_views = _sma(views_vals[-14:-7]) if len(views_vals) >= 14 else _sma(views_vals[:-7])
    avg_eng_last7 = _sma(eng_vals[-7:])
    avg_eng_prev7 = _sma(eng_vals[-14:-7]) if len(eng_vals) >= 14 else _sma(eng_vals[:-7])
    reach_trend = (last7_reach - prev7_reach) / max(prev7_reach, 1.0)
    views_trend = (last7_views - prev7_views) / max(prev7_views, 1.0)

    points = []
    for k in range(1, horizon_days + 1):
        f_reach = max(0.0, last7_reach * ((1.0 + reach_trend) ** (k / 7.0)))
        f_views = max(0.0, last7_views * ((1.0 + views_trend) ** (k / 7.0)))
        f_eng = _clamp(avg_eng_last7 + (avg_eng_last7 - avg_eng_prev7) * (k / 7.0) * 0.3, 0.0, 1.0)
        points.append({"day": (end_day + timedelta(days=k)).isoformat(), "reach": round(f_reach, 2), "views": round(f_views, 2), "engagement_rate": round(f_eng, 4)})

    days_with_reach = sum(1 for v in reach_vals if v > 0)
    reasons = []
    if days_with_reach < 10:
        reasons.append("мало данных")
    mean_reach = _sma(reach_vals)
    std_reach = statistics.pstdev(reach_vals) if len(reach_vals) >= 2 else 0.0
    if mean_reach > 0 and (std_reach / mean_reach) > 1.5:
        reasons.append("сильные пики")
    zero_ratio = (sum(1 for v in reach_vals if v <= 0) / max(len(reach_vals), 1))
    if zero_ratio > 0.5:
        reasons.append("частые нули")
    confidence_level = "high" if days_with_reach >= 21 and not reasons else ("medium" if days_with_reach >= 10 else "low")
    if not reasons:
        reasons = ["данных достаточно"]

    def _corr(xs: list[float], ys: list[float]) -> float:
        if len(xs) != len(ys) or len(xs) < 3:
            return 0.0
        mx = _sma(xs)
        my = _sma(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
        den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
        den = den_x * den_y
        if den <= 1e-9:
            return 0.0
        return num / den

    corr_posts_reach = _corr(posts_vals, reach_vals)
    elasticity = _clamp(corr_posts_reach * 0.3, 0.0, 0.2)
    if elasticity <= 0:
        elasticity = 0.08
    plus_multiplier = 1.0 + (elasticity * 0.3)
    total_reach = sum(float(p["reach"]) for p in points)
    total_views = sum(float(p["views"]) for p in points)
    avg_eng = _sma([float(p["engagement_rate"]) for p in points])
    current_posts_per_week = (sum(posts_vals) / max(history_days / 7.0, 1.0))
    plus_posts_per_week = current_posts_per_week * 1.3
    return {
        "horizon_days": horizon_days,
        "confidence": {"level": confidence_level, "reasons": reasons},
        "totals": {"reach": round(total_reach, 2), "views": round(total_views, 2), "engagement_rate_avg": round(avg_eng, 4)},
        "points": points,
        "scenarios": {
            "current": {"posts_per_week": round(current_posts_per_week, 2), "reach": round(total_reach, 2), "views": round(total_views, 2), "engagement_rate_avg": round(avg_eng, 4)},
            "plus30": {"posts_per_week": round(plus_posts_per_week, 2), "reach": round(total_reach * plus_multiplier, 2), "views": round(total_views * plus_multiplier, 2), "engagement_rate_avg": round(min(1.0, avg_eng * (1.0 + elasticity * 0.1)), 4)},
        },
        "based_on_from": start_day.isoformat(),
        "based_on_to": end_day.isoformat(),
    }


def _upsert_forecast_cache_v2(db: Session, user_id: int, payload: dict[str, Any]) -> None:
    horizon = int(payload.get("horizon_days") or 7)
    based_to = date.fromisoformat(str(payload.get("based_on_to")))
    based_from = date.fromisoformat(str(payload.get("based_on_from")))
    row = (
        db.query(Forecast)
        .filter(Forecast.user_id == user_id, Forecast.horizon_days == horizon, Forecast.based_on_to == based_to)
        .order_by(Forecast.id.desc())
        .first()
    )
    if not row:
        row = Forecast(user_id=user_id, horizon_days=horizon, based_on_to=based_to, based_on_from=based_from)
        db.add(row)
        db.flush()
    row.forecast_json = json.dumps(payload, ensure_ascii=False)
    row.based_on_from = based_from
    row.based_on_to = based_to
    row.created_at = _utcnow()


def dashboard_ai_score(db: Session, user_id: int, days: int, *, persist: bool = True) -> dict[str, Any]:
    days = max(7, min(int(days or 30), 120))
    today = _utcnow().date()
    current = compute_ai_score(db, user_id, days=30, reference_day=today)
    prev_7 = compute_ai_score(db, user_id, days=30, reference_day=(today - timedelta(days=7)))
    prev_period = compute_ai_score(db, user_id, days=30, reference_day=(today - timedelta(days=30)))
    delta_7d = round(float(current["total"]) - float(prev_7["total"]), 2)
    delta_vs_prev_period = round(float(current["total"]) - float(prev_period["total"]), 2)

    if persist:
        _upsert_ai_score_daily_v2(db, user_id, today, current)

    start_day = today - timedelta(days=days - 1)
    existing = (
        db.query(AiScoreDailyV2)
        .filter(AiScoreDailyV2.user_id == user_id, AiScoreDailyV2.day >= start_day, AiScoreDailyV2.day <= today)
        .order_by(AiScoreDailyV2.day.asc())
        .all()
    )
    existing_map = {r.day.isoformat(): r for r in existing}
    points = []
    for i in range(days):
        cur_day = start_day + timedelta(days=i)
        key = cur_day.isoformat()
        row = existing_map.get(key)
        if row:
            points.append({"day": key, "ai_score": round(float(row.score_total or 0.0), 2)})
            continue
        snapshot = compute_ai_score(db, user_id, days=30, reference_day=cur_day)
        if persist:
            _upsert_ai_score_daily_v2(db, user_id, cur_day, snapshot)
        points.append({"day": key, "ai_score": round(float(snapshot.get("total") or 0.0), 2)})

    return {
        "days": days,
        "current": round(float(current["total"]), 2),
        "delta_7d": delta_7d,
        "delta_vs_prev_period": delta_vs_prev_period,
        "needs_more_data": bool(current.get("needs_more_data")),
        "breakdown": {"factors": current.get("factors", []), "period": current.get("period", {}), "data_coverage": current.get("data_coverage", {})},
        "timeseries": points,
    }


def dashboard_forecast(db: Session, user_id: int, *, horizon: int = 7, days: int = 90, persist: bool = True) -> dict[str, Any]:
    payload = compute_forecast(db, user_id, horizon_days=horizon, history_days=days)
    if persist:
        _upsert_forecast_cache_v2(db, user_id, payload)
    return payload


def dashboard_summary(db: Session, user_id: int, days: int) -> dict[str, Any]:
    days = max(7, min(int(days or 30), 120))
    today = _utcnow().date()
    current_start = today - timedelta(days=days - 1)
    prev_end = current_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    current = _aggregate_period_totals_v2(db, user_id, current_start, today)
    prev = _aggregate_period_totals_v2(db, user_id, prev_start, prev_end)
    ai_score = dashboard_ai_score(db, user_id, days=min(days, 30), persist=False)

    def _delta(cur: float, old: float) -> dict[str, float]:
        diff = float(cur or 0.0) - float(old or 0.0)
        pct = (diff / abs(float(old or 0.0))) if float(old or 0.0) != 0 else (1.0 if diff > 0 else 0.0)
        return {"abs": round(diff, 2), "pct": round(pct, 4)}

    return {
        "days": days,
        "from_day": current_start.isoformat(),
        "to_day": today.isoformat(),
        "current": current,
        "prev": prev,
        "delta": {
            "reach": _delta(current["reach"], prev["reach"]),
            "views": _delta(current["views"], prev["views"]),
            "clicks": _delta(current["clicks"], prev["clicks"]),
            "likes": _delta(current["likes"], prev["likes"]),
            "comments": _delta(current["comments"], prev["comments"]),
            "shares": _delta(current["shares"], prev["shares"]),
            "items": _delta(current["items"], prev["items"]),
            "engagement_rate": _delta(current["engagement_rate"], prev["engagement_rate"]),
            "ai_score": _delta(ai_score.get("current", 0), ai_score.get("current", 0) - ai_score.get("delta_vs_prev_period", 0)),
        },
        # Backward-compatible fields for current frontend.
        "impressions": current["impressions"],
        "reach": current["reach"],
        "views": current["views"],
        "clicks": current["clicks"],
        "likes": current["likes"],
        "comments": current["comments"],
        "shares": current["shares"],
        "items": current["items"],
        "engagement_rate": current["engagement_rate"],
        "ai_score": ai_score.get("current", 0),
        "ai_score_delta_7d": ai_score.get("delta_7d", 0),
        "ai_score_delta_prev_period": ai_score.get("delta_vs_prev_period", 0),
        "by_platform": current["by_platform"],
    }
