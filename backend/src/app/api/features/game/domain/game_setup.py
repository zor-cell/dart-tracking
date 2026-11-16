"""A game's settings as one value: the variant with everything that was chosen for it."""

from dataclasses import dataclass, replace

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.finish import FinishRules
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_options import GameOptions, default_options
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerOptions
from app.api.features.game.domain.personal_training import PersonalOptions
from app.api.features.game.domain.training import TrainingOptions


@dataclass(frozen=True)
class GameSetup:
    variant: GameVariant
    # The starting score and finish of the points variants; None for the others.
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
        """The setup as a new game would take it: without Killer's dealt numbers and
        the training's seed and the personal plan, which every game draws afresh."""
        options = options or default_options(variant, 0)
        if isinstance(options, KillerOptions):
            options = replace(options, numbers=())
        if isinstance(options, TrainingOptions):
            options = replace(options, seed=0)
        if isinstance(options, PersonalOptions):
            options = replace(options, blocks=(), baselines=())
        return cls(variant, mode, checkout_mode, options, finish if variant.races else FinishRules())
