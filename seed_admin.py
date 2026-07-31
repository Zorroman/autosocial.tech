from database import SessionLocal
from migrations import run_migrations
from saas_auth import hash_password
from saas_models import AppUser, Plan
from saas_services import ensure_user_plan_and_credits, get_or_create_default_project, log_event, seed_plans


if __name__ == "__main__":
    import os

    run_migrations()
    seed_plans()

    email = os.getenv("ADMIN_EMAIL", "admin@autosocial.local").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "admin12345").strip()

    db = SessionLocal()
    try:
        existing = db.query(AppUser).filter_by(email=email).first()
        if existing:
            ensure_user_plan_and_credits(existing.id)
            print(f"Admin already exists: {email}")
        else:
            pro = db.query(Plan).filter_by(name="pro").first()
            admin = AppUser(
                email=email,
                password_hash=hash_password(password),
                role="admin",
                plan="pro",
                plan_id=pro.id if pro else None,
                billing_status="active",
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            ensure_user_plan_and_credits(admin.id)
            get_or_create_default_project(admin.id)
            log_event("admin_seed_cli", actor_user_id=admin.id, context=email)
            print(f"Admin created: {email}")
    finally:
        db.close()
