from typing import Literal

from app.api.core.dto.base import CamelModel


class SetEndedDto(CamelModel):
    """Client -> server: end a game nobody wins, or go back into it from the
    finished screen. Game-wide, so every device in the room shows the same screen."""

    type: Literal["set_ended"]
    ended: bool
