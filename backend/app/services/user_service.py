"""Business logic for user accounts.

The service layer orchestrates user-related use cases: it hashes credentials,
maps database uniqueness failures to HTTP conflicts, and delegates persistence
to the CRUD layer. Routers should depend on this module rather than calling
CRUD functions directly.
"""

from sqlalchemy.exc import IntegrityError
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.crud.user_crud import create_user, get_user_by_email as get_user_by_email_crud, get_user_by_username as get_user_by_username_crud
from app.models.user_model import User
from app.schemas.user_schema import Token, UserCreate, UserLogin
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Return the user with the given email, or ``None`` if no match exists.

    Delegates persistence lookup to ``user_crud.get_user_by_email``.
    """
    return await get_user_by_email_crud(db, email)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Return the user with the given username, or ``None`` if no match exists.

    Delegates persistence lookup to ``user_crud.get_user_by_username``.
    """
    return await get_user_by_username_crud(db, username)


async def check_email_exists(db: AsyncSession, email: str) -> bool:
    """Return whether an account already uses the given email.

    Backs the availability-check endpoint so the registration form can give
    field-level feedback as the user types. Registration itself does not rely
    on this check; the database unique constraint is the race-safe guard.
    """
    return await get_user_by_email_crud(db, email) is not None


async def check_username_exists(db: AsyncSession, username: str) -> bool:
    """Return whether an account already uses the given username.

    Backs the availability-check endpoint so the registration form can give
    field-level feedback as the user types. Registration itself does not rely
    on this check; the database unique constraint is the race-safe guard.
    """
    return await get_user_by_username_crud(db, username) is not None


async def register_user(db: AsyncSession, user: UserCreate) -> User:
    """Register a new user and return the persisted account.

    Hashes the raw password, then persists via the CRUD layer. On a unique
    constraint violation for email or username, rolls back the session and
    raises ``409 CONFLICT`` with a generic conflict message.
    """
    hashed_password = get_password_hash(user.password)

    try:
        return await create_user(db, user, hashed_password)

    except IntegrityError:
        await db.rollback()

        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = "A user with this email or username already exists.",
        )


async def authenticate_user(db: AsyncSession, credentials: UserLogin) -> Token:
    """Verify login credentials and return a signed JWT access token.

    Looks up the user by email and verifies the password against the stored
    hash. Raises ``401 UNAUTHORIZED`` with the same message for unknown emails
    and wrong passwords so callers cannot distinguish missing accounts from
    bad credentials. On success, returns a ``Token`` whose ``access_token``
    uses the user's id as the JWT subject.
    """
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = await get_user_by_email(db, credentials.email)
    if user is None or not verify_password(
        credentials.password, user.hashed_password
    ):
        raise invalid_credentials

    access_token = create_access_token(subject=str(user.id))

    return Token(access_token=access_token)
