"""Database access helpers for user records.

All functions accept an async SQLAlchemy session and perform queries or
writes against the ``users`` table. Callers are responsible for opening the
session and handling HTTP-level errors (e.g. 404 when a lookup returns None).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user_model import User
from app.schemas.user_schema import UserCreate


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Return the user with the given email, or None if no match exists."""
    statement = select(User).where(User.email == email)

    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """Return the user with the given primary key, or None if no match exists."""
    statement = select(User).where(User.id == user_id)

    result = await db.execute(statement)

    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user: UserCreate) -> User:
    """Persist a new user from validated registration input.

    Hashes ``user.password`` before insert, commits the transaction, and
    returns the refreshed ORM instance (including server-generated fields).
    """
    hashed_pw = get_password_hash(user.password)

    db_user = User(
        **user.model_dump(exclude={"password"}),
        hashed_password=hashed_pw,
    )

    db.add(db_user)
    await db.commit()

    await db.refresh(db_user)

    return db_user
