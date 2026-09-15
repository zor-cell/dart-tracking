from typing import Annotated

from pydantic import Field

from app.api.features.game.dto.command.next_player import NextPlayerDto
from app.api.features.game.dto.command.register_dart import RegisterDartDto
from app.api.features.game.dto.command.remove_dart import RemoveDartDto
from app.api.features.game.dto.command.undo import UndoDto

GameCommand = Annotated[
    RegisterDartDto
    | UndoDto
    | RemoveDartDto
    | NextPlayerDto,
    Field(discriminator="type"),
]