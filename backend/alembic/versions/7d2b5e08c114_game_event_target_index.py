"""game event target index

Revision ID: 7d2b5e08c114
Revises: 3c9e1f7a2b64
Create Date: 2026-09-20 12:00:00.000000

A moved dart names where it went; `dart_index` names where it came from.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7d2b5e08c114'
down_revision: Union[str, Sequence[str], None] = '3c9e1f7a2b64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("game_events", sa.Column("target_index", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("game_events", "target_index")
