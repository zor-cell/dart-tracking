"""Which games a history list holds. Every field narrows it to any of its values; an
empty one leaves it open, except `statuses`."""

from dataclasses import dataclass
from datetime import datetime

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.player_count import PlayerCount


@dataclass(frozen=True)
class GameFilter:
    # Part of a seated player's name, ignoring case.
    query: str | None = None
    variants: tuple[GameVariant, ...] = ()
    modes: tuple[GameMode, ...] = ()
    checkout_modes: tuple[CheckoutMode, ...] = ()
    # Empty hides discarded games and abandoned ones too short to count.
    statuses: tuple[GameStatus, ...] = ()
    # Player identities of which one has to hold a seat in the game.
    opponent_ids: tuple[str, ...] = ()
    player_counts: tuple[PlayerCount, ...] = ()
    # Bounds on the start of the game; `until` is exclusive.
    since: datetime | None = None
    until: datetime | None = None
    # Points one of the account's own visits reached, busts aside; only the history reads it.
    min_visit: int | None = None
