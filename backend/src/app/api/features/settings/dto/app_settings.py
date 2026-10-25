from typing import Annotated, Literal, Self

from pydantic import Field, field_validator

from app.api.core.dto.base import CamelModel
from app.api.features.settings.domain.app_settings import AppSettings


class AppSettingsDto(CamelModel):
    """The whole set, both ways: the answer to a read and the body of a write.
    Sent complete rather than as a patch, so a switch never has an undefined
    state on the wire."""

    confirm_throw_enabled: bool
    evaluation_enabled: bool
    preferred_doubles: list[Annotated[int, Field(ge=1, le=20)] | Literal[25]] = []

    @field_validator("preferred_doubles")
    @classmethod
    def unique(cls, doubles: list[int]) -> list[int]:
        """Drop repeats, keeping each double's first place."""
        return list(dict.fromkeys(doubles))

    @classmethod
    def from_entity(cls, settings: AppSettings) -> Self:
        return cls(
            confirm_throw_enabled=settings.confirm_throw_enabled,
            evaluation_enabled=settings.evaluation_enabled,
            preferred_doubles=list(settings.preferred_doubles),
        )

    def to_entity(self) -> AppSettings:
        return AppSettings(
            confirm_throw_enabled=self.confirm_throw_enabled,
            evaluation_enabled=self.evaluation_enabled,
            preferred_doubles=tuple(self.preferred_doubles),
        )
