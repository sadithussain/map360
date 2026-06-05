"""create groups and memberships tables

Revision ID: b7f2a9c4d1e3
Revises: de5adc7832ca
Create Date: 2026-06-05 18:13:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7f2a9c4d1e3"
down_revision: str | Sequence[str] | None = "de5adc7832ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_groups_id"), "groups", ["id"], unique=False)
    op.create_index(
        op.f("ix_groups_owner_id"), "groups", ["owner_id"], unique=False
    )

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "group_id", name="uq_membership_user_group"
        ),
    )
    op.create_index(
        op.f("ix_memberships_id"), "memberships", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_memberships_user_id"), "memberships", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_memberships_group_id"),
        "memberships",
        ["group_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_memberships_group_id"), table_name="memberships")
    op.drop_index(op.f("ix_memberships_user_id"), table_name="memberships")
    op.drop_index(op.f("ix_memberships_id"), table_name="memberships")
    op.drop_table("memberships")

    op.drop_index(op.f("ix_groups_owner_id"), table_name="groups")
    op.drop_index(op.f("ix_groups_id"), table_name="groups")
    op.drop_table("groups")
