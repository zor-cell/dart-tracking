from datetime import datetime

from app.api.core.dto.base import CamelModel


class InviteLinkDto(CamelModel):
    """The secret the invitation link carries, and when it stops working."""

    token: str
    expires_at: datetime
