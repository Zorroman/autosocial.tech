from database import SessionLocal
from models import User

db = SessionLocal()
for user in db.query(User).all():
    print("fb_user_id:", user.fb_user_id)
    print("page_id:", user.page_id)
    print("ig_user_id:", user.ig_user_id)
    print("access_token:", user.access_token[:10] + "...")  # укоротим для безопасности
    print("-" * 40)