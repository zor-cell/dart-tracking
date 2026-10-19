"""A game as it appears in a list, without its turns. Aggregated in the query,
because a list of a hundred games must not load a hundred aggregates; only
elimination games are replayed, in one batch."""

from dataclasses import dataclass
from datetime import datetime

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import GameStatus, counts_in_statistics


@dataclass(frozen=True)
class GameSummaryPlayer:
    name: str
    remaining: int
    is_me: bool


@dataclass(frozen=True)
class GameSummary:
    id: str
    mode: GameMode
    checkout_mode: CheckoutMode
    # Already derived (`effective_status`), so `abandoned` can appear here even
    # though no row ever holds it.
    status: GameStatus
    players: list[GameSummaryPlayer]
    winner_index: int | None
    dart_count: int
    own_darts: int
    created_at: datetime

    @property
    def counted(self) -> bool:
        return counts_in_statistics(self.status, self.own_darts)
