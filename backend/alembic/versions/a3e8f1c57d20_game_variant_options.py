"""game variant options

Revision ID: a3e8f1c57d20
Revises: c4f7a2e91d58
Create Date: 2026-11-11 12:00:00.000000

Cricket, Killer and Around the Clock: their own settings, and no mode or checkout.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a3e8f1c57d20'
down_revision: Union[str, Sequence[str], None] = 'c4f7a2e91d58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("games", sa.Column("options", sa.JSON(), nullable=True))
    op.alter_column("games", "mode", existing_type=sa.Integer(), nullable=True)
    op.alter_column("games", "checkout_mode", existing_type=sa.String(length=16), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM games WHERE mode IS NULL")
    op.alter_column("games", "checkout_mode", existing_type=sa.String(length=16), nullable=False)
    op.alter_column("games", "mode", existing_type=sa.Integer(), nullable=False)
    op.drop_column("games", "options")
