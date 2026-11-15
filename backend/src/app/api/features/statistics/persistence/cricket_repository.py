"""Loads the Cricket games a player finished, for the figures in `domain/`."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.statistics.domain.cricket_statistics import CricketStatistics
from app.api.features.statistics.persistence.played_games import PlayedGame, played_games


class CricketRepository:
    async def overview(
        self,
        session: AsyncSession,
        user_id: str,
        criteria: GameFilter = GameFilter(),
        last: int | None = None,
        player: PlayerIdentity | None = None,
    ) -> CricketStatistics:
        """The finished Cricket games `criteria` selects; `last` keeps the most recent,
        `player` reads that one instead of the account."""
        played = await played_games(
            session, user_id, criteria, last, player, (GameVariant.CRICKET,)
        )
        return await asyncio.to_thread(_tally, played)


def _tally(played: list[PlayedGame]) -> CricketStatistics:
    statistics = CricketStatistics()
    for game in played:
        statistics.add_game(game.game, game.seat, game.played_at)
    return statistics


repository = CricketRepository()
