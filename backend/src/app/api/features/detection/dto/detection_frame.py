from typing import Literal

from app.api.core.dto.base import CamelModel
from app.api.features.detection.dto.throw_trigger import ThrowTriggerDto


class DetectionFrameDto(CamelModel):
    """Client -> server: a still frame captured after the frame-diff trigger."""

    type: Literal["detection_frame"]
    image: str  # base64-encoded JPEG
    trigger: ThrowTriggerDto | None = None
