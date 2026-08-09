from typing import Literal

from app.api.core.dto.base import CamelModel


class NextPlayerDto(CamelModel):
    """Client -> server: end the visit and hand over to the next player."""

    type: Literal["next_player"]
