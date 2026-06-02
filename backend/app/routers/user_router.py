"""HTTP routes for user accounts.

Exposes user registration, login with JWT issuance, and the protected
``/users/me`` endpoint for retrieving the authenticated user's profile.
"""

from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.models.user_model import User
from app.schemas.user_schema import Token, UserCreate, UserLogin, UserResponse
from app.services.user_service import authenticate_user
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

    Delegates to the service layer, which rejects registration when the email
    is already in use and hashes the raw password before persistence; the
    response never includes credentials.
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