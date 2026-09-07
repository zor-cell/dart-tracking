from typing import Literal

from app.api.core.dto.base import CamelModel


class SetEvaluationDto(CamelModel):
    """Client -> server: mark this game as a test run, or stop.

    Game-wide rather than per device: it is the game that is being measured, and
    any device in the room may say so.
    """

    type: Literal["set_evaluation"]
    enabled: bool
