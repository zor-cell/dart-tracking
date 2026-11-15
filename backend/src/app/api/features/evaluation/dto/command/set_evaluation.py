from typing import Literal

from app.api.core.dto.base import CamelModel


class SetEvaluationDto(CamelModel):
    """Client -> server: mark this game as a test run, or stop, from any device."""

    type: Literal["set_evaluation"]
    enabled: bool
