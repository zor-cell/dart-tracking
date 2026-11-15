"""user display name

Revision ID: e5c9a13b7402
Revises: f4a1c7d2e903
Create Date: 2026-09-12 10:00:00.000000

Adds the display name, filled with the username for existing accounts.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5c9a13b7402'
down_revision: Union[str, Sequence[str], None] = 'f4a1c7d2e903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Added nullable so existing rows survive the ALTER, backfilled, then made
    # NOT NULL — there is no sensible server-side default for a name.
    op.add_column("users", sa.Column("display_name", sa.String(length=64), nullable=True))
    op.execute("UPDATE users SET display_name = username")
    op.alter_column("users", "display_name", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "display_name")
