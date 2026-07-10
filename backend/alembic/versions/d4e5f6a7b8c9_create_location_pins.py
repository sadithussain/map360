"""create location_pins table

Revision ID: d4e5f6a7b8c9
Revises: a1b2c3d4e5f6
Create Date: 2026-07-08 21:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "location_pins",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("osm_building_id", sa.BigInteger(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column(
            "building_geometry",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_location_pins_id"), "location_pins", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_location_pins_group_id"),
        "location_pins",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_location_pins_user_id"),
        "location_pins",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_location_pins_osm_building_id"),
        "location_pins",
        ["osm_building_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_location_pins_osm_building_id"), table_name="location_pins"
    )
    op.drop_index(op.f("ix_location_pins_user_id"), table_name="location_pins")
    op.drop_index(op.f("ix_location_pins_group_id"), table_name="location_pins")
    op.drop_index(op.f("ix_location_pins_id"), table_name="location_pins")
    op.drop_table("location_pins")
