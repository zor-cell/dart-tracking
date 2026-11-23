from typing import Literal

from app.api.core.dto.base import CamelModel


class SetEvaluationDto(CamelModel):
    """Client -> server: keep this game's camera frames, or stop and delete them."""

    type: Literal["set_evaluation"]
    enabled: bool
