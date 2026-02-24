import importlib
import os
import sys
from datetime import datetime, timedelta

import pytest


@pytest.fixture()
def db_modules(tmp_path):
    db_file = tmp_path / "ai_score_forecast.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    for name in ["database", "saas_models", "dashboard_metrics", "migrations"]:
        if name in sys.modules:
            del sys.modules[name]
    database = importlib.import_module("database")
    saas_models = importlib.import_module("saas_models")
    migrations = importlib.import_module("migrations")
    dashboard_metrics = importlib.import_module("dashboard_metrics")
    saas_models.SaaSBase.metadata.create_all(bind=database.engine)
    migrations.run_migrations()
    return database, saas_models, dashboard_metrics


def test_compute_ai_score_range_and_zero_safe(db_modules):
    database, models, dashboard_metrics = db_modules
    db = database.SessionLocal()
    try:
        user = models.AppUser(email="score@test.local", password_hash="hash")
        db.add(user)
        db.commit()
        db.refresh(user)

        # Zero-data path should not crash and must stay inside 0..100.
        payload_zero = dashboard_metrics.compute_ai_score(db, user.id, days=30)
        assert 0.0 <= float(payload_zero.get("total") or 0.0) <= 100.0
        assert len(payload_zero.get("factors") or []) == 5

        acc = models.ConnectedAccount(user_id=user.id, platform="meta", external_id="page-1", display_name="Page")
        db.add(acc)
        db.commit()
        db.refresh(acc)

        item = models.ContentItem(
            user_id=user.id,
            platform="meta",
            external_id="post-1",
            account_id=acc.id,
            content_type="post",
            title="Post",
            published_at=datetime.utcnow() - timedelta(days=3),
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        for i in range(8):
            db.add(
                models.ContentMetricDaily(
                    content_item_id=item.id,
                    day=(datetime.utcnow() - timedelta(days=i)).date(),
                    reach=100 + i * 5,
                    views=120 + i * 5,
                    clicks=5 + i,
                    likes=10 + i,
                    comments=2,
                    shares=1,
                )
            )
        db.commit()

        payload = dashboard_metrics.compute_ai_score(db, user.id, days=30)
        assert 0.0 <= float(payload.get("total") or 0.0) <= 100.0
        assert len(payload.get("factors") or []) == 5
    finally:
        db.close()


def test_compute_forecast_points_and_non_negative(db_modules):
    database, models, dashboard_metrics = db_modules
    db = database.SessionLocal()
    try:
        user = models.AppUser(email="forecast@test.local", password_hash="hash")
        db.add(user)
        db.commit()
        db.refresh(user)

        acc = models.ConnectedAccount(user_id=user.id, platform="meta", external_id="page-2", display_name="Page2")
        db.add(acc)
        db.commit()
        db.refresh(acc)

        item = models.ContentItem(
            user_id=user.id,
            platform="meta",
            external_id="post-2",
            account_id=acc.id,
            content_type="post",
            title="Post 2",
            published_at=datetime.utcnow() - timedelta(days=1),
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        for i in range(20):
            db.add(
                models.ContentMetricDaily(
                    content_item_id=item.id,
                    day=(datetime.utcnow() - timedelta(days=i)).date(),
                    reach=80 + i * 3,
                    views=90 + i * 3,
                    clicks=3 + (i % 4),
                    likes=8 + (i % 5),
                    comments=1 + (i % 2),
                    shares=1,
                )
            )
        db.commit()

        forecast = dashboard_metrics.compute_forecast(db, user.id, horizon_days=7, history_days=90)
        points = forecast.get("points") or []
        assert len(points) == 7
        assert all(float(p.get("reach") or 0) >= 0 for p in points)
        assert all(float(p.get("views") or 0) >= 0 for p in points)
    finally:
        db.close()
