from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.player.domain.player_identity import PlayerIdentity


class PlayerIdentityDto(CamelModel):
    id: str
    name: str
    is_self: bool

    @classmethod
    def from_entity(cls, identity: PlayerIdentity, viewer_id: str) -> Self:
        """`is_self` is a property of the pairing, not of the identity: the same
        row is "me" to its owner and an ordinary contact to nobody else."""
        return cls(
            id=identity.id,
            name=identity.display_name,
            is_self=identity.user_id == viewer_id,
        )
