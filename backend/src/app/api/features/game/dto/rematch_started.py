from typing import Literal

from app.api.core.dto.base import CamelModel


class RematchStartedDto(CamelModel):
    """Server -> previous game's room: the rematch to move over to."""

    type: Literal["rematch_started"] = "rematch_started"
    game_id: str
