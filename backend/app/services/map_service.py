"""Business logic for group map state and location pins."""

from uuid import UUID

from app.crud.generation_crud import list_map_objects_for_group
from app.crud.group_crud import get_membership as get_membership_crud
from app.crud.location_pin_crud import (
    create_location_pin as create_location_pin_crud,
)
from app.crud.location_pin_crud import (
    list_location_pins_for_group,
)
from app.models.location_pin_model import LocationPin
from app.models.user_model import User
from app.schemas.map_schema import (
    LocationPinCreate,
    LocationPinResponse,
    MapObjectResponse,
    MapStateResponse,
)
from app.services.group_service import get_group_by_id
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


def _geometry_bounds(geometry: dict) -> tuple[float, float, float, float]:
    """Return min_lng, min_lat, max_lng, max_lat for a polygon geometry."""

    def walk_coords(node: object) -> list[tuple[float, float]]:
        if not isinstance(node, list) or len(node) == 0:
            return []

        if isinstance(node[0], (int, float)):
            return [(float(node[0]), float(node[1]))]

        points: list[tuple[float, float]] = []
        for child in node:
            points.extend(walk_coords(child))
        return points

    points = walk_coords(geometry.get("coordinates", []))
    if not points:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="building_geometry has no coordinates.",
        )

    lngs = [point[0] for point in points]
    lats = [point[1] for point in points]
    return min(lngs), min(lats), max(lngs), max(lats)


def _centroid_inside_geometry(
    lat: float,
    lng: float,
    geometry: dict,
    *,
    tolerance: float = 0.002,
) -> bool:
    min_lng, min_lat, max_lng, max_lat = _geometry_bounds(geometry)
    return (
        min_lng - tolerance <= lng <= max_lng + tolerance
        and min_lat - tolerance <= lat <= max_lat + tolerance
    )


async def _require_group_membership(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> None:
    await get_group_by_id(db, group_id)

    membership = await get_membership_crud(db, group_id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group.",
        )


def _pin_to_response(pin: LocationPin) -> LocationPinResponse:
    return LocationPinResponse.model_validate(pin)


async def get_map_state(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> MapStateResponse:
    """Return the map state for a group the authenticated user belongs to."""
    await _require_group_membership(db, group_id, current_user)

    pins = await list_location_pins_for_group(db, group_id)
    map_objects = await list_map_objects_for_group(db, group_id)
    return MapStateResponse(
        group_id=group_id,
        pins=[_pin_to_response(pin) for pin in pins],
        objects=[MapObjectResponse.model_validate(obj) for obj in map_objects],
    )


async def create_location_pin(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
    payload: LocationPinCreate,
) -> LocationPinResponse:
    """Create a location pin tied to a base-map building footprint."""
    await _require_group_membership(db, group_id, current_user)

    if not _centroid_inside_geometry(
        payload.lat,
        payload.lng,
        payload.building_geometry,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="lat and lng must fall within the building geometry bounds.",
        )

    pin = await create_location_pin_crud(
        db,
        group_id=group_id,
        user_id=current_user.id,
        osm_building_id=payload.osm_building_id,
        lat=payload.lat,
        lng=payload.lng,
        building_geometry=payload.building_geometry,
        label=payload.label,
    )
    await db.commit()
    await db.refresh(pin)
    return _pin_to_response(pin)
