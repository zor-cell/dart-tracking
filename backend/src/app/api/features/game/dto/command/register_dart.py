from typing import Literal

from pydantic import Field

from app.api.features.game.domain.dart import Dart
from app.api.features.game.dto.command.game_command_base import GameCommandBase


class RegisterDartDto(GameCommandBase):
    """Client -> server: book one dart as the field it landed in, from any device in
    the room.
    """

    type: Literal["register_dart"]
    value: int = Field(ge=0, le=25)  # sector value, 25 for the bull, 0 for a miss
    multiplier: int = Field(ge=0, le=3)  # 0 miss, 1 single, 2 double, 3 triple

    def to_entity(self) -> Dart:
        return Dart(value=self.value, multiplier=self.multiplier)
