"""variant settings tables

Revision ID: d7b2e5a8c461
Revises: c4f8a2d6e913
Create Date: 2026-11-16 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd7b2e5a8c461'
down_revision: Union[str, Sequence[str], None] = 'c4f8a2d6e913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VARIANTS = ("x01", "elimination", "cricket", "killer", "around_the_clock", "training", "personal")


def upgrade() -> None:
    """Upgrade schema."""
    for variant in VARIANTS:
        _rename(f"game_{variant}", f"variant_{variant}")


def downgrade() -> None:
    """Downgrade schema."""
    for variant in VARIANTS:
        _rename(f"variant_{variant}", f"game_{variant}")


def _rename(old: str, new: str) -> None:
    """Rename the table and every constraint named after it, its primary key's index with it."""
    op.rename_table(old, new)
    names = op.get_bind().execute(
        sa.text("SELECT conname FROM pg_constraint WHERE conrelid = CAST(:table AS regclass)"),
        {"table": new},
    ).scalars().all()
    for name in names:
        if name.startswith(f"{old}_"):
            op.execute(f'ALTER TABLE {new} RENAME CONSTRAINT "{name}" TO "{new}{name[len(old):]}"')
