from typing import Literal

from app.api.core.dto.base import CamelModel


class ThrowFrameMessage(CamelModel):
    """Client -> server: a still frame captured after the frame-diff trigger."""

    type: Literal["detection_frame"]
    image: str  # base64-encoded JPEG
    # Off unless the client asks: on, the server dumps per-stage debug images.
    debug: bool = False
