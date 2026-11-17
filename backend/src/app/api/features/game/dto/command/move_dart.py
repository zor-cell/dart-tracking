from typing import Literal

from pydantic import Field

from app.api.features.game.dto.command.dart_correction import DartCorrectionBase


class MoveDartDto(DartCorrectionBase):
    """Client -> server: move one dart of a visit to another place in it — a throw
    the camera missed lands last when entered by hand."""

    type: Literal["move_dart"]
    index: int = Field(ge=0)
    to_index: int = Field(ge=0)
