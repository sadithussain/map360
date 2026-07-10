"""Pydantic schemas for group map state API responses."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocationPinCreate(BaseModel):
    """Request body for creating a building-tied location pin."""

    osm_building_id: int = Field(..., gt=0)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    building_geometry: dict[str, Any]
    label: str | None = Field(default=None, max_length=200)

    @field_validator("building_geometry")
    @classmethod
    def validate_building_geometry(cls, value: dict[str, Any]) -> dict[str, Any]:
        geometry_type = value.get("type")
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError(
                "building_geometry must be a GeoJSON Polygon or MultiPolygon."
            )

        coordinates = value.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) == 0:
            raise ValueError("building_geometry coordinates are required.")

        return value


class LocationPinResponse(BaseModel):
    """A real-world location pin on a group's map."""

    id: UUID
    osm_building_id: int
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
