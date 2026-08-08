from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_mode import GameMode


class GameConfigDto(CamelModel):
    mode: GameMode
    player_names: list[str]
    checkout_mode: CheckoutMode = CheckoutMode.DOUBLE_OUT
