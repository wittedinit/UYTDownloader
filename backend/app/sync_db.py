"""Shared synchronous DB engine for Celery workers. Avoids creating a new engine per call."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True, pool_size=5, max_overflow=10)
sync_session_factory = sessionmaker(sync_engine, expire_on_commit=False)


def get_sync_session() -> Session:
    """Get a sync DB session for use in Celery workers."""
    return sync_session_factory()
