from typing import Self

from pydantic import Field, model_validator

from app.api.core.dto.base import CamelModel


class PlayerSlotDto(CamelModel):
    """One seat in a new game: either an identity from the address book or a
    name typed for a guest (docs/feature/done/persistenz.md §4.4)."""

    player_id: str | None = None
    name: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def exactly_one(self) -> Self:
        name = self.name.strip() if self.name else None
        if (self.player_id is None) == (not name):
            raise ValueError("a seat takes either playerId or name")
        return self.model_copy(update={"name": name})
