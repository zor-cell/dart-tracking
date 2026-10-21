from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.player.domain.invitation import InvitationPreview
from app.api.features.player.domain.reciprocal_link import ReciprocalLink


class InvitationDto(CamelModel):
    inviter_name: str
    player_name: str
    game_count: int
    reciprocal: ReciprocalLink

    @classmethod
    def from_entity(cls, preview: InvitationPreview) -> Self:
        return cls(
            inviter_name=preview.inviter_name,
            player_name=preview.player_name,
            game_count=preview.game_count,
            reciprocal=preview.reciprocal,
        )
