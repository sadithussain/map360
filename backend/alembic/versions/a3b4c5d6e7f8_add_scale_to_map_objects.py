"""add scale to map_objects

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-11 17:45:00.000000

Adds a ``scale`` column (uniform size multiplier applied on top of the
client-side auto-fit) to ``map_objects`` so any group member can shrink or grow
a placed mesh that overlaps neighboring plots. Existing rows default to ``1``
(no change from the auto-fit size).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "map_objects",
        sa.Column(
            "scale",
            sa.Float(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("map_objects", "scale")
