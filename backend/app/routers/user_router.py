"""HTTP routes for user accounts.

Exposes user registration and login with JWT issuance. The protected
``/users/me`` endpoint is implemented in a later stage.
"""

from app.db.database import get_db
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
