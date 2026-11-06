"""deleted player name

Revision ID: 089093d532ff
Revises: 73da01f02259
Create Date: 2026-11-06 16:00:00.000000

A deleted account's entry keeps no name; the API names it in the request's language.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '089093d532ff'
down_revision: Union[str, Sequence[str], None] = '73da01f02259'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DELETED_NAME = "Gelöschter Spieler"


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("players", "display_name", existing_type=sa.String(length=64), nullable=True)
    op.execute(
        sa.text(
            "UPDATE players SET display_name = NULL WHERE display_name = :name"
            " AND user_id IS NULL AND owner_user_id IS NULL"
        ).bindparams(name=_DELETED_NAME)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.text("UPDATE players SET display_name = :name WHERE display_name IS NULL").bindparams(
            name=_DELETED_NAME
        )
    )
    op.alter_column("players", "display_name", existing_type=sa.String(length=64), nullable=False)
