"""drop unused settings

Revision ID: 9a2d6e4b7c31
Revises: f2b6d8a40c17
Create Date: 2026-10-25 23:00:00.000000

The score pad is always shown and the client detection overlay is gone, so
their two switches go.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9a2d6e4b7c31'
down_revision: Union[str, Sequence[str], None] = 'f2b6d8a40c17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("user_settings", "manual_entry_enabled")
    op.drop_column("user_settings", "debug_client_detection")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "user_settings",
        sa.Column(
            "debug_client_detection",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "manual_entry_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
