"""The settings of a variant beyond x01's mode and checkout, one class per variant."""

from app.api.features.game.domain.around_the_clock import ClockOptions, ClockProgress
from app.api.features.game.domain.cricket import CricketOptions, CricketProgress
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KILLER_NUMBERS, KillerOptions, KillerProgress

type GameOptions = CricketOptions | KillerOptions | ClockOptions
type GameProgress = CricketProgress | KillerProgress | ClockProgress


def default_options(variant: GameVariant, players: int) -> GameOptions | None:
    """The settings a variant starts with; Killer deals the numbers by seat."""
    match variant:
        case GameVariant.CRICKET:
            return CricketOptions()
        case GameVariant.KILLER:
            return KillerOptions(numbers=KILLER_NUMBERS[:players])
        case GameVariant.AROUND_THE_CLOCK:
            return ClockOptions()
    return None
