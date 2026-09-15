from typing import Literal

from pydantic import Field

from app.api.core.dto.base import CamelModel


class RemoveDartDto(CamelModel):
    """Client -> server: take one dart out of the open visit, by its position in it."""

    type: Literal["remove_dart"]
    index: int = Field(ge=0)
