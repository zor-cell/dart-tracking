"""advance on pull

Revision ID: d4b7e2a9c1f6
Revises: c5e8a1f2d7b3
Create Date: 2026-10-26 12:00:00.000000

The confirm switch gives way to handing over once the darts are pulled out.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4b7e2a9c1f6'
down_revision: Union[str, Sequence[str], None] = 'c5e8a1f2d7b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_settings",
        sa.Column("advance_on_pull", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.drop_column("user_settings", "confirm_throw_enabled")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "user_settings",
        sa.Column("confirm_throw_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.drop_column("user_settings", "advance_on_pull")
