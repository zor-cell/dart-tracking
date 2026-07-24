"""Render every stage of a `detect_dart` run as separate images.

Same idea as `board_debug_images.py`: a wrong score is almost never wrong at
the last step, so the useful question is which stage lost the dart —
registration, thresholding, or the axis fit. Used by
scripts/debug_detection.py and, later, by the detection websocket path.
"""

from pathlib import Path

import cv2
import numpy as np

from app.api.features.detection.entity.dart import Dart
from app.api.features.detection.entity.detection_trace import DetectionTrace

_COLOUR_AXIS = (255, 0, 255)  # magenta
_COLOUR_TIP = (0, 255, 255)  # yellow
_COLOUR_CHOSEN = (0, 220, 0)
_COLOUR_REJECTED = (140, 140, 140)


def write_debug_images(
    trace: DetectionTrace, dart: Dart | None, out_dir: Path
) -> list[Path]:
    """Write whichever stages the trace reached, and return the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    def emit(name: str, image: np.ndarray | None) -> None:
        if image is None:
            return
        path = out_dir / name
        cv2.imwrite(str(path), image)
        written.append(path)

    emit("01_alignment.jpg", _draw_alignment(trace))
    emit("02_difference.jpg", _draw_difference(trace))
    emit("03_mask.jpg", _draw_mask(trace))
    emit("04_components.jpg", _draw_components(trace))
    if dart is not None:
        emit("05_result.jpg", _draw_result(trace, dart))

    return written


def _draw_alignment(trace: DetectionTrace) -> np.ndarray | None:
    """Reference in red, aligned frame in cyan — grey means they agree.

    Coloured fringes along the wires mean the registration is off, which is the
    one failure that mimics a dart everywhere at once.
    """
    if trace.reference is None or trace.aligned is None:
        return None
    reference = cv2.cvtColor(trace.reference, cv2.COLOR_BGR2GRAY)
    aligned = cv2.cvtColor(trace.aligned, cv2.COLOR_BGR2GRAY)
    return cv2.merge([aligned, aligned, reference])


def _draw_difference(trace: DetectionTrace) -> np.ndarray | None:
    """The raw per-pixel difference, stretched so faint traces are visible.

    Held against 03_mask.jpg this answers the question the mask alone cannot:
    was the dart never in the difference, or was it thresholded away?
    """
    if trace.difference is None:
        return None
    return cv2.applyColorMap(
        cv2.normalize(trace.difference, None, 0, 255, cv2.NORM_MINMAX), cv2.COLORMAP_INFERNO
    )


def _draw_mask(trace: DetectionTrace) -> np.ndarray | None:
    """The thresholded, cleaned change mask over the frame it came from."""
    if trace.change_mask is None or trace.aligned is None:
        return None
    canvas = trace.aligned.copy()
    canvas[trace.change_mask > 0] = _COLOUR_CHOSEN
    return canvas


def _draw_components(trace: DetectionTrace) -> np.ndarray | None:
    """Which blob was taken for the dart, and what else was on offer."""
    if trace.labels is None or trace.aligned is None:
        return None
    canvas = trace.aligned.copy()
    canvas[(trace.labels > 0) & (trace.labels != trace.chosen_label)] = _COLOUR_REJECTED
    canvas[trace.labels == trace.chosen_label] = _COLOUR_CHOSEN
    return canvas


def _draw_result(trace: DetectionTrace, dart: Dart) -> np.ndarray:
    """The fitted axis and the tip that was scored."""
    canvas = trace.aligned.copy()
    tip, far_end = dart.axis_image
    cv2.line(
        canvas,
        tuple(round(v) for v in tip),
        tuple(round(v) for v in far_end),
        _COLOUR_AXIS,
        2,
        cv2.LINE_AA,
    )
    cv2.drawMarker(
        canvas, tuple(round(v) for v in tip), _COLOUR_TIP, cv2.MARKER_CROSS, 18, 2, cv2.LINE_AA
    )
    cv2.putText(
        canvas,
        f"{dart.segment.label} = {dart.points}",
        (round(tip[0]) + 12, round(tip[1]) - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        _COLOUR_TIP,
        2,
        cv2.LINE_AA,
    )
    return canvas
