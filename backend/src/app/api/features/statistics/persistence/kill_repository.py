"""Loads the Elimination and Killer games a player finished, for the kills in `domain/`."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.statistics.domain.kill_statistics import KillStatistics, game_kills
from app.api.features.statistics.persistence.played_games import PlayedGame, played_games

KILL_VARIANTS = (GameVariant.ELIMINATION, GameVariant.KILLER)


class KillRepository:
    async def overview(
        self,
        session: AsyncSession,
        user_id: str,
        criteria: GameFilter = GameFilter(),
        last: int | None = None,
        player: PlayerIdentity | None = None,
    ) -> KillStatistics:
        """The kills in the finished Elimination and Killer games `criteria` selects;
        `last` keeps the most recent, `player` reads that one instead of the account."""
        played = await played_games(session, user_id, criteria, last, player, KILL_VARIANTS)
        return await asyncio.to_thread(_tally, played)


def _tally(played: list[PlayedGame]) -> KillStatistics:
    statistics = KillStatistics()
    for game in played:
        statistics.games.append(game_kills(game.game, game.seat, game.played_at))
    return statistics


repository = KillRepository()
