"""Loads every finished game a player sat in, for the overall figures in `domain/`."""

import asyncio
from datetime import UTC, date, datetime, timedelta, tzinfo

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
        zone: tzinfo = UTC,
    ) -> OverallStatistics:
        """The finished games of any kind `criteria` selects, added up, their days in `zone`."""
        played = await played_games(session, user_id, criteria, last, player)
        first = None if criteria.since is None else criteria.since.astimezone(zone).date()
        if criteria.until is not None:
            end = criteria.until.astimezone(zone).date() - timedelta(days=1)
        else:
            end = None if first is None else datetime.now(zone).date()
        return await asyncio.to_thread(_tally, played, zone, first, end)


def _tally(
    played: list[PlayedGame], zone: tzinfo, first: date | None, last: date | None
) -> OverallStatistics:
    statistics = OverallStatistics(zone=zone, first_day=first, last_day=last)
    for game in played:
        statistics.add_game(game.game, game.seat, game.played_at, game.finished_at)
    return statistics


repository = OverallRepository()
