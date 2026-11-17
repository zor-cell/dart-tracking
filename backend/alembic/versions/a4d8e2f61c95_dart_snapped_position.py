"""dart snapped position

Revision ID: a4d8e2f61c95
Revises: e5c9a1d4b730
Create Date: 2026-11-17 14:00:00.000000
"""
from itertools import groupby
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a4d8e2f61c95'
down_revision: Union[str, Sequence[str], None] = 'e5c9a1d4b730'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The event columns the evaluation reads, named so later columns cannot break the backfill.
_EVENTS = sa.text(
    "SELECT game_id, kind, turn_index, player_index, accepted, camera_armed, client_id,"
    " value, multiplier, pos_x, pos_y, dart_index, target_index, failure, metrics,"
    " tracker_version, created_at FROM game_events ORDER BY game_id, id"
)
# Only a dart that is still the corrected field and lost its tip takes the tip back.
_SNAP = sa.text(
    "UPDATE game_darts SET pos_x = :x, pos_y = :y, pos_snapped = true"
    " WHERE game_id = :game_id AND turn_index = :turn_index AND dart_index = :dart_index"
    " AND value = :value AND multiplier = :multiplier AND pos_x IS NULL"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "game_darts",
        sa.Column("pos_snapped", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _backfill(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("game_darts", "pos_snapped")


def _backfill(bind: sa.Connection) -> None:
    """Give the darts corrected before this revision the tip a correction keeps now."""
    from app.api.features.evaluation.domain.snapping import snapped_darts
    from app.api.features.evaluation.persistence.evaluation_repository import events_from_rows

    rows = bind.execute(_EVENTS).all()
    for game_id, of_game in groupby(rows, key=lambda row: row.game_id):
        for snapped in snapped_darts(game_id, events_from_rows(list(of_game))):
            x, y = snapped.dart.position or (None, None)
            bind.execute(
                _SNAP,
                {
                    "x": x,
                    "y": y,
                    "game_id": game_id,
                    "turn_index": snapped.turn_index,
                    "dart_index": snapped.dart_index,
                    "value": snapped.dart.value,
                    "multiplier": snapped.dart.multiplier,
                },
            )
