"""The finished games a player sat in, loaded whole for the figures that replay them."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.persistence.game import GameTable
from app.api.features.game.persistence.game_player import GamePlayerTable
from app.api.features.game.persistence.game_repository import game_filter_clauses, hidden_by
from app.api.features.game.persistence.game_repository import repository as games
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.player.persistence.player import PlayerTable
from app.api.features.statistics.persistence.statistics_repository import (
    latest_games,
    seat_clauses,
)


@dataclass(frozen=True)
class PlayedGame:
    game: Game
    seat: int
    played_at: datetime
    finished_at: datetime | None


async def played_games(
    session: AsyncSession,
    user_id: str,
    criteria: GameFilter,
    last: int | None,
    player: PlayerIdentity | None,
    variants: Sequence[GameVariant] = (),
) -> list[PlayedGame]:
    """The finished games `criteria` selects, oldest first; `last` keeps the most recent,
    `player` reads that one's seats instead of the account's."""
    narrowed = [GameTable.variant.in_([variant.value for variant in variants])] if variants else []
    played = [
        *seat_clauses(user_id, player),
        *narrowed,
        GameTable.id.not_in(hidden_by(user_id)),
        GameTable.status == GameStatus.FINISHED.value,
        *game_filter_clauses(criteria),
    ]
    rows = (
        await session.execute(
            select(
                GameTable.id,
                GameTable.created_at,
                GameTable.finished_at,
                GamePlayerTable.player_index,
            )
            .join(GamePlayerTable, GamePlayerTable.game_id == GameTable.id)
            .join(PlayerTable, PlayerTable.id == GamePlayerTable.player_id)
            .where(*played, *latest_games(played, last))
            .order_by(GameTable.created_at.desc(), GameTable.id)
        )
    ).all()
    loaded = await games.many(session, [row.id for row in rows])
    return [
        PlayedGame(loaded[row.id], row.player_index, row.created_at, row.finished_at)
        for row in reversed(rows)
        if row.id in loaded
    ]
