"""user email verified

Revision ID: 6c3e9b1d4f27
Revises: 02355761a2ba
Create Date: 2026-10-17 12:00:00.000000

Adds when an account confirmed its address; null until then.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '6c3e9b1d4f27'
down_revision: Union[str, Sequence[str], None] = '02355761a2ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "email_verified_at")
