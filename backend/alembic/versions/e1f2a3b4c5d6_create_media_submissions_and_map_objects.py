"""create media_submissions and map_objects tables

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-07-20 18:45:00.000000

Adds the two tables backing the TRELLIS single-image-to-3D pipeline:
``media_submissions`` tracks each uploaded photo and its async generation job
status, while ``map_objects`` records the generated ``.glb`` placed at a pin's
real-world coordinates for the group map.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "media_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_image_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("mesh_storage_key", sa.String(), nullable=True),
        sa.Column("mesh_public_url", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["pin_id"], ["location_pins.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_media_submissions_id"),
        "media_submissions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_media_submissions_group_id"),
        "media_submissions",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_media_submissions_pin_id"),
        "media_submissions",
        ["pin_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_media_submissions_user_id"),
        "media_submissions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_media_submissions_status"),
        "media_submissions",
        ["status"],
        unique=False,
    )

    op.create_table(
        "map_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("mesh_public_url", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["pin_id"], ["location_pins.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["media_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id", name="uq_map_object_submission"),
    )
    op.create_index(op.f("ix_map_objects_id"), "map_objects", ["id"], unique=False)
    op.create_index(
        op.f("ix_map_objects_group_id"),
        "map_objects",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_map_objects_pin_id"), "map_objects", ["pin_id"], unique=False
    )
    op.create_index(
        op.f("ix_map_objects_submission_id"),
        "map_objects",
        ["submission_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_map_objects_submission_id"), table_name="map_objects")
    op.drop_index(op.f("ix_map_objects_pin_id"), table_name="map_objects")
    op.drop_index(op.f("ix_map_objects_group_id"), table_name="map_objects")
    op.drop_index(op.f("ix_map_objects_id"), table_name="map_objects")
    op.drop_table("map_objects")

    op.drop_index(op.f("ix_media_submissions_status"), table_name="media_submissions")
    op.drop_index(op.f("ix_media_submissions_user_id"), table_name="media_submissions")
    op.drop_index(op.f("ix_media_submissions_pin_id"), table_name="media_submissions")
    op.drop_index(op.f("ix_media_submissions_group_id"), table_name="media_submissions")
    op.drop_index(op.f("ix_media_submissions_id"), table_name="media_submissions")
    op.drop_table("media_submissions")
