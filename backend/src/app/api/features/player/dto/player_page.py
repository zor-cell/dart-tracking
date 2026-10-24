from app.api.core.dto.base import CamelModel
from app.api.features.player.dto.player_identity import PlayerIdentityDto


class PlayerPageDto(CamelModel):
    items: list[PlayerIdentityDto]
    # Entries across all pages.
    total: int
