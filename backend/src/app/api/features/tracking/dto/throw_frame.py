from typing import Literal

from app.api.core.dto.base import CamelModel


class ThrowFrameMessage(CamelModel):
    """Client -> server: a still frame captured after the frame-diff trigger."""

    type: Literal["throw_frame"]
    image: str  # base64-encoded JPEG
