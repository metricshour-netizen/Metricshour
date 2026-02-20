from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import settings


def _make_engine():
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,   # reconnect if connection dropped
        pool_size=10,
        max_overflow=20,
    )


# Engine is created lazily on first use so the app imports cleanly without a DB
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_session_factory():
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


# Convenience alias used by seeders
def SessionLocal() -> Session:
    return get_session_factory()()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and always closes it."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
