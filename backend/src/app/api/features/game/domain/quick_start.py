"""The setup a new game offers to start in one tap: the one the account plays most."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.finish import FinishRules
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_options import GameOptions, default_options
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerOptions

# Days after which a played game weighs half, as for the filter suggestions.
HALF_LIFE_DAYS = 30


@dataclass(frozen=True)
class GameSetup:
    variant: GameVariant
    mode: GameMode | None
    checkout_mode: CheckoutMode | None
    options: GameOptions | None
    finish: FinishRules = FinishRules()

    @classmethod
    def of(
        cls,
        variant: GameVariant,
        mode: GameMode | None,
        checkout_mode: CheckoutMode | None,
        options: GameOptions | None,
        finish: FinishRules = FinishRules(),
    ) -> "GameSetup":
        """Killer's dealt numbers are left out: a new game deals them afresh. Games
        stored before their variant had settings count as its defaults."""
        options = options or default_options(variant, 0)
        if isinstance(options, KillerOptions):
            options = replace(options, numbers=())
        return cls(variant, mode, checkout_mode, options, finish if variant.races else FinishRules())


@dataclass(frozen=True)
class PlayedSetup:
    game_id: str
    played_at: datetime
    setup: GameSetup


@dataclass(frozen=True)
class QuickStartSeat:
    # The identity to seat, or None to seat a guest by `name`.
    player_id: str | None
    name: str


def favourite(played: Sequence[PlayedSetup], now: datetime) -> PlayedSetup | None:
    """The latest game of the setup with the most weight, each game fading to half
    every `HALF_LIFE_DAYS`; on a tie the more recently played setup."""
    weights: dict[GameSetup, float] = {}
    latest: dict[GameSetup, PlayedSetup] = {}
    for game in played:
        age = max((now - game.played_at).total_seconds(), 0) / 86_400
        weights[game.setup] = weights.get(game.setup, 0) + 0.5 ** (age / HALF_LIFE_DAYS)
        if game.setup not in latest or latest[game.setup].played_at < game.played_at:
            latest[game.setup] = game
    if not weights:
        return None
    best = max(weights, key=lambda setup: (weights[setup], latest[setup].played_at))
    return latest[best]
