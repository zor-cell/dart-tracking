"""game tracker version

Revision ID: 9a6e2c4d7f31
Revises: 7d2b5e08c114
Create Date: 2026-09-21 12:00:00.000000

The tracker build (CI pipeline number) a game was played with.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9a6e2c4d7f31'
down_revision: Union[str, Sequence[str], None] = '7d2b5e08c114'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("games", sa.Column("tracker_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("games", "tracker_version")
