"""game claim token

Revision ID: a7c2e5f18d40
Revises: f3a9d2c6b814
Create Date: 2026-11-15 21:30:00.000000

Lets the device that set up an anonymous game hand it to an account later.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7c2e5f18d40'
down_revision: Union[str, Sequence[str], None] = 'f3a9d2c6b814'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("games", sa.Column("claim_token_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("games", "claim_token_hash")
