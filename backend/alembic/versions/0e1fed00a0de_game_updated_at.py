"""game updated_at

Revision ID: 0e1fed00a0de
Revises: d883252c5886
Create Date: 2026-09-04 16:40:00.000000

Tells a game nobody came back to from one still being played, which is what
`abandoned` rests on. Existing rows start at their creation time — that is the
truth for a finished game and the safe assumption for an old open one.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0e1fed00a0de'
down_revision: Union[str, Sequence[str], None] = 'd883252c5886'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "games",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute("UPDATE games SET updated_at = COALESCE(finished_at, created_at)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("games", "updated_at")
