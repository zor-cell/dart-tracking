from typing import Literal

from app.api.features.game.dto.command.game_command_base import GameCommandBase


class UndoDto(GameCommandBase):
    """Client -> server: step back one action — a dart, or the switch to the
    current player."""

    type: Literal["undo"]
