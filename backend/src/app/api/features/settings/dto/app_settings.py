from typing import Annotated, Literal, Self

from pydantic import Field, field_validator

from app.api.core.dto.base import CamelModel
from app.api.features.settings.domain.app_settings import AppSettings
from app.api.core.domain.language import Language
from app.api.features.announcement.domain.speaker import Voice


class AppSettingsDto(CamelModel):
    """The whole set, both ways: the answer to a read and the body of a write.
    Sent complete rather than as a patch, so a switch never has an undefined
    state on the wire."""

    advance_on_pull: bool
    evaluation_enabled: bool
    language: Language | None = None
    preferred_doubles: list[Annotated[int, Field(ge=1, le=20)] | Literal[25]] = []
    announcer_language: Language | None = None
    announcer_voice: Voice = Voice.FIRST

    @field_validator("preferred_doubles")
    @classmethod
    def unique(cls, doubles: list[int]) -> list[int]:
        """Drop repeats, keeping each double's first place."""
        return list(dict.fromkeys(doubles))

    @classmethod
    def from_entity(cls, settings: AppSettings) -> Self:
        return cls(
            advance_on_pull=settings.advance_on_pull,
            evaluation_enabled=settings.evaluation_enabled,
            language=settings.language,
            preferred_doubles=list(settings.preferred_doubles),
            announcer_language=settings.announcer_language,
            announcer_voice=settings.announcer_voice,
        )

    def to_entity(self) -> AppSettings:
        return AppSettings(
            advance_on_pull=self.advance_on_pull,
            evaluation_enabled=self.evaluation_enabled,
            language=self.language,
            preferred_doubles=tuple(self.preferred_doubles),
            announcer_language=self.announcer_language,
            announcer_voice=self.announcer_voice,
        )
