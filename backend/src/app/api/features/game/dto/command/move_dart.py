from typing import Literal

from pydantic import Field

from app.api.core.dto.base import CamelModel


class MoveDartDto(CamelModel):
    """Client -> server: move one dart of the open visit to another place in it —
    a throw the camera missed lands last when entered by hand."""

    type: Literal["move_dart"]
    index: int = Field(ge=0)
    to_index: int = Field(ge=0)
