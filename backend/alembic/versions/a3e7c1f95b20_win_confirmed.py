"""win confirmed

Revision ID: a3e7c1f95b20
Revises: 089093d532ff
Create Date: 2026-11-06 17:00:00.000000

Whether the room has taken the win, so every device shows the finished screen.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a3e7c1f95b20'
down_revision: Union[str, Sequence[str], None] = '089093d532ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "games",
        sa.Column("win_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("games", "win_confirmed")
