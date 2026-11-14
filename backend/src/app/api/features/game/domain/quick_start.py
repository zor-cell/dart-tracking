"""The setup a new game offers to start in one tap: the one the account plays most."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.api.features.game.domain.game_setup import GameSetup

# Days after which a played game weighs half, as for the filter suggestions.
HALF_LIFE_DAYS = 30


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
