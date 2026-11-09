from app.api.core.dto.base import CamelModel


class SpeechTestDto(CamelModel):
    """The clips of the test phrase; empty when the server has no voice."""

    clips: list[str]
