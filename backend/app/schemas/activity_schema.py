"""Pydantic schemas for group social / collaborative features.

Covers the activity feed (also used for the contributions log), the map-growth
chart, and the in-map discovery list.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActivityEventResponse(BaseModel):
    """A single event on a group's activity timeline.

    ``payload`` is a denormalized snapshot (label, coordinates, osm building id)
    captured when the event was recorded so the feed renders without joining the
    target row.
    """

    id: UUID
    event_type: str
    actor_user_id: UUID
    actor_username: str
    target_type: str
    target_id: UUID | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityListResponse(BaseModel):
    """A page of activity events, newest first."""

    events: list[ActivityEventResponse] = Field(default_factory=list)


class GrowthPoint(BaseModel):
    """One day on the map-growth chart.

    ``count`` is the number of models placed on ``date``; ``cumulative`` is the
    running total up to and including that day.
    """

    date: str
    count: int
    cumulative: int


class GrowthResponse(BaseModel):
    """Map growth over time for a group."""

    points: list[GrowthPoint] = Field(default_factory=list)
    total: int = 0


class PlaceSummary(BaseModel):
    """A contributed place for the in-map discovery view."""

    pin_id: UUID
    map_object_id: UUID
    label: str | None = None
    lat: float
    lng: float
    contributor_username: str | None = None
    created_at: datetime


class PlacesResponse(BaseModel):
    """Contributed places in a group, newest first."""

    places: list[PlaceSummary] = Field(default_factory=list)
