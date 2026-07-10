"""Database access helpers for location pins."""

from uuid import UUID

from app.models.location_pin_model import LocationPin
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def create_location_pin(
    db: AsyncSession,
    *,
    group_id: UUID,
    user_id: UUID,
    osm_building_id: int,
    lat: float,
    lng: float,
    building_geometry: dict,
    label: str | None,
) -> LocationPin:
    """Persist a new location pin for a group."""
    pin = LocationPin(
        group_id=group_id,
        user_id=user_id,
        osm_building_id=osm_building_id,
        lat=lat,
        lng=lng,
        building_geometry=building_geometry,
        label=label,
    )
    db.add(pin)
    await db.flush()
    await db.refresh(pin)
    return pin


async def list_location_pins_for_group(
    db: AsyncSession,
    group_id: UUID,
) -> list[LocationPin]:
    """Return all location pins for a group, oldest first."""
    result = await db.execute(
        select(LocationPin)
        .where(LocationPin.group_id == group_id)
        .order_by(LocationPin.created_at.asc())
    )
    return list(result.scalars().all())
