"""game event dart index

Revision ID: 3c9e1f7a2b64
Revises: b17d4e9c05a2
Create Date: 2026-09-15 12:00:00.000000

A removed dart names its position in the visit.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3c9e1f7a2b64'
down_revision: Union[str, Sequence[str], None] = 'b17d4e9c05a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("game_events", sa.Column("dart_index", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("game_events", "dart_index")
