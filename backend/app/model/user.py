from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class GeoPoint(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=1, max_length=32)
    avatar_url: str | None = None


class User(UserBase):
    id: UUID
    last_location: GeoPoint | None = None
    location_updated_at: datetime | None = None
    active_group_id: UUID | None = None
    xp_score: int = Field(0, ge=0)
    models_generated: int = Field(0, ge=0)
    created_at: datetime
    updated_at: datetime | None = None


class UserInDB(User):
    hashed_password: str


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=32)
    avatar_url: str | None = None
    active_group_id: UUID | None = None


class UserLocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class UserPublic(BaseModel):
    id: UUID
    username: str
    avatar_url: str | None = None
    xp_score: int
    models_generated: int
