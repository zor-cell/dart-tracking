"""dart targets

Revision ID: f3a9d2c6b814
Revises: e1b7c4a92f35
Create Date: 2026-11-15 00:30:00.000000

Stores the field each dart was thrown at, replayed from the stored games.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision: str = 'f3a9d2c6b814'
down_revision: Union[str, Sequence[str], None] = 'e1b7c4a92f35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SETTINGS_TABLES = (
    "game_x01", "game_elimination", "game_cricket", "game_killer",
    "game_around_the_clock", "game_training",
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("game_darts", sa.Column("target_value", sa.SmallInteger(), nullable=True))
    op.add_column("game_darts", sa.Column("target_multiplier", sa.SmallInteger(), nullable=True))

    session = Session(bind=op.get_bind())
    if session.execute(sa.text("SELECT 1 FROM game_darts LIMIT 1")).first() is not None:
        _backfill(session)


def _backfill(session: Session) -> None:
    """Replay every stored game with the rules of the app and write its targets."""
    from app.api.features.game.domain.dart import Dart
    from app.api.features.game.domain.game import Game
    from app.api.features.game.domain.player import Player
    from app.api.features.game.domain.turn import Turn
    from app.api.features.game.persistence.game_settings import SETTINGS_TABLES, setup_of

    setups = {}
    existing = set(sa.inspect(session.connection()).get_table_names())
    for table in SETTINGS_TABLES.values():
        if table.__tablename__ not in existing:
            continue
        columns = [column.name for column in table.__table__.columns]
        rows = session.execute(sa.text(f"SELECT {', '.join(columns)} FROM {table.__tablename__}"))
        for row in rows.mappings():
            setups[str(row["game_id"])] = setup_of(table(**row))

    for game_id, setup in setups.items():
        seats = session.execute(
            sa.text("SELECT player_index FROM game_players WHERE game_id = :id ORDER BY player_index"),
            {"id": game_id},
        ).scalars().all()
        turns = session.execute(
            sa.text(
                "SELECT turn_index, player_index, busted FROM game_turns "
                "WHERE game_id = :id ORDER BY turn_index"
            ),
            {"id": game_id},
        ).all()
        darts: dict[int, list[Dart]] = {}
        for dart in session.execute(
            sa.text(
                "SELECT turn_index, value, multiplier FROM game_darts "
                "WHERE game_id = :id ORDER BY turn_index, dart_index"
            ),
            {"id": game_id},
        ):
            darts.setdefault(dart.turn_index, []).append(Dart(dart.value, dart.multiplier))
        if not darts:
            continue

        game = Game(
            id=game_id,
            mode=setup.mode,
            players=[Player(id=seat, name="", identity_id="") for seat in seats],
            variant=setup.variant,
            checkout_mode=setup.checkout_mode,
            options=setup.options,
            finish=setup.finish,
            turns=[
                Turn(player_id=turn.player_index, darts=darts.get(turn.turn_index, []), busted=turn.busted)
                for turn in turns
            ],
        )
        updates = [
            {
                "id": game_id,
                "turn": turn.turn_index,
                "dart": dart_index,
                "value": target.value,
                "multiplier": target.multiplier,
            }
            for turn, aimed in zip(turns, game.targets(), strict=True)
            for dart_index, target in enumerate(aimed)
            if target is not None
        ]
        if updates:
            session.execute(
                sa.text(
                    "UPDATE game_darts SET target_value = :value, target_multiplier = :multiplier "
                    "WHERE game_id = :id AND turn_index = :turn AND dart_index = :dart"
                ),
                updates,
            )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("game_darts", "target_multiplier")
    op.drop_column("game_darts", "target_value")
