"""create group invite codes table

Revision ID: c3d8e1f5a2b6
Revises: b7f2a9c4d1e3
Create Date: 2026-06-11 10:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d8e1f5a2b6"
down_revision: str | Sequence[str] | None = "b7f2a9c4d1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "group_invite_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column(
            "created_by_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash", name="uq_group_invite_codes_code_hash"),
    )
    op.create_index(
        op.f("ix_group_invite_codes_id"),
        "group_invite_codes",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_group_invite_codes_group_id"),
        "group_invite_codes",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_group_invite_codes_code_hash"),
        "group_invite_codes",
        ["code_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_group_invite_codes_created_by_id"),
        "group_invite_codes",
        ["created_by_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_group_invite_codes_created_by_id"),
        table_name="group_invite_codes",
    )
    op.drop_index(
        op.f("ix_group_invite_codes_code_hash"),
        table_name="group_invite_codes",
    )
    op.drop_index(
        op.f("ix_group_invite_codes_group_id"),
        table_name="group_invite_codes",
    )
    op.drop_index(
        op.f("ix_group_invite_codes_id"),
        table_name="group_invite_codes",
    )
    op.drop_table("group_invite_codes")
