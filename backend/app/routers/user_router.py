"""HTTP routes for user accounts.

Currently exposes user registration. Login, token issuance, and the
``/users/me`` endpoint are implemented in later stages.
"""

from app.crud.user_crud import create_user, get_user_by_email
from app.db.database import get_db
from app.schemas.user_schema import UserCreate, UserResponse
from fastapi import APIRouter, Depends, HTTPException, status
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

    Rejects registration when the email is already in use. The raw password is
    hashed in the CRUD layer before persistence; the response never includes
    credentials.
    """
    existing = await get_user_by_email(db, user.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    return await create_user(db, user)
