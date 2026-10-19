from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.checkout import Setup


class SetupDto(CamelModel):
    """Darts to throw when the visit cannot finish, and the points they leave."""

    darts: list[str]
    leave: int

    @classmethod
    def from_entity(cls, setup: Setup) -> Self:
        return cls(darts=list(setup.darts), leave=setup.leave)
