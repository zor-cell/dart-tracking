"""training any ring

Revision ID: b9d3e6f2a174
Revises: c8e4f1a26d93
Create Date: 2026-11-16 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b9d3e6f2a174'
down_revision: Union[str, Sequence[str], None] = 'c8e4f1a26d93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "game_training",
        sa.Column("any_ring", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("game_training", "any_ring")
