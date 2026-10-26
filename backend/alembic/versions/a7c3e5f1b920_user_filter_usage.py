"""user filter usage

Revision ID: a7c3e5f1b920
Revises: d4b7e2a9c1f6
Create Date: 2026-10-26 22:30:00.000000

The filters an account picks in its lists, kept for the client to rank its suggestions.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a7c3e5f1b920'
down_revision: Union[str, Sequence[str], None] = 'd4b7e2a9c1f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_settings",
        sa.Column(
            "filter_usage",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_settings", "filter_usage")
