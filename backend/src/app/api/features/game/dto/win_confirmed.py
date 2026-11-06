from typing import Literal

from app.api.core.dto.base import CamelModel


class WinConfirmedDto(CamelModel):
    """Server -> room: the winning visit's darts were pulled, so every device takes the win."""

    type: Literal["win_confirmed"] = "win_confirmed"
