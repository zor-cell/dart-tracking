"""user settings

Revision ID: b8e3d1470f52
Revises: a41c7b902e18
Create Date: 2026-09-07 10:00:00.000000

Moves the app's switches off the browser and onto the account, so they follow
the user across devices. An account without a row runs on the defaults, which
is also what an anonymous session gets.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b8e3d1470f52'
down_revision: Union[str, Sequence[str], None] = 'a41c7b902e18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("manual_entry_enabled", sa.Boolean(), nullable=False),
        sa.Column("confirm_throw_enabled", sa.Boolean(), nullable=False),
        sa.Column("evaluation_enabled", sa.Boolean(), nullable=False),
        sa.Column("debug_calibration", sa.Boolean(), nullable=False),
        sa.Column("debug_detection", sa.Boolean(), nullable=False),
        sa.Column("debug_client_detection", sa.Boolean(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_settings")
