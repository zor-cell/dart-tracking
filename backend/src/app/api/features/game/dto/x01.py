from typing import Literal

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_variant import GameVariant


class X01SettingsDto(CamelModel):
    variant: Literal[GameVariant.X01] = GameVariant.X01
    mode: GameMode
    checkout_mode: CheckoutMode = CheckoutMode.DOUBLE_OUT
    # How the race ends once someone has finished.
    catch_up: bool = False
    play_on: bool = False
