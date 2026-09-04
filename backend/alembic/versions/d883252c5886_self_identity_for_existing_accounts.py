"""self identity for existing accounts

Revision ID: d883252c5886
Revises: 67f76ee220b7
Create Date: 2026-09-04 16:05:00.000000

From M4 on, registering also creates the account's own entry in its address
book. Accounts that existed before have none, and nothing would ever create it —
so they get one here, named after the username.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd883252c5886'
down_revision: Union[str, Sequence[str], None] = '67f76ee220b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        INSERT INTO players (id, display_name, user_id, owner_user_id)
        SELECT uuidv7(), users.username, users.id, users.id
        FROM users
        WHERE NOT EXISTS (
            SELECT 1 FROM players WHERE players.user_id = users.id
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Only the rows this migration can have created: an identity that is an
    # account and plays in no game yet.
    op.execute(
        """
        DELETE FROM players
        WHERE user_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM game_players WHERE game_players.player_id = players.id
          )
        """
    )
