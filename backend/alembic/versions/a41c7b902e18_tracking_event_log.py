"""tracking event log

Revision ID: a41c7b902e18
Revises: 0e1fed00a0de
Create Date: 2026-09-06 12:00:00.000000

Append-only record of what the tracker claimed and what the players accepted,
which the game's own turn list cannot hold: undo deletes the darts it takes
back. The flag on `games` marks a game as a test run.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a41c7b902e18'
down_revision: Union[str, Sequence[str], None] = '0e1fed00a0de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "games",
        sa.Column(
            "evaluation_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.create_table(
        "tracking_events",
        # A plain sequence, unlike the uuid ids elsewhere: the replay depends on
        # the exact order the rows were written in.
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("player_index", sa.Integer(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("camera_armed", sa.Boolean(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("value", sa.Integer(), nullable=True),
        sa.Column("multiplier", sa.Integer(), nullable=True),
        sa.Column("pos_x", sa.Float(), nullable=True),
        sa.Column("pos_y", sa.Float(), nullable=True),
        sa.Column("failure", sa.String(length=32), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tracking_events_game_id"), "tracking_events", ["game_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_tracking_events_game_id"), table_name="tracking_events")
    op.drop_table("tracking_events")
    op.drop_column("games", "evaluation_enabled")
