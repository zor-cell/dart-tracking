"""Which games a history list holds. Every field narrows it; None leaves it open,
except `status`."""

from dataclasses import dataclass
from datetime import datetime

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.game_variant import GameVariant


@dataclass(frozen=True)
class GameFilter:
    # Part of a seated player's name, ignoring case.
    query: str | None = None
    variant: GameVariant | None = None
    mode: GameMode | None = None
    checkout_mode: CheckoutMode | None = None
    # None hides discarded games and abandoned ones too short to count.
    status: GameStatus | None = None
    # A player identity that has to hold a seat in the game.
    opponent_id: str | None = None
    # Bounds on the number of seats, both inclusive.
    min_players: int | None = None
    max_players: int | None = None
    # Bounds on the start of the game; `until` is exclusive.
    since: datetime | None = None
    until: datetime | None = None
