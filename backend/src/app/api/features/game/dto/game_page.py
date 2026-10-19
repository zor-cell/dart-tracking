from app.api.core.dto.base import CamelModel
from app.api.features.game.dto.game_summary import GameSummaryDto


class GamePageDto(CamelModel):
    items: list[GameSummaryDto]
    # Games matching the filter across all pages.
    total: int
