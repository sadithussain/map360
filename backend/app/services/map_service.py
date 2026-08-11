"""Business logic for group map state and location pins."""

from uuid import UUID

from app.crud.activity_crud import create_activity_event
from app.crud.generation_crud import (
    get_map_object_for_group,
    list_map_objects_for_group,
)
from app.crud.generation_crud import (
    update_map_object_transform as update_map_object_transform_crud,
)
from app.crud.group_crud import get_membership as get_membership_crud
from app.crud.location_pin_crud import (
    create_location_pin as create_location_pin_crud,
)
from app.crud.location_pin_crud import (
    delete_all_location_pins_for_group as delete_all_location_pins_for_group_crud,
)
from app.crud.location_pin_crud import (
    delete_location_pin as delete_location_pin_crud,
)
from app.crud.location_pin_crud import (
    get_location_pin as get_location_pin_crud,
)
from app.crud.location_pin_crud import (
    list_rendered_location_pins_for_group,
)
from app.models.activity_model import (
    ACTIVITY_EVENT_PIN_CREATED,
    ACTIVITY_TARGET_PIN,
)
from app.models.location_pin_model import LocationPin
from app.models.map_object_model import MapObject
from app.models.user_model import User
from app.schemas.map_schema import (
    MAX_MAP_OBJECT_SCALE,
    MIN_MAP_OBJECT_SCALE,
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


def _map_object_to_response(obj: MapObject) -> MapObjectResponse:
    """Build a map-object response, pulling ``osm_building_id`` from the pin.

    Assumes ``obj.pin`` was eager-loaded by the CRUD layer.
    """
    return MapObjectResponse(
        id=obj.id,
        pin_id=obj.pin_id,
        osm_building_id=obj.pin.osm_building_id,
        lat=obj.lat,
        lng=obj.lng,
        mesh_public_url=obj.mesh_public_url,
        heading=obj.heading if obj.heading is not None else 0.0,
        scale=obj.scale if obj.scale is not None else 1.0,
    )


async def get_map_state(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> MapStateResponse:
    """Return the map state for a group the authenticated user belongs to."""
    await _require_group_membership(db, group_id, current_user)

    pins = await list_rendered_location_pins_for_group(db, group_id)
    map_objects = await list_map_objects_for_group(db, group_id)
    return MapStateResponse(
        group_id=group_id,
        pins=[_pin_to_response(pin) for pin in pins],
        objects=[_map_object_to_response(obj) for obj in map_objects],
    )


async def list_map_objects(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
    *,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[MapObjectResponse]:
    """List a group's map objects, optionally filtered by a lng/lat bbox."""
    await _require_group_membership(db, group_id, current_user)

    map_objects = await list_map_objects_for_group(db, group_id, bbox=bbox)
    return [_map_object_to_response(obj) for obj in map_objects]


async def get_map_object(
    db: AsyncSession,
    group_id: UUID,
    object_id: UUID,
    current_user: User,
) -> MapObjectResponse:
    """Return a single map object (with its mesh URL) scoped to a group."""
    await _require_group_membership(db, group_id, current_user)

    obj = await get_map_object_for_group(db, group_id, object_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Map object not found in this group.",
        )
    return _map_object_to_response(obj)


async def update_map_object_transform(
    db: AsyncSession,
    group_id: UUID,
    object_id: UUID,
    current_user: User,
    *,
    heading: float,
    scale: float,
) -> MapObjectResponse:
    """Adjust a placed map object's yaw ``heading`` and uniform ``scale``.

    Any member of the group may adjust the transform (no owner/role check).
    Normalizes ``heading`` into ``[0, 360)`` and clamps ``scale`` into
    ``[MIN_MAP_OBJECT_SCALE, MAX_MAP_OBJECT_SCALE]`` before persisting.
    """
    await _require_group_membership(db, group_id, current_user)

    obj = await get_map_object_for_group(db, group_id, object_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Map object not found in this group.",
        )

    normalized_heading = heading % 360.0
    clamped_scale = max(MIN_MAP_OBJECT_SCALE, min(MAX_MAP_OBJECT_SCALE, scale))
    obj = await update_map_object_transform_crud(
        db, obj, heading=normalized_heading, scale=clamped_scale
    )
    return _map_object_to_response(obj)


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

    # Record the contribution on the group's activity timeline within the same
    # transaction so the feed never drifts from the pins it describes.
    await create_activity_event(
        db,
        group_id=group_id,
        actor_user_id=current_user.id,
        event_type=ACTIVITY_EVENT_PIN_CREATED,
        target_type=ACTIVITY_TARGET_PIN,
        target_id=pin.id,
        payload={
            "label": pin.label,
            "lat": pin.lat,
            "lng": pin.lng,
            "osm_building_id": pin.osm_building_id,
            "pin_id": str(pin.id),
        },
    )

    await db.commit()
    await db.refresh(pin)
    return _pin_to_response(pin)


async def delete_location_pin(
    db: AsyncSession,
    group_id: UUID,
    pin_id: UUID,
    current_user: User,
) -> None:
    """Delete a pin (and its submissions/objects) from a group.

    Used to roll back a pin whose upload never started a generation, so empty
    pins are never left behind. Enforces group membership and pin scope.
    """
    await _require_group_membership(db, group_id, current_user)

    pin = await get_location_pin_crud(db, pin_id)
    if pin is None or pin.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location pin not found in this group.",
        )

    await delete_location_pin_crud(db, pin)
    await db.commit()


async def delete_all_location_pins(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> int:
    """Delete every pin in a group (and cascaded submissions/objects).

    Intended for test/dev map resets. Enforces group membership. Returns the
    number of pins removed.
    """
    await _require_group_membership(db, group_id, current_user)
    deleted = await delete_all_location_pins_for_group_crud(db, group_id)
    await db.commit()
    return deleted
