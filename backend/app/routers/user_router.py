"""HTTP routes for user accounts.

Currently exposes user registration. Login, token issuance, and the
``/users/me`` endpoint are implemented in later stages.
"""

from app.db.database import get_db
from app.schemas.user_schema import UserCreate, UserResponse
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
