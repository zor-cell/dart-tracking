from datetime import datetime
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_record import GameRecord
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.dto.game_state import GameStateDto
from app.api.features.game.dto.visit import VisitDto
from app.api.features.statistics.domain.player_statistics import PlayerStatistics
from app.api.features.statistics.dto.player_statistics import PlayerStatisticsDto


class GameDetailDto(CamelModel):
    game: GameStateDto
    status: GameStatus
    created_at: datetime
    finished_at: datetime | None
    # One per player, in seat order.
    statistics: list[PlayerStatisticsDto]
    visits: list[VisitDto]

    @classmethod
    def from_entity(
        cls, game: Game, record: GameRecord, statistics: list[PlayerStatistics]
    ) -> Self:
        visits = [
            VisitDto.from_entity(turn, standings)
            for turn, standings in zip(game.turns, game.standings_after_turns(), strict=True)
            if turn.darts
        ]
        return cls(
            game=GameStateDto.from_entity(game),
            status=record.status,
            created_at=record.created_at,
            finished_at=record.finished_at,
            statistics=[PlayerStatisticsDto.from_entity(entry) for entry in statistics],
            visits=visits,
        )
