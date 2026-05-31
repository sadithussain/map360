"""Business logic for user accounts.

The service layer orchestrates user-related use cases: it validates business
rules (e.g. unique email), hashes credentials, and delegates persistence to the
CRUD layer. Routers should depend on this module rather than calling CRUD
functions directly.
"""

from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.crud.user_crud import create_user, get_user_by_email
from app.models.user_model import User
from app.schemas.user_schema import Token, UserCreate, UserLogin
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


async def register_user(db: AsyncSession, user: UserCreate) -> User:
    """Register a new user and return the persisted account.

    Rejects registration with a ``409 CONFLICT`` when the email is already in
    use. Hashes the raw password before handing the prepared credentials to the
    CRUD layer for persistence.
    """
    existing = await get_user_by_email(db, user.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    hashed_password = get_password_hash(user.password)

    return await create_user(db, user, hashed_password)


async def authenticate_user(db: AsyncSession, credentials: UserLogin) -> Token:
    """Verify login credentials and return a signed access token.

    Looks up the user by email and checks the password against the stored
    bcrypt hash. Raises ``401 UNAUTHORIZED`` with a generic message for both
    unknown emails and bad passwords so callers cannot probe which accounts
    exist. On success, issues a JWT whose subject is the user's id.
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
