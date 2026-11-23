"""frame deletions

Revision ID: b7d4e9a2c361
Revises: a4d8e2f61c95
Create Date: 2026-11-23 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7d4e9a2c361'
down_revision: Union[str, Sequence[str], None] = 'a4d8e2f61c95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "frame_deletions",
        sa.Column("game_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("frame_deletions")
