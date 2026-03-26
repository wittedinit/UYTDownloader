from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# Async engine (for FastAPI endpoints)
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

# Sync engine (for Celery workers and services)
_sync_engine = create_engine(settings.database_url_sync, echo=False, pool_pre_ping=True, pool_size=5, max_overflow=10)
_sync_session_factory = sessionmaker(bind=_sync_engine, expire_on_commit=False)


def get_sync_session() -> Session:
    """Get a synchronous DB session. Caller must close it."""
    return _sync_session_factory()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
