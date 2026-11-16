"""The settings of a variant beyond x01's mode and checkout, one class per variant."""

from app.api.features.game.domain.around_the_clock import ClockOptions, ClockProgress
from app.api.features.game.domain.cricket import CricketOptions, CricketProgress
from app.api.features.game.domain.elimination import EliminationOptions
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KILLER_NUMBERS, KillerOptions, KillerProgress
from app.api.features.game.domain.personal_training import PersonalOptions, PersonalProgress
from app.api.features.game.domain.training import TrainingOptions, TrainingProgress

type GameOptions = (
    CricketOptions
    | KillerOptions
    | ClockOptions
    | EliminationOptions
    | TrainingOptions
    | PersonalOptions
)
type GameProgress = (
    CricketProgress | KillerProgress | ClockProgress | TrainingProgress | PersonalProgress
)


def default_options(variant: GameVariant, players: int) -> GameOptions | None:
    """The settings a variant starts with; Killer deals the numbers by seat."""
    match variant:
        case GameVariant.CRICKET:
            return CricketOptions()
        case GameVariant.KILLER:
            return KillerOptions(numbers=KILLER_NUMBERS[:players])
        case GameVariant.AROUND_THE_CLOCK:
            return ClockOptions()
        case GameVariant.ELIMINATION:
            return EliminationOptions()
        case GameVariant.TRAINING:
            return TrainingOptions()
        case GameVariant.PERSONAL:
            return PersonalOptions()
    return None
