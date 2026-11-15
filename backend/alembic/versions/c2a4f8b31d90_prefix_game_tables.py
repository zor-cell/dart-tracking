"""prefix game tables

Revision ID: c2a4f8b31d90
Revises: b8e3d1470f52
Create Date: 2026-09-07 12:00:00.000000

Renames the tables that belong to a game to `game_*`, with their indexes and sequences.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c2a4f8b31d90'
down_revision: Union[str, Sequence[str], None] = 'b8e3d1470f52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("turns", "game_turns")
    op.rename_table("darts", "game_darts")
    op.rename_table("tracking_events", "game_events")
    op.execute("ALTER INDEX ix_tracking_events_game_id RENAME TO ix_game_events_game_id")
    op.execute("ALTER SEQUENCE tracking_events_id_seq RENAME TO game_events_id_seq")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER SEQUENCE game_events_id_seq RENAME TO tracking_events_id_seq")
    op.execute("ALTER INDEX ix_game_events_game_id RENAME TO ix_tracking_events_game_id")
    op.rename_table("game_events", "tracking_events")
    op.rename_table("game_darts", "darts")
    op.rename_table("game_turns", "turns")
