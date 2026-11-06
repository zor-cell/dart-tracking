from typing import Literal

from app.api.core.dto.base import CamelModel


class SetWinConfirmedDto(CamelModel):
    """Client -> server: take the win, or go back to it from the finished screen.
    Game-wide, so every device in the room shows the same screen."""

    type: Literal["set_win_confirmed"]
    confirmed: bool
