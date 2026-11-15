"""Render every stage of a `detect_dart` run as a numbered image, from the search
region (01) through alignment, difference, threshold, cleanup, mask, fused
components and flight axis to the scored tip (09).
"""

from pathlib import Path

import cv2
import numpy as np

from app.api.features.detection.domain.detection import Dart
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.detection.debug.trace import DetectionTrace

_COLOUR_AXIS = (255, 0, 255)  # magenta
_COLOUR_TIP = (0, 255, 255)  # yellow
_COLOUR_CHOSEN = (0, 220, 0)
_COLOUR_SATURATION = (0, 255, 255)  # yellow — only the saturation channel saw it
_COLOUR_FLIGHT = (0, 140, 255)  # orange — the fragment that anchored the fit
_COLOUR_LINE = (255, 0, 255)  # magenta — the fused dart line, as the axis
_COLOUR_REJECTED = (140, 140, 140)
_COLOUR_TOO_SMALL = (70, 70, 70)  # below the fragment area floor: never a candidate
_COLOUR_REGION = (0, 255, 255)  # the seed radius
_COLOUR_SEARCH = (0, 160, 255)  # the outer radius a dart may extend to
_COLOUR_SPECKLE = (0, 0, 255)  # dropped as noise
_COLOUR_UNANCHORED = (255, 80, 80)  # dropped for never reaching the board
_COLOUR_UNOBSERVED = (255, 0, 255)  # board the incoming frame did not cover

_LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX


def write_debug_images(trace: DetectionTrace, dart: Dart | None, out_dir: Path) -> list[Path]:
    """Write whichever stages the trace reached, and return the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    def emit(name: str, image: np.ndarray | None) -> None:
        if image is None:
            return
        path = out_dir / name
        cv2.imwrite(str(path), image)
        written.append(path)

    emit("01_region.jpg", _draw_region(trace))
    emit("02_alignment.jpg", _draw_alignment(trace))
    emit("03_difference.jpg", _draw_difference(trace))
    emit("04_threshold.jpg", _draw_threshold(trace))
    emit("05_cleanup.jpg", _draw_cleanup(trace))
    emit("06_mask.jpg", _draw_mask(trace))
    emit("07_components.jpg", _draw_components(trace))
    emit("08_axis.jpg", _draw_axis(trace))
    if dart is not None:
        emit("09_result.jpg", _draw_result(trace, dart))

    return written


def _caption(canvas: np.ndarray, lines: list[str]) -> np.ndarray:
    """Stamp a few lines of figures into the top-left corner."""
    for index, line in enumerate(lines):
        origin = (8, 20 + index * 18)
        # Drawn twice: a dark stroke under the light text keeps it readable over
        # both the white board beds and the black ones.
        cv2.putText(canvas, line, origin, _LABEL_FONT, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(canvas, line, origin, _LABEL_FONT, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def _outline(canvas: np.ndarray, curve: np.ndarray | None, colour: tuple[int, int, int]) -> None:
    """Draw a boundary curve onto the canvas as a polyline."""
    if curve is None:
        return
    cv2.polylines(canvas, [curve.astype(np.int32)], True, colour, 1, cv2.LINE_AA)


def _draw_region(trace: DetectionTrace) -> np.ndarray | None:
    """The search region: yellow is the seed radius a change must reach into, orange
    how far it may extend; everything dimmed is never looked at.
    """
    if trace.reference is None or trace.region is None:
        return None

    canvas = trace.reference.copy()
    if trace.search is not None:
        # Dim what is out of scope rather than blacking it out: the surround and
        # the wall are the context that says whether the framing is sane.
        outside = trace.search == 0
        canvas[outside] = (canvas[outside] * 0.35).astype(np.uint8)
        _outline(canvas, trace.search_outline, _COLOUR_SEARCH)
    # Board area the incoming frame did not cover, before anything else is drawn
    # over it: this is the strip that used to arrive as a bright false change.
    if trace.unobserved_region is not None:
        canvas[trace.unobserved_region > 0] = _COLOUR_UNOBSERVED
    _outline(canvas, trace.region_outline, _COLOUR_REGION)

    lines = [
        f"{trace.pixels_per_mm:.2f} px/mm",
        "yellow: seed radius (must reach in)",
        "orange: search radius (may extend to)",
    ]
    if trace.unobserved_region is not None and np.any(trace.unobserved_region):
        lines.append(
            f"magenta: board not covered by this frame "
            f"({int(np.count_nonzero(trace.unobserved_region))} px)"
        )
    if trace.region_clipped > 0:
        lines.append(f"! board {100 * trace.region_clipped:.0f}% outside the frame")
    return _caption(canvas, lines)


def _draw_alignment(trace: DetectionTrace) -> np.ndarray | None:
    """Reference in red, aligned frame in cyan: grey where they agree."""
    if trace.reference is None or trace.aligned is None:
        return None
    reference = cv2.cvtColor(trace.reference, cv2.COLOR_BGR2GRAY)
    aligned = cv2.cvtColor(trace.aligned, cv2.COLOR_BGR2GRAY)
    canvas = cv2.merge([aligned, aligned, reference])
    return _caption(
        canvas,
        [
            f"{trace.alignment_inliers} RANSAC inliers",
            f"camera moved {trace.alignment_shift_px:.1f} px",
        ],
    )


def _draw_difference(trace: DetectionTrace) -> np.ndarray | None:
    """The raw per-pixel difference, stretched so faint traces are visible."""
    if trace.difference is None:
        return None
    canvas = cv2.applyColorMap(
        cv2.normalize(trace.difference, None, 0, 255, cv2.NORM_MINMAX), cv2.COLORMAP_INFERNO
    )
    _outline(canvas, trace.region_outline, _COLOUR_REGION)
    _outline(canvas, trace.search_outline, _COLOUR_SEARCH)
    return _caption(canvas, [f"peak difference {trace.difference.max()} grey levels"])


def _draw_threshold(trace: DetectionTrace) -> np.ndarray | None:
    """Everything over the difference threshold, before any cleanup."""
    if trace.raw_mask is None or trace.aligned is None:
        return None
    canvas = trace.aligned.copy()
    canvas[trace.raw_mask > 0] = _COLOUR_CHOSEN
    if trace.saturation_only is not None:
        canvas[trace.saturation_only > 0] = _COLOUR_SATURATION
    _outline(canvas, trace.region_outline, _COLOUR_REGION)

    lines = [f"{int(np.count_nonzero(trace.raw_mask))} px over threshold"]
    # Which channel carried the change: a white flight on a cream bed is
    # invisible in intensity and shows here as saturation alone.
    if trace.saturation_only is not None:
        lines.append(
            f"yellow: saturation alone ({int(np.count_nonzero(trace.saturation_only))} px)"
        )
    return _caption(canvas, lines)


def _draw_cleanup(trace: DetectionTrace) -> np.ndarray | None:
    """What the two cleanup steps removed: red as speckle below the area floor, pale
    blue for never reaching the seed radius; green survived.
    """
    if trace.aligned is None or trace.speckle_removed is None:
        return None
    canvas = trace.aligned.copy()
    canvas[trace.speckle_removed > 0] = _COLOUR_SPECKLE
    if trace.outside_removed is not None:
        canvas[trace.outside_removed > 0] = _COLOUR_UNANCHORED
    if trace.change_mask is not None:
        canvas[trace.change_mask > 0] = _COLOUR_CHOSEN
    _outline(canvas, trace.region_outline, _COLOUR_REGION)

    return _caption(
        canvas,
        [
            f"red: speckle < {trace.minimum_speckle_px:.0f} px "
            f"({int(np.count_nonzero(trace.speckle_removed))} px)",
            f"blue: unanchored ({int(np.count_nonzero(trace.outside_removed))} px)",
            f"green: kept ({int(np.count_nonzero(trace.change_mask))} px)",
        ],
    )


def _draw_mask(trace: DetectionTrace) -> np.ndarray | None:
    """The cleaned change mask on its own, black on white, as fragment fusion gets it."""
    if trace.change_mask is None:
        return None
    canvas = cv2.cvtColor(trace.change_mask, cv2.COLOR_GRAY2BGR)
    _outline(canvas, trace.region_outline, _COLOUR_REGION)
    _outline(canvas, trace.search_outline, _COLOUR_SEARCH)
    return canvas


def _draw_components(trace: DetectionTrace) -> np.ndarray | None:
    """The fragment fusion: dark grey out of the flight's reach, light grey off the
    line, green the fused dart, orange its flight and cyan the fitted line.
    """
    if trace.labels is None or trace.aligned is None:
        return None
    canvas = trace.aligned.copy()

    # Painted outward from least to most interesting, so overlaps resolve the
    # right way round.
    canvas[trace.labels > 0] = _COLOUR_TOO_SMALL
    if trace.eligible_labels:
        canvas[np.isin(trace.labels, trace.eligible_labels)] = _COLOUR_REJECTED
    if trace.inlier_labels:
        canvas[np.isin(trace.labels, trace.inlier_labels)] = _COLOUR_CHOSEN
    if trace.flight_label is not None:
        canvas[trace.labels == trace.flight_label] = _COLOUR_FLIGHT

    if trace.fitted_line is not None and trace.fitted_line[1] is not None and trace.inlier_labels:
        anchor, direction = trace.fitted_line
        # Draw the line only across the fused fragments' actual span, not to the
        # image edges — the extent is the informative part.
        rows, columns = np.where(np.isin(trace.labels, trace.inlier_labels))
        projections = (np.column_stack((columns, rows)) - anchor) @ direction
        start = tuple(round(v) for v in anchor + direction * projections.min())
        end = tuple(round(v) for v in anchor + direction * projections.max())
        cv2.line(canvas, start, end, _COLOUR_LINE, 1, cv2.LINE_AA)

    lines = [
        f"candidate floor {trace.minimum_candidate_px:.0f} px (to vote)",
        f"{int(trace.labels.max())} components, "
        f"{len(trace.eligible_labels)} in reach, {len(trace.inlier_labels)} fused",
    ]
    # The size the blob was judged on. Printed even when it passed, because the
    # margin to the limit is what says whether a rejection was close.
    if trace.dart_length_mm:
        lines.append(
            f"blob {trace.dart_length_mm:.0f} x {trace.dart_width_mm:.0f} mm, "
            f"{trace.dart_area_mm2:.0f} mm2"
        )
    if trace.failure is DetectionFailure.IMPLAUSIBLE_SHAPE:
        lines.append("REJECTED: too big for a dart")
    elif trace.failure is DetectionFailure.DARTS_REMOVED:
        lines.append(f"REJECTED: dart removed ({100 * trace.changed_from_empty:.0f}% differs from empty board)")
    elif trace.rejected_miss:
        lines.append("REJECTED: too small for a miss")
    return _caption(canvas, lines)


def _draw_axis(trace: DetectionTrace) -> np.ndarray | None:
    """Which end of the fused blob was taken for the flight, with both end widths."""
    if trace.axis_ends is None or trace.end_widths is None or trace.aligned is None:
        return None
    canvas = trace.aligned.copy()
    if trace.change_mask is not None:
        canvas[trace.change_mask > 0] = _COLOUR_REJECTED
    if trace.inlier_labels and trace.labels is not None:
        canvas[np.isin(trace.labels, trace.inlier_labels)] = _COLOUR_CHOSEN

    tip, far_end = (tuple(round(v) for v in end) for end in trace.axis_ends)
    cv2.line(canvas, tip, far_end, _COLOUR_AXIS, 1, cv2.LINE_AA)
    cv2.drawMarker(canvas, tip, _COLOUR_TIP, cv2.MARKER_CROSS, 14, 2, cv2.LINE_AA)
    cv2.circle(canvas, far_end, 6, _COLOUR_FLIGHT, 2, cv2.LINE_AA)

    tip_width, flight_width = trace.end_widths
    return _caption(
        canvas,
        [
            f"tip end (cross) width {tip_width:.1f} px",
            f"flight end (circle) width {flight_width:.1f} px",
            f"margin {flight_width - tip_width:+.1f} px",
        ],
    )


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
    # Top left of the tip marker, white on a black outline.
    label = dart.segment.label
    (width, _), _ = cv2.getTextSize(label, _LABEL_FONT, 0.6, 2)
    origin = (round(tip[0]) - 4 - width, round(tip[1]) - 4)
    cv2.putText(canvas, label, origin, _LABEL_FONT, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(canvas, label, origin, _LABEL_FONT, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    x, y = dart.tip_board
    return _caption(canvas, [f"tip ({x:.1f}, {y:.1f}) mm   r={np.hypot(x, y):.1f} mm"])
