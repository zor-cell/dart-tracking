from typing import Literal

from pydantic import Field

from app.api.core.dto.base import CamelModel
from app.api.features.game.entity.dart import Dart


class RegisterDartMessage(CamelModel):
    """Client -> server: book one dart, as the field it landed in rather than as
    points — T20 and three single 20s score the same but are not the same throw,
    and the scoreboard shows which one it was.

    Sent by any device in the game's room: the camera phone when the user
    corrects a misread, a scoreboard phone entering the visit by hand.
    """

    type: Literal["register_dart"]
    value: int = Field(ge=0, le=25)  # sector value, 25 for the bull, 0 for a miss
    multiplier: int = Field(ge=0, le=3)  # 0 miss, 1 single, 2 double, 3 triple

    def to_entity(self) -> Dart:
        return Dart(value=self.value, multiplier=self.multiplier)
