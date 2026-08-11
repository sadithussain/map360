"""create activity_events table

Revision ID: b8c9d0e1f2a3
Revises: a3b4c5d6e7f8
Create Date: 2026-08-11 18:30:00.000000

Adds the ``activity_events`` table that backs Stage 9 social features (group
activity feed, contributions log, map-growth chart). Each row records a
member action (``pin_created`` or ``object_placed``) with a denormalized
``payload`` snapshot so the feed renders without joining the target row.

To make the feed useful immediately, this migration backfills historical
events from existing ``location_pins`` (pin creations) and ``map_objects``
(mesh placements), attributing each object placement to the member who
uploaded its source image.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "activity_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_activity_events_id"), "activity_events", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_activity_events_group_id"),
        "activity_events",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activity_events_actor_user_id"),
        "activity_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activity_events_event_type"),
        "activity_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activity_events_created_at"),
        "activity_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_group_created_at",
        "activity_events",
        ["group_id", "created_at"],
        unique=False,
    )

    # Backfill: one ``pin_created`` event per existing pin.
    op.execute(
        """
        INSERT INTO activity_events (
            id, group_id, actor_user_id, event_type,
            target_type, target_id, payload, created_at
        )
        SELECT
            gen_random_uuid(),
            p.group_id,
            p.user_id,
            'pin_created',
            'pin',
            p.id,
            jsonb_build_object(
                'label', p.label,
                'lat', p.lat,
                'lng', p.lng,
                'osm_building_id', p.osm_building_id,
                'pin_id', p.id::text
            ),
            p.created_at
        FROM location_pins p
        """
    )

    # Backfill: one ``object_placed`` event per existing map object, attributed
    # to the member who uploaded the source image for its submission.
    op.execute(
        """
        INSERT INTO activity_events (
            id, group_id, actor_user_id, event_type,
            target_type, target_id, payload, created_at
        )
        SELECT
            gen_random_uuid(),
            o.group_id,
            s.user_id,
            'object_placed',
            'map_object',
            o.id,
            jsonb_build_object(
                'label', p.label,
                'lat', o.lat,
                'lng', o.lng,
                'osm_building_id', p.osm_building_id,
                'pin_id', o.pin_id::text,
                'map_object_id', o.id::text
            ),
            o.created_at
        FROM map_objects o
        JOIN media_submissions s ON s.id = o.submission_id
        JOIN location_pins p ON p.id = o.pin_id
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_activity_events_group_created_at", table_name="activity_events")
    op.drop_index(op.f("ix_activity_events_created_at"), table_name="activity_events")
    op.drop_index(op.f("ix_activity_events_event_type"), table_name="activity_events")
    op.drop_index(
        op.f("ix_activity_events_actor_user_id"), table_name="activity_events"
    )
    op.drop_index(op.f("ix_activity_events_group_id"), table_name="activity_events")
    op.drop_index(op.f("ix_activity_events_id"), table_name="activity_events")
    op.drop_table("activity_events")
