from datetime import datetime
from typing import Self

from pydantic import Field

from app.api.core.dto.base import CamelModel
from app.api.features.settings.domain.filter_use import FilterUse

# Picks an account keeps; the client drops its weakest beyond this.
MAX_FILTER_USES = 50


class FilterUseDto(CamelModel):
    view: str = Field(min_length=1, max_length=32)
    key: str = Field(min_length=1, max_length=32)
    value: str = Field(min_length=1, max_length=128)
    score: float = Field(ge=0, le=1_000_000)
    last_used_at: datetime

    @classmethod
    def from_entity(cls, use: FilterUse) -> Self:
        return cls(
            view=use.view,
            key=use.key,
            value=use.value,
            score=use.score,
            last_used_at=use.last_used_at,
        )

    def to_entity(self) -> FilterUse:
        return FilterUse(
            view=self.view,
            key=self.key,
            value=self.value,
            score=self.score,
            last_used_at=self.last_used_at,
        )


class FilterUsageDto(CamelModel):
    """All of an account's picks, both ways: bounded in size, not in meaning."""

    uses: list[FilterUseDto] = Field(max_length=MAX_FILTER_USES)

    @classmethod
    def from_entities(cls, uses: tuple[FilterUse, ...]) -> Self:
        return cls(uses=[FilterUseDto.from_entity(use) for use in uses])

    def to_entities(self) -> tuple[FilterUse, ...]:
        return tuple(use.to_entity() for use in self.uses)
