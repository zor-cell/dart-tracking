"""Client -> server: one processed frame of the trigger episode behind a throw frame."""

from typing import Literal

from pydantic import NonNegativeFloat, NonNegativeInt

from app.api.core.dto.base import CamelModel


class TriggerSampleDto(CamelModel):
    t_ms: int  # relative to the capturing frame, negative before it
    state: Literal["idle", "motion", "settling"]
    active_blocks: NonNegativeInt
    ambient_blocks: NonNegativeFloat
    cells: list[NonNegativeInt]  # indices of the active cells, row-major
