"""convert timestamp columns to timezone-aware

Revision ID: a1b2c3d4e5f6
Revises: c3d8e1f5a2b6
Create Date: 2026-06-20 16:45:00.000000

The application stores UTC, timezone-aware datetimes (``datetime.now(UTC)``),
but these columns were originally created as ``TIMESTAMP WITHOUT TIME ZONE``.
asyncpg refuses to bind an offset-aware value to a naive column, which broke
inserts (e.g. user registration). Convert the affected columns to
``TIMESTAMP WITH TIME ZONE`` and interpret any existing naive values as UTC.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "c3d8e1f5a2b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (table, column) pairs that store UTC timestamps.
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("users", "created_at"),
    ("groups", "created_at"),
    ("memberships", "joined_at"),
    ("group_invite_codes", "created_at"),
    ("group_invite_codes", "expires_at"),
    ("group_invite_codes", "revoked_at"),
)


def upgrade() -> None:
    """Upgrade schema."""
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(),
            type_=postgresql.TIMESTAMP(timezone=True),
            existing_nullable=True,
            # Existing naive values were written as UTC; preserve that meaning.
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
