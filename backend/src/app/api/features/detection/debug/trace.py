"""What dart detection saw at each stage, so a run can be judged by eye.

Same arrangement as `CalibrationTrace`: `detect_dart` only holds on to values it
computes anyway, so recording is free and always on. Data only — rendering is
`render.py`.
"""

from dataclasses import dataclass, field

import numpy as np

from app.api.features.detection.domain.detection_failure import DetectionFailure


@dataclass
class DetectionTrace:
    reference: np.ndarray | None = None
    frame: np.ndarray | None = None
    # `frame` warped onto `reference`. Comparing the two is the quickest way to
    # tell a real change from a registration error.
    aligned: np.ndarray | None = None
    alignment: np.ndarray | None = None
    alignment_inliers: int = 0
    # How far the camera moved between the two frames, in pixels of board
    # outline. Registration absorbs it, but its sub-pixel remainder is what
    # lights up wires and printed numbers, so it belongs next to the result.
    alignment_shift_px: float = 0.0

    # The two radii the difference is judged against. `region` is the seed area a
    # change must reach to be believed; `search` is the wider area a dart may
    # extend into once it has reached the seed. Everything outside `search` is
    # never looked at.
    region: np.ndarray | None = None
    search: np.ndarray | None = None
    # The same two boundaries as exact image-space curves. The masks are what
    # the pipeline tests against; these are what the debug images draw, so an
    # outline is not mistaken for a rasterisation artefact of its mask.
    region_outline: np.ndarray | None = None
    search_outline: np.ndarray | None = None
    # Fraction of the seed outline that falls outside the frame. Non-zero means
    # the board is not fully in shot — a framing problem, not an algorithm one.
    region_clipped: float = 0.0

    # Which reference pixels the warped frame actually covered. Everything else
    # is `warpPerspective`'s black fill, which differences as a bright streak
    # along the frame edge and is not a change at all.
    observed: np.ndarray | None = None
    # The part of `region` the incoming frame did not reach. Board area the
    # camera moved out of shot between the two frames — a dart landing there
    # cannot be seen, so it is worth telling apart from finding nothing.
    unobserved_region: np.ndarray | None = None

    difference: np.ndarray | None = None  # greyscale, before thresholding
    # The mask as it stands after each cleanup step, so a lost dart can be
    # blamed on the step that lost it rather than on the final mask alone.
    raw_mask: np.ndarray | None = None  # threshold + search clip, nothing else
    speckle_removed: np.ndarray | None = None  # components below the area floor
    outside_removed: np.ndarray | None = None  # components that never reach `region`
    change_mask: np.ndarray | None = None  # what fragment fusion actually sees

    labels: np.ndarray | None = None
    # Fragment fusion: which labelled components were taken for the dart, which
    # one anchored the fit as the flight, and the line they were fused along
    # (anchor point, unit direction). `eligible_labels` are the ones within one
    # dart length of the anchor — the rest could never have been supporters.
    flight_label: int | None = None
    eligible_labels: list[int] = field(default_factory=list)
    inlier_labels: list[int] = field(default_factory=list)
    fitted_line: tuple[np.ndarray, np.ndarray | None] | None = None

    # The fused blob's own dimensions in board millimetres: its extent along the
    # principal axis, across it, and its area. These are what tell a dart from
    # something merely in the way — a player fetching their darts covers the
    # board with a blob the fit is otherwise happy to call a dart.
    dart_length_mm: float = 0.0
    dart_width_mm: float = 0.0
    dart_area_mm2: float = 0.0

    # The axis fit on the fused blob: both ends (tip first) and the width
    # measured at each, which is what decided which end is the flight. A tip on
    # the wrong end of an otherwise perfect blob shows up here and nowhere else.
    axis_ends: tuple[np.ndarray, np.ndarray] | None = None
    end_widths: tuple[float, float] | None = None

    pixels_per_mm: float = 0.0
    # Area floors actually in force for this frame, in pixels. They are derived
    # from `pixels_per_mm`, and at the low end of the test set the millimetre
    # figures come out to only a handful of pixels — worth showing rather than
    # recomputing by hand.
    minimum_speckle_px: float = 0.0
    minimum_candidate_px: float = 0.0

    failure: DetectionFailure | None = None
