"""Async SQLAlchemy engine, session factory, and declarative base.

The database is hosted on Supabase Postgres and accessed asynchronously via
``asyncpg``. ``Base`` is the shared declarative base for all ORM models;
``get_db`` is a FastAPI dependency that yields a request-scoped session.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base class for all ORM models."""


settings = get_settings()

engine = create_async_engine(
    str(settings.database_url),
    echo=settings.is_development,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped ``AsyncSession`` and ensure it is closed.

    Use as a FastAPI dependency: ``db: AsyncSession = Depends(get_db)``.
    """
    async with AsyncSessionLocal() as session:
        yield session
