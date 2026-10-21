from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.player.domain.player_link import PlayerLink


class PlayerLinkDto(CamelModel):
    player_id: str
    player_name: str
    owner_name: str
    retired: bool

    @classmethod
    def from_entity(cls, link: PlayerLink) -> Self:
        return cls(
            player_id=link.player_id,
            player_name=link.player_name,
            owner_name=link.owner_name,
            retired=link.retired,
        )
