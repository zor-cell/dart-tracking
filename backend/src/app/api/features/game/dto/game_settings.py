"""The settings of a game on the wire: one schema per variant, told apart by `variant`."""

from dataclasses import replace
from random import randrange
from typing import Annotated

from pydantic import Field

from app.api.features.game.domain.around_the_clock import ClockOptions
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.cricket import CricketOptions
from app.api.features.game.domain.elimination import EliminationOptions
from app.api.features.game.domain.finish import FinishRules
from app.api.features.game.domain.game_setup import GameSetup
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerOptions, deal_numbers
from app.api.features.game.domain.personal_training import PersonalOptions
from app.api.features.game.domain.training import TrainingOptions
from app.api.features.game.dto.around_the_clock import ClockSettingsDto
from app.api.features.game.dto.cricket import CricketSettingsDto
from app.api.features.game.dto.elimination import EliminationSettingsDto
from app.api.features.game.dto.killer import KillerSettingsDto
from app.api.features.game.dto.personal_training import PersonalSettingsDto
from app.api.features.game.dto.training import TrainingSettingsDto
from app.api.features.game.dto.x01 import X01SettingsDto

type GameSettingsDto = Annotated[
    X01SettingsDto
    | EliminationSettingsDto
    | CricketSettingsDto
    | KillerSettingsDto
    | ClockSettingsDto
    | TrainingSettingsDto
    | PersonalSettingsDto,
    Field(discriminator="variant"),
]


def to_setup(
    settings: GameSettingsDto, players: int, plan: PersonalOptions | None = None
) -> GameSetup:
    """The domain settings of a new game: deals Killer's numbers, draws the training's
    seed, takes the personal training's `plan`."""
    match settings:
        case X01SettingsDto():
            finish = FinishRules(catch_up=settings.catch_up, play_on=settings.play_on)
            return GameSetup(GameVariant.X01, settings.mode, settings.checkout_mode, None, finish)
        case EliminationSettingsDto():
            return GameSetup(
                GameVariant.ELIMINATION,
                settings.mode,
                settings.checkout_mode,
                EliminationOptions(kill=settings.kill),
                FinishRules(catch_up=settings.catch_up, play_on=settings.play_on),
            )
        case CricketSettingsDto():
            options = CricketOptions(scoring=settings.scoring)
            return GameSetup(GameVariant.CRICKET, None, None, options)
        case KillerSettingsDto():
            return GameSetup(
                GameVariant.KILLER,
                None,
                None,
                KillerOptions(
                    numbers=deal_numbers(players), lives=settings.lives, zone=settings.zone
                ),
            )
        case ClockSettingsDto():
            return GameSetup(
                GameVariant.AROUND_THE_CLOCK,
                None,
                None,
                ClockOptions(zone=settings.zone, skip=settings.skip),
                FinishRules(catch_up=settings.catch_up, play_on=settings.play_on),
            )
        case TrainingSettingsDto():
            return GameSetup(
                GameVariant.TRAINING,
                None,
                None,
                TrainingOptions(
                    goal=settings.goal,
                    ring=settings.ring,
                    fields=tuple((field.value, field.multiplier) for field in settings.fields),
                    repeats=settings.repeats,
                    shuffle=settings.shuffle,
                    any_ring=settings.any_ring,
                    darts=settings.darts,
                    minutes=settings.minutes,
                    seed=randrange(2**31),
                ),
            )
        case PersonalSettingsDto():
            if plan is None:
                raise ValueError("a personal training needs its plan")
            # Without a single in the focus the switch changes nothing, so it stays on.
            any_ring = settings.any_ring or None not in settings.focus.rings
            personal = replace(plan, any_ring=any_ring, minutes=settings.minutes)
            return GameSetup(GameVariant.PERSONAL, None, None, personal)


def settings_dto(setup: GameSetup) -> GameSettingsDto:
    finish = {"catch_up": setup.finish.catch_up, "play_on": setup.finish.play_on}
    match setup.options:
        case EliminationOptions(kill=kill):
            return EliminationSettingsDto(**_points(setup), kill=kill, **finish)
        case CricketOptions(scoring=scoring):
            return CricketSettingsDto(scoring=scoring)
        case KillerOptions(lives=lives, zone=zone):
            return KillerSettingsDto(lives=lives, zone=zone)
        case ClockOptions(zone=zone, skip=skip):
            return ClockSettingsDto(zone=zone, skip=skip, **finish)
        case TrainingOptions() as training:
            return TrainingSettingsDto.of(training)
        case PersonalOptions() as personal:
            return PersonalSettingsDto.of(personal)
    return X01SettingsDto(**_points(setup), **finish)


def _points(setup: GameSetup) -> dict[str, int | CheckoutMode]:
    if setup.mode is None:
        raise ValueError(f"{setup.variant} needs a mode")
    return {"mode": setup.mode, "checkout_mode": setup.checkout_mode or CheckoutMode.DOUBLE_OUT}
