"""HTTP routes for groups.

Exposes group creation. The owning user is resolved from the validated Bearer
token via the auth dependency, so no owner id is accepted from the client.
"""

from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.models.user_model import User
from app.schemas.group_schema import GroupCreate, GroupResponse
from app.services.group_service import create_group as create_group_service
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post(
    "",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_group(
    group: GroupCreate,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> GroupResponse:
    """Create a new group owned by the authenticated user.

    Identity comes from the validated Bearer token, so the owner is never
    trusted from the request. Delegates to the service layer, which creates
    the group and the owner's membership in a single transaction.
    """
    return await create_group_service(db, group, current_user)
