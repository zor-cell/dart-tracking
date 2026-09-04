from typing import Literal

from app.api.core.dto.base import CamelModel


class GameStatusUpdateDto(CamelModel):
    """The two things a person may say about a game: leave it out of the
    statistics, or let it count again. What "counting again" means is derived
    from the score (docs/feature/persistenz.md §4.5), not taken from here."""

    status: Literal["discarded", "active"]
