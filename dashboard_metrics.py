from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from facebook_api import list_pages
from saas_models import ConnectedAccount, ContentItem, ContentMetricDaily, SocialAccount
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

    db.commit()
    return {"meta_items": meta_items, "youtube_items": youtube_items, "errors": errors}


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

    return {
        "days": days,
        "from_day": start_day.isoformat(),
        "to_day": _utcnow().date().isoformat(),
        "impressions": _to_int(row[0] if row else 0),
        "reach": _to_int(row[1] if row else 0),
        "views": _to_int(row[2] if row else 0),
        "clicks": _to_int(row[3] if row else 0),
        "likes": _to_int(row[4] if row else 0),
        "comments": _to_int(row[5] if row else 0),
        "shares": _to_int(row[6] if row else 0),
        "items": _to_int(row[7] if row else 0),
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
        )
        .join(ContentItem, ContentItem.id == ContentMetricDaily.content_item_id)
        .filter(ContentItem.user_id == user_id, ContentMetricDaily.day >= start_day)
        .group_by(ContentMetricDaily.day)
        .order_by(ContentMetricDaily.day.asc())
        .all()
    )
    for day, reach, views, impressions in rows:
        key = day.isoformat()
        points[key] = {
            "day": key,
            "reach": _to_int(reach),
            "views": _to_int(views),
            "impressions": _to_int(impressions),
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
        items.append(
            {
                "id": row.id,
                "platform": row.platform,
                "content_type": row.content_type,
                "title": row.title,
                "message": row.message,
                "url": row.url,
                "published_at": row.published_at.isoformat() if row.published_at else None,
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
