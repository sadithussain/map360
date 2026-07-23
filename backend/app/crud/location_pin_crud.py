"""Database access helpers for location pins."""

from uuid import UUID

from app.models.location_pin_model import LocationPin
from app.models.map_object_model import MapObject
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


async def list_rendered_location_pins_for_group(
    db: AsyncSession,
    group_id: UUID,
) -> list[LocationPin]:
    """Return only pins that have a successful 3D render (a map object).

    Pins are created alongside an image upload but should stay hidden from the
    map until TRELLIS produces a ``MapObject``. Pins that are still processing,
    failed, or never uploaded are excluded.
    """
    has_map_object = (
        select(MapObject.id)
        .where(MapObject.pin_id == LocationPin.id)
        .exists()
    )
    result = await db.execute(
        select(LocationPin)
        .where(LocationPin.group_id == group_id, has_map_object)
        .order_by(LocationPin.created_at.asc())
    )
    return list(result.scalars().all())


async def get_location_pin(
    db: AsyncSession,
    pin_id: UUID,
) -> LocationPin | None:
    """Return a location pin by id, or ``None`` if it does not exist."""
    result = await db.execute(
        select(LocationPin).where(LocationPin.id == pin_id)
    )
    return result.scalar_one_or_none()


async def delete_location_pin(
    db: AsyncSession,
    pin: LocationPin,
) -> None:
    """Delete a pin via the ORM so submissions/objects cascade-delete."""
    await db.delete(pin)
    await db.flush()


async def delete_all_location_pins_for_group(
    db: AsyncSession,
    group_id: UUID,
) -> int:
    """Delete every pin in a group via the ORM (cascades submissions/objects).

    Returns the number of pins deleted. Used for test/dev map resets.
    """
    pins = await list_location_pins_for_group(db, group_id)
    for pin in pins:
        await db.delete(pin)
    await db.flush()
    return len(pins)
