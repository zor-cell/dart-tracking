"""A counted game on its own, for how the figures move over time."""

from dataclasses import dataclass
from datetime import datetime

from app.api.features.statistics.domain.player_statistics import PlayerStatistics


@dataclass(frozen=True)
class TrendPoint:
    game_id: str
    played_at: datetime
    statistics: PlayerStatistics
