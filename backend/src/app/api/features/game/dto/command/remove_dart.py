from typing import Literal

from pydantic import Field

from app.api.features.game.dto.command.game_command_base import GameCommandBase


class RemoveDartDto(GameCommandBase):
    """Client -> server: take one dart out of the open visit, by its position in it."""

    type: Literal["remove_dart"]
    index: int = Field(ge=0)
