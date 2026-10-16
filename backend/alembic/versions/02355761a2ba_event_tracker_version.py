"""event tracker version

Revision ID: 02355761a2ba
Revises: 5b8d2f6e1a47
Create Date: 2026-10-16 12:00:00.000000

Moves the tracker version from the game onto each event, as a pipeline version.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '02355761a2ba'
down_revision: Union[str, Sequence[str], None] = '5b8d2f6e1a47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Build number a game recorded -> tracker version of the commit that build deployed.
BUILD_VERSIONS = {
    138: 33,
    139: 33,
    140: 33,
    141: 33,
    142: 33,
    144: 33,
    145: 33,
    146: 34,
    147: 34,
    148: 35,
    149: 35,
    150: 36,
    152: 36,
    153: 37,
    154: 38,
    156: 39,
    160: 40,
    161: 40,
    163: 40,
    164: 40,
    165: 40,
    167: 40,
    169: 41,
    170: 41,
    172: 41,
    179: 41,
    184: 41,
    187: 41,
    1001: 41,
    1002: 41,
    1003: 41,
    1004: 42,
}


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("game_events", sa.Column("tracker_version", sa.Integer(), nullable=True))

    connection = op.get_bind()
    recorded = connection.execute(
        sa.text("SELECT DISTINCT tracker_version FROM games WHERE tracker_version IS NOT NULL")
    ).scalars()
    unmapped = sorted(set(recorded) - BUILD_VERSIONS.keys())
    if unmapped:
        raise RuntimeError(f"builds without a tracker version in BUILD_VERSIONS: {unmapped}")

    for build, version in BUILD_VERSIONS.items():
        connection.execute(
            sa.text(
                "UPDATE game_events SET tracker_version = :version FROM games"
                " WHERE game_events.game_id = games.id AND games.tracker_version = :build"
            ),
            {"version": version, "build": build},
        )

    op.drop_column("games", "tracker_version")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("games", sa.Column("tracker_version", sa.Integer(), nullable=True))
    op.drop_column("game_events", "tracker_version")
