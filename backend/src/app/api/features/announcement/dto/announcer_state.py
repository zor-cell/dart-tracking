from typing import Literal

from app.api.core.dto.base import CamelModel


class AnnouncerStateDto(CamelModel):
    """Server -> room: which device currently speaks the booked darts, if any."""

    type: Literal["announcer_state"] = "announcer_state"
    client_id: str | None
