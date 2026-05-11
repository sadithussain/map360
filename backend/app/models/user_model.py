import uuid

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid = True), primary_key = True, default = uuid.uuid4, index = True)
    username = Column(String, unique = True, index = True, nullable = False)
    email = Column(String, unique = True, index = True, nullable = False)
    hashed_password = Column(String, nullable = False)

    experience_points = Column(Integer, default = 0, nullable = False)

    created_at = Column(DateTime, default = lambda: datetime.now(timezone.utc))

    memberships = relationship("Membership", back_populates = "user", cascade = "all, delete-orphan")

    submissions = relationship("Submission", back_populates = "user", cascade = "all, delete-orphan")