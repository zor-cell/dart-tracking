from datetime import datetime
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.kill_statistics import GameKills, KillStatistics


class GameKillsDto(CamelModel):
    game_id: str
    played_at: datetime
    kills: int
    losses: int
    won: bool
    darts: int

    @classmethod
    def from_entity(cls, game: GameKills) -> Self:
        return cls(
            game_id=game.game_id,
            played_at=game.played_at,
            kills=game.kills,
            losses=game.losses,
            won=game.won,
            darts=game.darts,
        )


class KillStatisticsDto(CamelModel):
    """Kills over the selected games: resets in Elimination, lives taken in Killer."""

    kills: int
    losses: int
    wins: int
    darts: int
    # Oldest first.
    games: list[GameKillsDto]
    most: GameKillsDto | None

    @classmethod
    def from_entity(cls, statistics: KillStatistics) -> Self:
        most = statistics.most
        return cls(
            kills=statistics.kills,
            losses=statistics.losses,
            wins=statistics.wins,
            darts=statistics.darts,
            games=[GameKillsDto.from_entity(game) for game in statistics.games],
            most=None if most is None else GameKillsDto.from_entity(most),
        )
