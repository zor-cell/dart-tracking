"""user settings language

Revision ID: 73da01f02259
Revises: d8f1b3c6a2e5
Create Date: 2026-11-02 11:00:00.000000

The language an account picked for the frontend, null until it picks one.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '73da01f02259'
down_revision: Union[str, Sequence[str], None] = 'd8f1b3c6a2e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("user_settings", sa.Column("language", sa.String(length=8), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_settings", "language")
