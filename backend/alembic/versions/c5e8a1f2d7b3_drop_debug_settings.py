"""drop debug settings

Revision ID: c5e8a1f2d7b3
Revises: 9a2d6e4b7c31
Create Date: 2026-10-26 00:30:00.000000

The live debug dumps go; a test run keeps what they were used for.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c5e8a1f2d7b3'
down_revision: Union[str, Sequence[str], None] = '9a2d6e4b7c31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("user_settings", "debug_calibration")
    op.drop_column("user_settings", "debug_detection")


def downgrade() -> None:
    """Downgrade schema."""
    for column in ("debug_detection", "debug_calibration"):
        op.add_column(
            "user_settings",
            sa.Column(column, sa.Boolean(), server_default=sa.false(), nullable=False),
        )
