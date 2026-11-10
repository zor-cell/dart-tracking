"""announcer voice

Revision ID: c4f7a2e91d58
Revises: b8d2e4f61a37
Create Date: 2026-11-10 19:30:00.000000

The language and voice an account's announcer speaks in.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4f7a2e91d58'
down_revision: Union[str, Sequence[str], None] = 'b8d2e4f61a37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("user_settings", sa.Column("announcer_language", sa.String(length=8), nullable=True))
    op.add_column(
        "user_settings",
        sa.Column("announcer_voice", sa.String(length=16), server_default="first", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_settings", "announcer_voice")
    op.drop_column("user_settings", "announcer_language")
