"""player former owner

Revision ID: f2b6d8a40c17
Revises: e7a3c5d91b28
Create Date: 2026-10-21 21:30:00.000000

The address book a linked entry was taken out of.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f2b6d8a40c17'
down_revision: Union[str, Sequence[str], None] = 'e7a3c5d91b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "players",
        sa.Column("former_owner_user_id", sa.Uuid(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        "players_former_owner_user_id_fkey",
        "players",
        "users",
        ["former_owner_user_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("players_former_owner_user_id_fkey", "players", type_="foreignkey")
    op.drop_column("players", "former_owner_user_id")
