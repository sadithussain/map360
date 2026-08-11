"""add heading to map_objects

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-08 22:20:00.000000

Adds a ``heading`` column (yaw in degrees clockwise from north) to
``map_objects`` so any group member can manually orient a placed mesh after
generation. Existing rows default to ``0`` (TRELLIS's raw orientation).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "map_objects",
        sa.Column(
            "heading",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("map_objects", "heading")
