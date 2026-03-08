from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import settings


def _make_engine():
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,        # reconnect if connection dropped
        pool_size=2,               # Aiven has strict connection limits; keep pool tiny
        max_overflow=3,            # max 5 total connections from this process
        pool_recycle=300,
        connect_args={
            "prepare_threshold": None,  # disable prepared statements (Aiven compatibility)
        },
    )


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_session_factory():
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


def SessionLocal() -> Session:
    return get_session_factory()()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and always closes it."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
