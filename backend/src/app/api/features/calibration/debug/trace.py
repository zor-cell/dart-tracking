"""What board detection saw at each stage; `detect_board` replaces the module-level
`board_detector.trace` on every call. Data only, rendered by `render.py`.
"""

from dataclasses import dataclass, field

import numpy as np

from app.api.features.calibration.domain.calibration_failure import CalibrationFailure


@dataclass
class CalibrationPass:
    """One refinement pass: the wire search from a given centre estimate; the fields
    after `transitions` stay None if the pass gave up before them.
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
    dropped_off_board: np.ndarray | None = None
    dropped_outer: np.ndarray | None = None
    kept_red: np.ndarray | None = None
    kept_green: np.ndarray | None = None
    hull: np.ndarray | None = None
    ellipse: tuple[tuple[float, float], tuple[float, float], float] | None = None
    passes: list[CalibrationPass] = field(default_factory=list)
    current: CalibrationPass | None = None
    failure: CalibrationFailure | None = None

    def begin_pass(self, centre: tuple[float, float]) -> None:
        """Start recording a new refinement pass."""
        self.current = CalibrationPass(centre=centre)
        self.passes.append(self.current)
