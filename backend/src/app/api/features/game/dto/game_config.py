from app.api.core.dto.base import CamelModel
from app.api.features.game.dto.game_settings import GameSettingsDto
from app.api.features.game.dto.player_slot import PlayerSlotDto


class GameConfigDto(CamelModel):
    players: list[PlayerSlotDto]
    settings: GameSettingsDto
    evaluation_enabled: bool = False
    rematch_of: str | None = None
