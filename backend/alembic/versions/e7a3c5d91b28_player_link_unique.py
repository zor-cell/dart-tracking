"""player link unique

Revision ID: e7a3c5d91b28
Revises: d4f81b6c2e95
Create Date: 2026-10-21 12:00:00.000000

An address book links an account at most once.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e7a3c5d91b28'
down_revision: Union[str, Sequence[str], None] = 'd4f81b6c2e95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "players_owner_user_id_user_id_key", "players", ["owner_user_id", "user_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("players_owner_user_id_user_id_key", "players", type_="unique")
