"""Client -> server: the trigger's own view of one frame of the episode, in test runs."""

from typing import Literal

from pydantic import PositiveInt

from app.api.core.dto.base import CamelModel


class TriggerSnapshotDto(CamelModel):
    moment: Literal["arm", "peak", "capture"]
    t_ms: int  # relative to the capturing frame, negative before it
    width: PositiveInt
    height: PositiveInt
    luma: str  # base64, one byte per pixel, row-major
    changed: str  # base64, one bit per pixel, row-major, most significant bit first
