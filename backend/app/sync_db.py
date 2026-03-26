"""Shared synchronous DB session — re-exports from database.py.

This module exists for backward compatibility. All sync session usage
should go through database.get_sync_session() which uses a single
shared connection pool.
"""

from app.database import _sync_engine as sync_engine, get_sync_session

__all__ = ["sync_engine", "get_sync_session"]
