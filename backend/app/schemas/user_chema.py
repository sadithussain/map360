from pydantic import BaseModel, EmailStr, Field, ConfigDict
from uuid import UUID
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(..., min_length = 3, max_length = 50, description = "The user's unique display name")
    email: EmailStr = Field(..., description = "The user's email address")

class UserCreate(UserBase):
    password: str = Field(..., min_length = 8, max_length = 100, description = "Raw, unhashed password")

class UserResponse(UserBase):
    id: UUID
    experience_points: int
    created_at: datetime

    model_config = ConfigDict(from_attributes = True)