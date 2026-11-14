"""Loads the Elimination and Killer games a player finished, for the kills in `domain/`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.game.domain.game_filter import GameFilter
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.player.domain.player_identity import PlayerIdentity
from app.api.features.statistics.domain.kill_statistics import KillStatistics, game_kills
from app.api.features.statistics.persistence.played_games import played_games

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
        statistics = KillStatistics()
        for played in await played_games(session, user_id, criteria, last, player, KILL_VARIANTS):
            statistics.games.append(game_kills(played.game, played.seat, played.played_at))
        return statistics


repository = KillRepository()
