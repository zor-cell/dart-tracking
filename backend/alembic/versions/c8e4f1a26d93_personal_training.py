"""personal training

Revision ID: c8e4f1a26d93
Revises: a7c2e5f18d40
Create Date: 2026-11-16 12:00:00.000000

The settings table of the personal training, holding the plan it was started on.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c8e4f1a26d93'
down_revision: Union[str, Sequence[str], None] = 'a7c2e5f18d40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "game_personal",
        sa.Column(
            "game_id", sa.Uuid(as_uuid=False), sa.ForeignKey("games.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("focus", sa.String(length=16), nullable=False),
        sa.Column("length", sa.Integer(), nullable=False),
        sa.Column("any_ring", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("blocks", postgresql.JSONB(), nullable=False),
        sa.Column("baselines", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("game_personal")
