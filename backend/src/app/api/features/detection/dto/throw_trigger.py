"""Client -> server: what the frame-diff episode behind a throw frame looked like."""

from pydantic import NonNegativeFloat, NonNegativeInt

from app.api.core.dto.base import CamelModel
from app.api.features.detection.dto.trigger_sample import TriggerSampleDto
from app.api.features.detection.dto.trigger_snapshot import TriggerSnapshotDto


class ThrowTriggerDto(CamelModel):
    """The client's own trigger metrics, logged beside the detector's so the two
    halves of a false trigger can be told apart."""

    peak_blocks: NonNegativeInt  # highest active-cell count in the episode
    peak_excess: NonNegativeFloat  # highest count above the steady baseline
    # Bounding box of the active cells at the peak frame, in cells.
    span_cols: NonNegativeInt
    span_rows: NonNegativeInt
    frames: NonNegativeInt  # episode length, in processed frames
    timed_out: bool  # captured by the motion timeout instead of settling
    grid_cols: NonNegativeInt  # grid the counts and spans are relative to
    grid_rows: NonNegativeInt
    timeline: list[TriggerSampleDto] = []  # the frames leading up to the capture
    snapshots: list[TriggerSnapshotDto] = []  # sent in test runs only
