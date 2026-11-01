"""turn and dart times

Revision ID: b3e8f2a6d1c4
Revises: a7c3e5f1b920
Create Date: 2026-11-01 21:00:00.000000

When each dart was booked and each visit closed, filled in from the event log for
the games that have one.
"""
from collections import defaultdict
from itertools import groupby
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3e8f2a6d1c4'
down_revision: Union[str, Sequence[str], None] = 'a7c3e5f1b920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Events that put a dart into the open visit.
_BOOKINGS = {"detected", "manual", "miss_filled"}


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("game_turns", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("game_darts", sa.Column("thrown_at", sa.DateTime(timezone=True), nullable=True))
    _backfill(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("game_darts", "thrown_at")
    op.drop_column("game_turns", "ended_at")


def _backfill(connection: sa.Connection) -> None:
    """Replays each game's event log the way `visit_replay` does, keeping only the times."""
    events = connection.execute(
        sa.text(
            "SELECT game_id, kind, accepted, dart_index, target_index, created_at"
            " FROM game_events WHERE kind <> 'calibrated' ORDER BY game_id, id"
        )
    ).all()
    finished = dict(
        connection.execute(
            sa.text("SELECT id, finished_at FROM games WHERE finished_at IS NOT NULL")
        ).all()
    )

    darts: list[dict[str, object]] = []
    turns: list[dict[str, object]] = []
    for game_id, rows in groupby(events, key=lambda row: row.game_id):
        thrown, ended = _replay(rows)
        darts += [
            {"game": game_id, "turn": turn, "dart": index, "at": at}
            for turn, times in thrown.items()
            for index, at in enumerate(times)
        ]
        if game_id in finished and thrown:
            ended.setdefault(max(thrown), finished[game_id])
        turns += [{"game": game_id, "turn": turn, "at": at} for turn, at in ended.items()]

    if darts:
        connection.execute(
            sa.text(
                "UPDATE game_darts SET thrown_at = :at"
                " WHERE game_id = :game AND turn_index = :turn AND dart_index = :dart"
            ),
            darts,
        )
    if turns:
        connection.execute(
            sa.text(
                "UPDATE game_turns SET ended_at = :at WHERE game_id = :game AND turn_index = :turn"
            ),
            turns,
        )


def _replay(rows) -> tuple[dict[int, list], dict[int, object]]:
    """Booking times per visit slot, and when each slot was handed over."""
    thrown: dict[int, list] = defaultdict(list)
    ended: dict[int, object] = {}
    open_index = 0
    for row in rows:
        if row.kind == "shadow_booked" or (row.kind in _BOOKINGS and row.accepted):
            thrown[open_index].append(row.created_at)
        elif not row.accepted:
            continue
        elif row.kind == "undo":
            while not thrown[open_index] and open_index > 0:
                open_index -= 1
                ended.pop(open_index, None)
            if thrown[open_index]:
                thrown[open_index].pop()
        elif row.kind == "visit_reopened":
            open_index = max(open_index - 1, 0)
            ended.pop(open_index, None)
        elif row.kind == "dart_removed":
            if row.dart_index is not None and row.dart_index < len(thrown[open_index]):
                thrown[open_index].pop(row.dart_index)
        elif row.kind == "dart_moved":
            times = thrown[open_index]
            index, to_index = row.dart_index, row.target_index
            if index is not None and to_index is not None and max(index, to_index) < len(times):
                times.insert(to_index, times.pop(index))
        elif row.kind == "next_player":
            ended[open_index] = row.created_at
            open_index += 1
    return {turn: times for turn, times in thrown.items() if times}, ended
