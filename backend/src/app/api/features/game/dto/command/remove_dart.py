from typing import Literal

from pydantic import Field

from app.api.features.game.dto.command.dart_correction import DartCorrectionBase


class RemoveDartDto(DartCorrectionBase):
    """Client -> server: take one dart out of a visit, by its position in it."""

    type: Literal["remove_dart"]
    index: int = Field(ge=0)
