"""game finish rules

Revision ID: b6d2e9f41a73
Revises: a3e8f1c57d20
Create Date: 2026-11-13 12:00:00.000000

How a race ends: whether the round catches up after a finish, and whether play
goes on for the places after the winner.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b6d2e9f41a73'
down_revision: Union[str, Sequence[str], None] = 'a3e8f1c57d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "games",
        sa.Column("catch_up", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "games",
        sa.Column("play_on", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("games", "play_on")
    op.drop_column("games", "catch_up")
