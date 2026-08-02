"""OpenAI quota/billing safety net -- detection, counters, Telegram alerting,
and durable fallback-mode tracking. Scope: observability and notification
only. It never changes what gets generated (that's shorts_hook_diversity.py
and video_script_generator.py's own fallback logic) and never touches the
scheduler, media selection, TTS, subtitles, music, CTA, render, or upload.

Durable state (is a channel currently in "OpenAI degraded" mode, when was
the last alert sent) is stored as rows in the existing SystemLog table --
no new table, no migration. Two marker messages act as a tiny state
machine: "openai_quota_alert_sent" (we're in degraded mode, cooldown
running) and "openai_recovered" (we're not). Whichever is most recent wins.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict
from datetime import datetime, timedelta

import openai as _openai_sdk
import requests

log = logging.getLogger("factory.openai_quota")

# ------------------------------------------------------------- classification

# insufficient_quota / billing_hard_limit_reached: HTTP 429, RateLimitError,
# but NOT the same as an ordinary rate_limit_exceeded (also HTTP 429,
# RateLimitError) -- the SDK exception class alone can't tell them apart,
# only the error body's `code`/`type` can.
_QUOTA_BILLING_CODES = {
    "insufficient_quota",
    "billing_hard_limit_reached",
    "billing_not_active",
    "account_deactivated",
}


def classify_openai_error(exc: Exception) -> str:
    """Returns one of: 'quota_billing', 'rate_limit', 'timeout', 'other'.
    Never raises -- an exception from the classifier itself would be worse
    than a wrong-but-safe 'other' classification."""
    try:
        if isinstance(exc, _openai_sdk.APITimeoutError):
            return "timeout"

        code = str(getattr(exc, "code", "") or "").strip().lower()
        err_type = str(getattr(exc, "type", "") or "").strip().lower()
        message = str(getattr(exc, "message", "") or str(exc) or "").lower()

        if code in _QUOTA_BILLING_CODES or err_type in _QUOTA_BILLING_CODES:
            return "quota_billing"
        # Defensive fallback for wording OpenAI may use without a matching
        # `code` (SDK error taxonomy has shifted before) -- message-based,
        # deliberately narrow so it can't accidentally swallow an ordinary
        # rate limit or a generic 4xx.
        if "quota" in message or "billing" in message or "deactivated" in message:
            return "quota_billing"

        if isinstance(exc, _openai_sdk.RateLimitError):
            return "rate_limit"
        if isinstance(exc, (_openai_sdk.AuthenticationError, _openai_sdk.PermissionDeniedError)):
            return "other"  # bad/revoked key etc. -- not a quota/billing signal on its own
        return "other"
    except Exception:
        return "other"


# ------------------------------------------------------------------ counters
# In-process only (reset on worker restart) -- exposed for observability,
# not meant to be a durable metric store.

_counters_lock = threading.Lock()
_counters: dict[str, int] = defaultdict(int)

_COUNTER_NAMES = (
    "openai_success", "openai_quota_error", "openai_timeout", "openai_rate_limit",
    "fallback_short_generated", "longform_blocked_provider", "provider_recovered",
)


def record_event(name: str) -> None:
    if name not in _COUNTER_NAMES:
        return
    with _counters_lock:
        _counters[name] += 1
    log.info("openai_quota_guard event=%s count=%d", name, _counters[name])


def get_counters() -> dict[str, int]:
    with _counters_lock:
        return {name: _counters.get(name, 0) for name in _COUNTER_NAMES}


# -------------------------------------------------------------- telegram alert

def _telegram_config() -> tuple[str, str]:
    return (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip(), (os.getenv("TELEGRAM_CHAT_ID") or "").strip()


def send_telegram_alert(text: str) -> bool:
    """Never raises. Returns False (and logs, not sends) when Telegram isn't
    configured -- per spec: don't invent a new integration if one isn't set
    up, degrade to the existing logging mechanism instead."""
    token, chat_id = _telegram_config()
    if not token or not chat_id:
        log.warning("Telegram alert skipped (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not configured): %s",
                    text.replace("\n", " ")[:300])
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=8,
        )
        if resp.status_code != 200:
            log.warning("Telegram alert failed: HTTP %s", resp.status_code)
            return False
        return True
    except Exception as exc:
        log.warning("Telegram alert failed: %s", str(exc)[:200])
        return False


def format_quota_alert(*, stage: str, project_id: int | None, channel_name: str | None,
                       error_class: str, fallback_target: str) -> str:
    # Deliberately excludes secrets/API keys/response headers/full exception
    # body -- only the error class (a fixed short label), never raw exc.body.
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return (
        "OpenAI quota/billing exhausted. AutoSocial switched to fallback mode.\n"
        f"time: {ts}\n"
        f"stage: {stage}\n"
        f"project_id: {project_id if project_id is not None else 'n/a'}\n"
        f"channel: {channel_name or 'n/a'}\n"
        f"error_class: {error_class}\n"
        f"fallback: {fallback_target}"
    )


def format_recovery_alert() -> str:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"OpenAI access restored. Normal generation resumed.\ntime: {ts}"


# ------------------------------------------------------ durable state (SystemLog)

_ALERT_SENT_MARKER = "openai_quota_alert_sent"
_RECOVERED_MARKER = "openai_recovered"
_ALERT_COOLDOWN = timedelta(hours=6)


def _latest_marker(db):
    from app_models import SystemLog
    return (
        db.query(SystemLog)
        .filter(SystemLog.message.in_([_ALERT_SENT_MARKER, _RECOVERED_MARKER]))
        .order_by(SystemLog.created_at.desc())
        .first()
    )


def is_in_fallback_mode(db) -> bool:
    row = _latest_marker(db)
    return bool(row and row.message == _ALERT_SENT_MARKER)


def _should_send_quota_alert(db) -> bool:
    row = _latest_marker(db)
    if row is None or row.message != _ALERT_SENT_MARKER:
        return True  # first event, or we were previously marked recovered
    age = datetime.utcnow() - row.created_at
    return age >= _ALERT_COOLDOWN


def handle_quota_event(db, *, stage: str, project_id: int | None, channel_name: str | None,
                       error_class: str, fallback_target: str) -> bool:
    """Call whenever a quota/billing error actually changed behavior (a Short
    fell back, or a long-form project got blocked). Sends at most one alert
    per _ALERT_COOLDOWN; always returns without raising."""
    from app_models import SystemLog
    try:
        if not _should_send_quota_alert(db):
            return False
        text = format_quota_alert(stage=stage, project_id=project_id, channel_name=channel_name,
                                  error_class=error_class, fallback_target=fallback_target)
        sent = send_telegram_alert(text)
        db.add(SystemLog(level="warning", message=_ALERT_SENT_MARKER,
                         context=json.dumps({"stage": stage, "project_id": project_id,
                                             "channel": channel_name, "error_class": error_class,
                                             "telegram_sent": sent}, ensure_ascii=False)))
        db.commit()
        return sent
    except Exception as exc:
        log.warning("handle_quota_event failed: %s", str(exc)[:200])
        return False


def handle_recovery_event(db) -> bool:
    """Call after a generation call succeeds via the real OpenAI path (not
    fallback). No-op if we weren't in fallback mode -- safe to call on every
    successful generation."""
    from app_models import SystemLog
    try:
        if not is_in_fallback_mode(db):
            return False
        sent = send_telegram_alert(format_recovery_alert())
        db.add(SystemLog(level="info", message=_RECOVERED_MARKER,
                         context=json.dumps({"telegram_sent": sent}, ensure_ascii=False)))
        db.commit()
        record_event("provider_recovered")
        return sent
    except Exception as exc:
        log.warning("handle_recovery_event failed: %s", str(exc)[:200])
        return False
