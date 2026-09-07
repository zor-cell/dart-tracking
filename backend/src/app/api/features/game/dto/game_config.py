from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.dto.player_slot import PlayerSlotDto


class GameConfigDto(CamelModel):
    mode: GameMode
    players: list[PlayerSlotDto]
    checkout_mode: CheckoutMode = CheckoutMode.DOUBLE_OUT
    evaluation_enabled: bool = False
