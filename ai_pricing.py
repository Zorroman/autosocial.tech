"""Centralized AI pricing catalog and budget enforcement.

Prices change; defaults below carry an effective date and can be overridden
without code changes via the AI_PRICING_JSON env var (same structure).
Unknown model => cost is None (never zero): the UI shows "no data" instead of
pretending an operation was free.

All money values are USD unless stated otherwise.
"""
import json
import os
from datetime import datetime, timedelta

from database import SessionLocal
from app_models import AICostRecord

# unit: what input_units/output_units are measured in for the model.
DEFAULT_PRICING = [
    {
        "provider": "openai", "model": "gpt-4o-mini", "unit": "1M tokens",
        "input_price": 0.15, "output_price": 0.60, "currency": "USD",
        "effective_date": "2025-01-01", "source_note": "openai.com/api/pricing",
    },
    {
        "provider": "openai", "model": "gpt-4o-mini-tts", "unit": "1M characters",
        "input_price": 0.60, "output_price": 12.00, "currency": "USD",
        "effective_date": "2025-06-01", "source_note": "openai.com/api/pricing (tts audio out)",
    },
    # Known-free operations: cost 0 is a fact, distinct from "unknown".
    {
        "provider": "edge", "model": "edge-tts", "unit": "characters",
        "input_price": 0.0, "output_price": 0.0, "currency": "USD",
        "effective_date": "2025-01-01", "source_note": "Edge neural TTS is free",
    },
    {
        "provider": "pexels", "model": "stock", "unit": "requests",
        "input_price": 0.0, "output_price": 0.0, "currency": "USD",
        "effective_date": "2025-01-01", "source_note": "Pexels API free tier",
    },
    {
        "provider": "local", "model": "ffmpeg", "unit": "renders",
        "input_price": 0.0, "output_price": 0.0, "currency": "USD",
        "effective_date": "2025-01-01", "source_note": "local render, no monetary cost",
    },
]


def pricing_table() -> list[dict]:
    raw = (os.getenv("AI_PRICING_JSON") or "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    return DEFAULT_PRICING


def find_price(provider: str, model: str) -> dict | None:
    for row in pricing_table():
        if row.get("provider") == provider and row.get("model") == model:
            return row
    return None


def estimate_cost(provider: str, model: str, input_units: float | None, output_units: float | None) -> float | None:
    """Returns estimated cost in the table currency, or None when unknown."""
    price = find_price(provider, model)
    if not price:
        return None
    unit = str(price.get("unit") or "")
    divisor = 1_000_000.0 if unit.startswith("1M") else 1.0
    total = 0.0
    if input_units:
        total += (float(input_units) / divisor) * float(price.get("input_price") or 0.0)
    if output_units:
        total += (float(output_units) / divisor) * float(price.get("output_price") or 0.0)
    return round(total, 6)


# ----------------------------------------------------------------- budgets

class BudgetExceeded(Exception):
    pass


def _budget(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


def budgets() -> dict:
    return {
        "daily_ai_budget": _budget("AI_DAILY_BUDGET", "5.0"),
        "monthly_ai_budget": _budget("AI_MONTHLY_BUDGET", "50.0"),
        "max_cost_per_video": _budget("AI_MAX_COST_PER_VIDEO", "2.0"),
        "max_regenerations_per_project": int(_budget("AI_MAX_REGENERATIONS_PER_PROJECT", "10")),
        "max_videos_per_day": int(_budget("AI_MAX_VIDEOS_PER_DAY", "20")),
        "confirm_threshold": _budget("AI_CONFIRM_COST_THRESHOLD", "1.0"),
        "currency": "USD",
    }


def _spent_since(db, since) -> float:
    rows = (
        db.query(AICostRecord)
        .filter(AICostRecord.created_at >= since, AICostRecord.status == "success")
        .all()
    )
    return sum((r.actual_cost if r.actual_cost is not None else (r.estimated_cost or 0.0)) for r in rows)


def spent_summary(db=None) -> dict:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        now = datetime.utcnow()
        day = _spent_since(db, now - timedelta(days=1))
        month = _spent_since(db, now - timedelta(days=30))
        b = budgets()
        return {
            "spent_today": round(day, 4),
            "spent_month": round(month, 4),
            "daily_budget": b["daily_ai_budget"],
            "monthly_budget": b["monthly_ai_budget"],
            "daily_remaining": round(max(0.0, b["daily_ai_budget"] - day), 4),
            "monthly_remaining": round(max(0.0, b["monthly_ai_budget"] - month), 4),
            "currency": b["currency"],
        }
    finally:
        if own:
            db.close()


def check_budget(db, *, project_id: int | None = None, estimated_cost: float | None = None) -> None:
    """Raises BudgetExceeded with a clear message when a paid operation must
    not start. Free (cost==0) operations always pass."""
    if estimated_cost is not None and estimated_cost <= 0:
        return
    b = budgets()
    now = datetime.utcnow()
    day_spent = _spent_since(db, now - timedelta(days=1))
    month_spent = _spent_since(db, now - timedelta(days=30))
    projected = estimated_cost or 0.0
    if day_spent + projected > b["daily_ai_budget"]:
        raise BudgetExceeded(
            f"Daily AI budget exceeded: spent {day_spent:.2f} of {b['daily_ai_budget']:.2f} {b['currency']}"
        )
    if month_spent + projected > b["monthly_ai_budget"]:
        raise BudgetExceeded(
            f"Monthly AI budget exceeded: spent {month_spent:.2f} of {b['monthly_ai_budget']:.2f} {b['currency']}"
        )
    if project_id:
        rows = (
            db.query(AICostRecord)
            .filter(AICostRecord.project_id == project_id, AICostRecord.status == "success")
            .all()
        )
        video_spent = sum((r.actual_cost if r.actual_cost is not None else (r.estimated_cost or 0.0)) for r in rows)
        if video_spent + projected > b["max_cost_per_video"]:
            raise BudgetExceeded(
                f"Per-video AI budget exceeded: spent {video_spent:.2f} of {b['max_cost_per_video']:.2f} {b['currency']}"
            )
        regen_count = (
            db.query(AICostRecord)
            .filter(AICostRecord.project_id == project_id,
                    AICostRecord.operation_type == "regeneration").count()
        )
        if regen_count >= b["max_regenerations_per_project"]:
            raise BudgetExceeded(f"Max regenerations reached ({regen_count})")


def record_cost(
    *,
    provider: str,
    operation_type: str,
    model: str | None = None,
    channel_id: int | None = None,
    project_id: int | None = None,
    request_id: str | None = None,
    input_units: float | None = None,
    output_units: float | None = None,
    audio_characters: int | None = None,
    image_count: int | None = None,
    video_seconds: float | None = None,
    actual_cost: float | None = None,
    status: str = "success",
    error: str | None = None,
    db=None,
) -> AICostRecord | None:
    """Persist one cost record after a real operation. Idempotent on
    (operation_type, request_id) when request_id is provided."""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        if request_id:
            existing = (
                db.query(AICostRecord)
                .filter_by(operation_type=operation_type, request_id=request_id)
                .first()
            )
            if existing:
                return existing
        est = estimate_cost(provider, model or "", input_units, output_units)
        price = find_price(provider, model or "")
        rec = AICostRecord(
            channel_id=channel_id,
            project_id=project_id,
            provider=provider,
            model=model,
            operation_type=operation_type,
            request_id=request_id,
            input_units=input_units,
            output_units=output_units,
            audio_characters=audio_characters,
            image_count=image_count,
            video_seconds=video_seconds,
            estimated_cost=est,
            actual_cost=actual_cost,
            currency=(price or {}).get("currency") if (price or actual_cost is not None) else None,
            status=status,
            error=error,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec
    except Exception:
        db.rollback()
        return None
    finally:
        if own:
            db.close()
