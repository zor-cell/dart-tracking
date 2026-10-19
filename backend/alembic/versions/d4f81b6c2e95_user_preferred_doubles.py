"""user preferred doubles

Revision ID: d4f81b6c2e95
Revises: 6c3e9b1d4f27
Create Date: 2026-10-19 12:00:00.000000

The finishing doubles an account wants the checkout to suggest first.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4f81b6c2e95'
down_revision: Union[str, Sequence[str], None] = '6c3e9b1d4f27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_settings",
        sa.Column(
            "preferred_doubles",
            sa.ARRAY(sa.Integer()),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_settings", "preferred_doubles")
