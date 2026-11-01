from typing import Literal

from app.api.core.dto.base import CamelModel


class SetTrackingPausedDto(CamelModel):
    """Client -> server: hold the camera's bookings, or resume them. Game-wide,
    so any device in the room can pause the camera that films the board."""

    type: Literal["set_tracking_paused"]
    paused: bool
