"""Pydantic schemas for group map state API responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LocationPinResponse(BaseModel):
    """A real-world location pin on a group's map."""

    id: UUID
    lat: float
    lng: float
    label: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MapObjectResponse(BaseModel):
    """A user-generated 3D object placed on the map at a pin location."""

    id: UUID
    pin_id: UUID
    lat: float
    lng: float

    model_config = ConfigDict(from_attributes=True)


class MapStateResponse(BaseModel):
    """Aggregated map state for a group, returned to the frontend."""

    group_id: UUID
    pins: list[LocationPinResponse] = Field(default_factory=list)
    objects: list[MapObjectResponse] = Field(default_factory=list)
