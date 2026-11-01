"""What the games table knows about a game beyond its score."""

from dataclasses import dataclass
from datetime import datetime

from app.api.features.game.domain.game_status import GameStatus


@dataclass(frozen=True)
class GameRecord:
    status: GameStatus
    created_at: datetime
    finished_at: datetime | None
