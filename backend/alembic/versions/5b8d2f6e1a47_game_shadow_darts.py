"""game shadow darts

Revision ID: 5b8d2f6e1a47
Revises: 9a6e2c4d7f31
Create Date: 2026-09-25 18:00:00.000000

Holds the darts the camera located after a win or bust closed the open visit
(docs/feature/done/korrektur.md §7).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5b8d2f6e1a47'
down_revision: Union[str, Sequence[str], None] = '9a6e2c4d7f31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "games",
        sa.Column("shadow_darts", sa.JSON(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("games", "shadow_darts")
