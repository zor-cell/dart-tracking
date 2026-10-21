"""An invitation to link an address-book entry to the account that opens it."""

from dataclasses import dataclass

from app.api.features.player.domain.reciprocal_link import ReciprocalLink


@dataclass(frozen=True)
class Invitation:
    player_id: str
    owner_user_id: str


@dataclass(frozen=True)
class InvitationPreview:
    """What the invitee is asked to agree to."""

    inviter_name: str
    player_name: str
    game_count: int
    reciprocal: ReciprocalLink
