"""game hides

Revision ID: c5d2a8e7f310
Revises: b3e8f2a6d1c4
Create Date: 2026-11-01 23:00:00.000000

Hiding a game becomes a choice of each account; a discarded game stays hidden for its owner.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c5d2a8e7f310'
down_revision: Union[str, Sequence[str], None] = 'b3e8f2a6d1c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "game_hides",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("game_id", sa.Uuid(), sa.ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    )
    op.execute(
        "INSERT INTO game_hides (user_id, game_id)"
        " SELECT owner_user_id, id FROM games"
        " WHERE status = 'discarded' AND owner_user_id IS NOT NULL"
    )
    op.execute(
        "UPDATE games SET status = CASE WHEN finished_at IS NULL THEN 'active' ELSE 'finished' END"
        " WHERE status = 'discarded'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "UPDATE games SET status = 'discarded' FROM game_hides"
        " WHERE game_hides.game_id = games.id AND game_hides.user_id = games.owner_user_id"
    )
    op.drop_table("game_hides")
