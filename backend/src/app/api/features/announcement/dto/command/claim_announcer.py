from typing import Literal

from app.api.core.dto.base import CamelModel


class ClaimAnnouncerDto(CamelModel):
    """Client -> server: let this device speak the booked darts from now on."""

    type: Literal["claim_announcer"]
