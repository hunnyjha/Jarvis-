"""
JARVIS Database — Async SQLAlchemy engine, session factory, and dependencies.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


# Engine and session factory (initialized lazily)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG and not settings.is_production,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session.
    Automatically commits on success and rolls back on error.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions (for use outside FastAPI)."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database — create tables if they don't exist."""
    engine = get_engine()
    async with engine.begin() as conn:
        # Import all models to ensure they're registered with Base
        from app.models import (  # noqa: F401
            audit,
            memory,
            reddit,
            report,
            research,
            security,
            user,
        )
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")


async def close_db() -> None:
    """Close database connections on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    logger.info("Database connections closed")


# Compatibility alias used by background tasks in route files
class _AsyncSessionLocal:
    """
    Async context manager that creates a new database session.
    Used as `async with AsyncSessionLocal() as db:` in background tasks.
    """

    def __init__(self) -> None:
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        factory = get_session_factory()
        self._session = factory()
        await self._session.__aenter__()
        return self._session

    async def __aexit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        if self._session is not None:
            if exc_type:
                await self._session.rollback()
            else:
                await self._session.commit()
            await self._session.__aexit__(exc_type, exc_val, exc_tb)
            self._session = None


def AsyncSessionLocal() -> _AsyncSessionLocal:
    """Factory for async database session context managers."""
    return _AsyncSessionLocal()
