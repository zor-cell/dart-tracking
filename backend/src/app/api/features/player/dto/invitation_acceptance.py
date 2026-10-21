from app.api.core.dto.base import CamelModel


class InvitationAcceptanceDto(CamelModel):
    """Whether the inviter also gets linked in the invitee's own address book."""

    reciprocal: bool = False
