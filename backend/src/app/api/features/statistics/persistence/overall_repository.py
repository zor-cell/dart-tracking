"""Loads every finished game a player sat in, for the overall figures in `domain/`."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.statistics.domain.overall_statistics import OverallStatistics
from app.api.features.statistics.persistence.played_games import PlayedGame, played_games


class OverallRepository:
    async def overview(
        self,
        session: AsyncSession,
        user_id: str,
        criteria: GameFilter = GameFilter(),
        last: int | None = None,
        player: PlayerIdentity | None = None,
    ) -> OverallStatistics:
        """The finished games of any kind `criteria` selects, added up."""
        played = await played_games(session, user_id, criteria, last, player)
        return await asyncio.to_thread(_tally, played)


def _tally(played: list[PlayedGame]) -> OverallStatistics:
    statistics = OverallStatistics()
    for game in played:
        statistics.add_game(game.game, game.seat, game.played_at, game.finished_at)
    return statistics


repository = OverallRepository()
