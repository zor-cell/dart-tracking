"""What dart detection saw at each stage, so a run can be judged by eye.

Data only — rendering is `render.py`. See docs/feature/erkennung.md §4.
"""

from dataclasses import dataclass, field

import numpy as np

from app.api.features.detection.domain.detection_failure import DetectionFailure


@dataclass
class DetectionTrace:
    reference: np.ndarray | None = None
    frame: np.ndarray | None = None
    aligned: np.ndarray | None = None  # `frame` warped onto `reference`
    alignment: np.ndarray | None = None
    alignment_inliers: int = 0
    # Camera movement between the two frames, in pixels of board outline.
    alignment_shift_px: float = 0.0

    # Seed area a change must reach, and the wider area a dart may extend into
    # once it has. Outside `search` is never looked at.
    region: np.ndarray | None = None
    search: np.ndarray | None = None
    # The same two boundaries as exact image-space curves, for drawing.
    region_outline: np.ndarray | None = None
    search_outline: np.ndarray | None = None
    # Fraction of the seed outline falling outside the frame.
    region_clipped: float = 0.0

    # Which reference pixels the warped frame covered; the rest is
    # `warpPerspective`'s black fill.
    observed: np.ndarray | None = None
    # The part of `region` the incoming frame did not reach.
    unobserved_region: np.ndarray | None = None

    difference: np.ndarray | None = None  # greyscale, before thresholding
    # The mask after each cleanup step.
    raw_mask: np.ndarray | None = None  # threshold + search clip, nothing else
    speckle_removed: np.ndarray | None = None  # components below the area floor
    outside_removed: np.ndarray | None = None  # components that never reach `region`
    change_mask: np.ndarray | None = None  # what fragment fusion sees

    labels: np.ndarray | None = None
    # Fragment fusion: the components taken for the dart, the one that anchored
    # the fit as the flight, and the line they were fused along.
    flight_label: int | None = None
    eligible_labels: list[int] = field(default_factory=list)  # within one dart length
    inlier_labels: list[int] = field(default_factory=list)
    fitted_line: tuple[np.ndarray, np.ndarray | None] | None = None

    # The fused blob's dimensions in board millimetres.
    dart_length_mm: float = 0.0
    dart_width_mm: float = 0.0
    dart_area_mm2: float = 0.0

    # Axis fit on the fused blob: both ends (tip first) and the width at each,
    # which is what decided which end is the flight.
    axis_ends: tuple[np.ndarray, np.ndarray] | None = None
    end_widths: tuple[float, float] | None = None

    pixels_per_mm: float = 0.0
    # Area floors in force for this frame, in pixels, derived from `pixels_per_mm`.
    minimum_speckle_px: float = 0.0
    minimum_candidate_px: float = 0.0

    failure: DetectionFailure | None = None
