"""SQLAlchemy declarative base for ORM models.

Engine and session wiring is intentionally omitted here; it will be added
once the application has concrete database configuration requirements.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base class for all ORM models."""
