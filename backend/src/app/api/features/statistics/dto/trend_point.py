from datetime import datetime
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.trend import TrendPoint


class TrendPointDto(CamelModel):
    """One game's figures; the rates stay pairs, so a chart can weigh them."""

    game_id: str
    played_at: datetime
    darts: int
    average: float
    first_nine_average: float
    checkout_hits: int
    checkout_attempts: int
    legs_won: int
    won_leg_darts: int

    @classmethod
    def from_entity(cls, point: TrendPoint) -> Self:
        statistics = point.statistics
        return cls(
            game_id=point.game_id,
            played_at=point.played_at,
            darts=statistics.darts,
            average=round(statistics.average, 2),
            first_nine_average=round(statistics.first_nine_average, 2),
            checkout_hits=statistics.checkout_hits,
            checkout_attempts=statistics.checkout_attempts,
            legs_won=statistics.legs_won,
            won_leg_darts=statistics.won_leg_darts,
        )
