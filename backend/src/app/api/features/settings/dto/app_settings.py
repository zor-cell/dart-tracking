from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.settings.domain.app_settings import AppSettings


class AppSettingsDto(CamelModel):
    """The whole set, both ways: the answer to a read and the body of a write.
    Sent complete rather than as a patch, so a switch never has an undefined
    state on the wire."""

    manual_entry_enabled: bool
    confirm_throw_enabled: bool
    evaluation_enabled: bool
    debug_calibration: bool
    debug_detection: bool
    debug_client_detection: bool

    @classmethod
    def from_entity(cls, settings: AppSettings) -> Self:
        return cls(
            manual_entry_enabled=settings.manual_entry_enabled,
            confirm_throw_enabled=settings.confirm_throw_enabled,
            evaluation_enabled=settings.evaluation_enabled,
            debug_calibration=settings.debug_calibration,
            debug_detection=settings.debug_detection,
            debug_client_detection=settings.debug_client_detection,
        )

    def to_entity(self) -> AppSettings:
        return AppSettings(
            manual_entry_enabled=self.manual_entry_enabled,
            confirm_throw_enabled=self.confirm_throw_enabled,
            evaluation_enabled=self.evaluation_enabled,
            debug_calibration=self.debug_calibration,
            debug_detection=self.debug_detection,
            debug_client_detection=self.debug_client_detection,
        )
