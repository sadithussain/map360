"""HTTP routes for user accounts.

Exposes user registration, login with JWT issuance, and the protected
``/users/me`` endpoint for retrieving the authenticated user's profile.
"""

from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.models.user_model import User
from app.schemas.user_schema import Token, UserCreate, UserLogin, UserPasswordChange, UserResponse
from app.services.user_service import authenticate_user, check_email_exists as check_email_exists_service, check_username_exists as check_username_exists_service, change_user_password as change_user_password_service
from app.services.user_service import register_user as register_user_service
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new user and return the created account.

    Delegates to the service layer, which hashes the raw password before
    persistence and returns a generic ``409`` conflict if the email or
    username is already taken; the response never includes credentials.
    """
    return await register_user_service(db, user)


@router.post("/login", response_model=Token)
async def login_user(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate a user and return a signed JWT access token.

    Delegates to the service layer, which verifies the password against the
    stored hash and responds with ``401`` for invalid credentials.
    """
    return await authenticate_user(db, credentials)


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    current_user: User = Depends(get_authenticated_user),
) -> UserResponse:
    """Return the authenticated user's own profile.

    Identity comes from the validated Bearer token via the auth dependency,
    so no user id is accepted from the client. Credentials are never included
    in the ``UserResponse`` output.
    """
    return current_user

@router.get("/exists/email/{email}", response_model=bool)
async def check_email_exists(
    email: str,
    db: AsyncSession = Depends(get_db),
) -> bool:
    """Report whether the given email is already registered.

    Supports field-level feedback while the user fills out the registration
    form. Registration does not depend on this check; the database unique
    constraint remains the race-safe guard against duplicates.
    """
    return await check_email_exists_service(db, email)


@router.get("/exists/username/{username}", response_model=bool)
async def check_username_exists(
    username: str,
    db: AsyncSession = Depends(get_db),
) -> bool:
    """Report whether the given username is already taken.

    Supports field-level feedback while the user fills out the registration
    form. Registration does not depend on this check; the database unique
    constraint remains the race-safe guard against duplicates.
    """
    return await check_username_exists_service(db, username)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_user_password(
    passwords: UserPasswordChange,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change the authenticated user's own password.

    Identity comes from the validated Bearer token, so a client can only
    change its own password. Delegates to the service layer, which verifies
    the current password and hashes the new one before persistence. Returns
    ``204 No Content`` on success.
    """
    await change_user_password_service(db, current_user, passwords)