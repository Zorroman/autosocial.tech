from datetime import datetime

from database import SessionLocal
from app_models import AppUser
from app_services import create_daily_blog_post, reset_monthly_credits, run_due_content_plan, seed_plans


def run_daily_jobs() -> None:
    seed_plans()
    run_due_content_plan(limit=500)
    create_daily_blog_post()


def run_monthly_regrant() -> None:
    seed_plans()
    db = SessionLocal()
    try:
        users = db.query(AppUser).all()
        for user in users:
            plan_name = user.plan or "free"
            reset_monthly_credits(user.id, plan_name)
    finally:
        db.close()


if __name__ == "__main__":
    # Basic daily execution entrypoint (for Windows Task Scheduler / cron)
    run_daily_jobs()
    print(f"Daily jobs completed at {datetime.utcnow().isoformat()}Z")
