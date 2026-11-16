"""training limit

Revision ID: c4f8a2d6e913
Revises: b9d3e6f2a174
Create Date: 2026-11-16 15:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4f8a2d6e913'
down_revision: Union[str, Sequence[str], None] = 'b9d3e6f2a174'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("game_training", sa.Column("darts", sa.SmallInteger(), nullable=True))
    op.add_column("game_training", sa.Column("minutes", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("game_training", "minutes")
    op.drop_column("game_training", "darts")
