"""A game as it appears in a list, without its turns. Aggregated in the query,
because a list of a hundred games must not load a hundred aggregates; only
games beyond plain x01 are replayed, in one batch."""

from dataclasses import dataclass
from datetime import datetime

from app.api.features.game.domain.game_setup import GameSetup
from app.api.features.game.domain.game_status import GameStatus, counts_in_statistics


@dataclass(frozen=True)
class GameSummaryPlayer:
    name: str
    # None outside the points variants.
    remaining: int | None
    is_me: bool


@dataclass(frozen=True)
class GameSummary:
    id: str
    setup: GameSetup
    # Already derived (`effective_status`), so `abandoned` can appear here even
    # though no row ever holds it.
    status: GameStatus
    players: list[GameSummaryPlayer]
    winner_index: int | None
    dart_count: int
    created_at: datetime

    @property
    def counted(self) -> bool:
        return counts_in_statistics(self.status)
