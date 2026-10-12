"""user role

Revision ID: f4a1c7d2e903
Revises: c2a4f8b31d90
Create Date: 2026-09-08 10:00:00.000000

Adds the role that gates the evaluation page. Existing accounts become plain
users; the address below is seeded as the admin, since the page is only useful
to whoever runs the test games.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f4a1c7d2e903'
down_revision: Union[str, Sequence[str], None] = 'c2a4f8b31d90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ADMIN_EMAIL = "philippemanu.zorman@gmail.com"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "role", sa.String(length=16), server_default="user", nullable=False
        ),
    )
    op.execute(
        sa.text("UPDATE users SET role = 'admin' WHERE email = :email").bindparams(
            email=ADMIN_EMAIL
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "role")
