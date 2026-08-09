from typing import Literal

from app.api.core.dto.base import CamelModel


class UndoDto(CamelModel):
    """Client -> server: step back one action — a dart, or the switch to the
    current player."""

    type: Literal["undo"]
