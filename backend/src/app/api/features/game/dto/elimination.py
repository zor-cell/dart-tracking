from typing import Literal

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.elimination import EliminationKill
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_variant import GameVariant


class EliminationSettingsDto(CamelModel):
    variant: Literal[GameVariant.ELIMINATION] = GameVariant.ELIMINATION
    mode: GameMode
    checkout_mode: CheckoutMode = CheckoutMode.DOUBLE_OUT
    # Which darts send an opponent back to zero.
    kill: EliminationKill = EliminationKill.ANY
    catch_up: bool = False
    play_on: bool = False
