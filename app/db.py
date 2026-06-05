from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _make_engine(url: str):
    if "sqlite" in url:
        return create_engine(url, connect_args={"check_same_thread": False})
    # Postgres: use psycopg driver, no special connect_args needed
    return create_engine(url)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
