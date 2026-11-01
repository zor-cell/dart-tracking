from typing import Literal

from app.api.core.dto.base import CamelModel


class GameStatusUpdateDto(CamelModel):
    """The two things a person may say about a game: leave it out of their own
    list and statistics, or let it count again."""

    status: Literal["discarded", "active"]
