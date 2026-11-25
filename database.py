import os
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///autosocial.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Keep the driver supplied by requirements.txt when SQLAlchemy changes its default.
# Explicit driver choices in DATABASE_URL remain untouched.
engine_url = make_url(DATABASE_URL)
if engine_url.drivername == "postgresql":
    engine_url = engine_url.set(drivername="postgresql+psycopg2")

engine = create_engine(engine_url, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()
