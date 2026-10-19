from typing import Literal

from app.api.features.game.dto.command.game_command_base import GameCommandBase


class NextPlayerDto(GameCommandBase):
    """Client -> server: end the visit and hand over to the next player."""

    type: Literal["next_player"]
