"""Authentication dependencies for protecting routes.

Provides ``get_current_user``, a FastAPI dependency that validates the Bearer
JWT issued at login, resolves the ``sub`` claim to a persisted user, and makes
that ``User`` available to protected endpoints. Routers should depend on this
rather than decoding tokens themselves.
"""

from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.crud.user_crud import get_user_by_id
from app.db.database import get_db
from app.models.user_model import User

# tokenUrl points at the login route so OpenAPI/Swagger can authorize requests.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve and return the authenticated user for a request.

    Validates the Bearer token's signature and expiry, reads the ``sub`` claim
    as the user's id, and loads the matching record. Raises ``401`` for any
    missing, malformed, expired, or otherwise unresolvable token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise credentials_exception from exc

    subject = payload.get("sub")
    if subject is None:
        raise credentials_exception

    try:
        user_id = UUID(subject)
    except (ValueError, TypeError) as exc:
        raise credentials_exception from exc

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    return user
