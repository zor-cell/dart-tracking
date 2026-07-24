"""What dart detection saw at each stage, so a run can be judged by eye.

Same arrangement as `CalibrationTrace`: `detect_dart` only holds on to values it
computes anyway, so recording is free and always on. Data only — rendering is
`services/dart_debug_images.py`.
"""

from dataclasses import dataclass

import numpy as np

from app.api.features.detection.entity.detection_failure import DetectionFailure


@dataclass
class DetectionTrace:
    reference: np.ndarray | None = None
    frame: np.ndarray | None = None
    # `frame` warped onto `reference`. Comparing the two is the quickest way to
    # tell a real change from a registration error.
    aligned: np.ndarray | None = None
    alignment: np.ndarray | None = None
    alignment_inliers: int = 0
    difference: np.ndarray | None = None  # greyscale, before thresholding
    change_mask: np.ndarray | None = None  # after threshold, morphology and ROI
    labels: np.ndarray | None = None
    chosen_label: int | None = None
    pixels_per_mm: float = 0.0
    failure: DetectionFailure | None = None
