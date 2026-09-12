"""game variant

Revision ID: b17d4e9c05a2
Revises: e5c9a13b7402
Create Date: 2026-09-12 12:00:00.000000

A game now carries which direction its score runs. Every game that existed
before is x01, the only variant there was.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b17d4e9c05a2'
down_revision: Union[str, Sequence[str], None] = 'e5c9a13b7402'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Backfilled rather than given a server default: the default would outlive
    # the migration and silently decide the variant for every future insert.
    op.add_column("games", sa.Column("variant", sa.String(length=16), nullable=True))
    op.execute("UPDATE games SET variant = 'x01'")
    op.alter_column("games", "variant", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("games", "variant")
