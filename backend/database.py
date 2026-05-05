import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


ENV = os.getenv("ENV", "development")


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if ENV == "development":
        DATABASE_URL = os.getenv("DEV_DATABASE_URL") or "postgresql+psycopg://postgres:Deimos202212@localhost:5432/lecture_summarizer"
    else:
        raise RuntimeError("DATABASE_URL is not set")


connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
