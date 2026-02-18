from sqlalchemy import Column, String, DateTime
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    fb_user_id = Column(String, primary_key=True)
    access_token = Column(String)
    page_id = Column(String)
    ig_user_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
