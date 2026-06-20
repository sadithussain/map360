"""Async SQLAlchemy engine, session factory, and declarative base.

The database is hosted on Supabase Postgres and accessed asynchronously via
``asyncpg``. ``Base`` is the shared declarative base for all ORM models;
``get_db`` is a FastAPI dependency that yields a request-scoped session.
"""

import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base class for all ORM models."""


def transaction_pooler_connect_args(database_url: str) -> dict | None:
    """Return asyncpg ``connect_args`` required by Supabase's transaction pooler.

    asyncpg prepares every statement server-side and caches it by name. Supabase's
    transaction pooler (PgBouncer on port 6543) recycles backend connections
    between clients and cannot track those prepared statements, producing errors
    such as ``prepared statement "__asyncpg_stmt_x__" does not exist``. To stay
    compatible we disable both asyncpg statement caches and generate a unique name
    for every prepared statement.

    Returns ``None`` for direct or session-mode connections, so those keep normal
    prepared-statement caching for better performance.
    """
    if ":6543" not in database_url:
        return None
    return {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
    }


settings = get_settings()
_database_url = str(settings.database_url)

_engine_kwargs: dict = {"echo": settings.is_development}
if (_pooler_args := transaction_pooler_connect_args(_database_url)) is not None:
    # PgBouncer owns connection pooling; NullPool avoids a redundant second pool.
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs["connect_args"] = _pooler_args
else:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(_database_url, **_engine_kwargs)

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
