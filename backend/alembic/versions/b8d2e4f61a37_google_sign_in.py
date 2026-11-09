"""google sign in

Revision ID: b8d2e4f61a37
Revises: a3e7c1f95b20
Create Date: 2026-11-09 23:00:00.000000

Links an account to its Google identity; an account made through Google has no password.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b8d2e4f61a37'
down_revision: Union[str, Sequence[str], None] = 'a3e7c1f95b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("google_subject", sa.String(length=255), nullable=True))
    op.create_unique_constraint("users_google_subject_key", "users", ["google_subject"])
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.drop_constraint("users_google_subject_key", "users", type_="unique")
    op.drop_column("users", "google_subject")
