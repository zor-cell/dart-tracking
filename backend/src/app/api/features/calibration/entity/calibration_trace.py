"""What board detection saw at each stage, so a run can be judged by eye.

`detect_board` fills one of these on every call: it only keeps references to
values it computes anyway, so recording costs nothing and does not have to be
switched on. Pass one in to get it back.

This is deliberately data only — no drawing. Turning a trace into pictures is
the job of scripts/debug_images.py, which keeps OpenCV rendering out of the
service and lets the debug views change without touching detection.
"""

from dataclasses import dataclass, field

import numpy as np

from app.api.features.calibration.entity.calibration_failure import CalibrationFailure


@dataclass
class CalibrationPass:
    """One refinement pass: the wire search from a given centre estimate.

    Everything after `transitions` stays None if the pass gave up before
    getting there, which is precisely the case worth looking at.
    """

    centre: tuple[float, float]
    ring_colours: list[int] = field(default_factory=list)
    transitions: list[tuple[float, bool]] = field(default_factory=list)
    correspondences: list[tuple[float, float]] | None = None
    homography: np.ndarray | None = None
    projected_centre: tuple[float, float] | None = None


@dataclass
class CalibrationTrace:
    """`current` always points at the pass in progress, so the functions doing
    the actual detection work can just write to `trace.current.whatever`
    without board_detector having to thread a pass argument through every call.
    """

    image: np.ndarray | None = None
    red_mask: np.ndarray | None = None
    green_mask: np.ndarray | None = None
    hull: np.ndarray | None = None
    ellipse: tuple[tuple[float, float], tuple[float, float], float] | None = None
    passes: list[CalibrationPass] = field(default_factory=list)
    current: CalibrationPass | None = None
    failure: CalibrationFailure | None = None

    def begin_pass(self, centre: tuple[float, float]) -> None:
        """Start recording a new refinement pass."""
        self.current = CalibrationPass(centre=centre)
        self.passes.append(self.current)
