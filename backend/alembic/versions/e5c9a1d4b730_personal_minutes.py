"""personal minutes

Revision ID: e5c9a1d4b730
Revises: d7b2e5a8c461
Create Date: 2026-11-16 21:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5c9a1d4b730'
down_revision: Union[str, Sequence[str], None] = 'd7b2e5a8c461'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("variant_personal", sa.Column("minutes", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("variant_personal", "minutes")
