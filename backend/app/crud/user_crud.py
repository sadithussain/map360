"""Database access helpers for user records.

All functions accept an async SQLAlchemy session and perform queries or
writes against the ``users`` table. Callers are responsible for opening the
session and handling HTTP-level errors (e.g. 404 when a lookup returns None).
"""

from uuid import UUID

from app.models.user_model import User
from app.schemas.user_schema import UserCreate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


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


async def create_user(
    db: AsyncSession, user: UserCreate, hashed_password: str
) -> User:
    """Persist a new user from validated input and a pre-hashed password.

    The service layer is responsible for hashing ``user.password``; this
    function commits the transaction and returns the refreshed ORM instance
    (including server-generated fields).
    """
    db_user = User(
        **user.model_dump(exclude={"password"}),
        hashed_password=hashed_password,
    )

    db.add(db_user)
    await db.commit()

    await db.refresh(db_user)

    return db_user
