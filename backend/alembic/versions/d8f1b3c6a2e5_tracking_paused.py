"""tracking paused

Revision ID: d8f1b3c6a2e5
Revises: c5d2a8e7f310
Create Date: 2026-11-01 23:30:00.000000

Whether the camera may book darts in a game, so tracking can be paused.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd8f1b3c6a2e5'
down_revision: Union[str, Sequence[str], None] = 'c5d2a8e7f310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "games",
        sa.Column("tracking_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("games", "tracking_paused")
