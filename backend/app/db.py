"""
SQLAlchemy engine/session setup.

The engine connects to the EXISTING egcivic database (see README "Database
baseline"). Nothing in this module, or anywhere in app/models/, ever calls
Base.metadata.create_all() — the schema was created by database/init/*.sql
and the backend only ever maps onto it.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Shared declarative base for every model in app/models/."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one Session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Used by GET /health — a real round trip to Postgres, not just 'engine exists'."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
