"""Measures where the triple and double ring of one board lie, off its calibration picture:
rays from the centre, mapped into the image through the homography, walked for colour runs.
"""

import math
import statistics

import numpy as np

from app.api.features.calibration.domain.board_geometry import (
    DOUBLE_INNER_RADIUS,
    DOUBLE_OUTER_RADIUS,
    SECTOR_COUNT,
    STANDARD_RINGS,
    TRIPLE_INNER_RADIUS,
    TRIPLE_OUTER_RADIUS,
    RingRadii,
    sector_centre_angle,
)

# Rays per sector, as offsets from its centre line, clear of the wires on either side.
_RAY_OFFSETS = tuple(math.radians(degrees) for degrees in (-5.0, -2.5, 0.0, 2.5, 5.0))

# Sampling along a ray, in board mm.
_STEP_MM = 0.1
_RAY_RADII = np.arange(85.0, 180.0, _STEP_MM)

# How far beyond its standard edges a ring is looked for.
_SEARCH_MM = 6.0

# Gaps in the colour this short are bridged (the larger of the two, per ray).
_BRIDGE_MM = 1.0
_BRIDGE_PX = 2.0

# A coloured run shorter than this is not a ring.
_MIN_RUN_MM = 4.0

# Below this resolution colour bleeds across the ring edges by more than the error being fixed.
_MIN_PX_PER_MM = 1.0

# Share of rays that must find a ring before its measurement replaces the standard.
_MIN_RAY_SHARE = 0.4

# How far a measured edge may lie from the standard before it is distrusted.
_MAX_DEVIATION_MM = 4.0

# The colour mask reaches into the wires; edges are moved this far into the ring.
_EDGE_INSET_MM = 0.5


def measure_rings(homography: np.ndarray, colour: np.ndarray) -> RingRadii:
    """The board's ring radii read off its red/green mask; standard where too few rays agree."""
    inverse = np.linalg.inv(homography)
    edges: dict[str, list[float]] = {
        "triple_inner": [],
        "triple_outer": [],
        "double_inner": [],
        "double_outer": [],
    }
    scales: list[float] = []

    for index in range(SECTOR_COUNT):
        for offset in _RAY_OFFSETS:
            ray = _sample_ray(colour, inverse, sector_centre_angle(index) + offset)
            if ray is None:
                continue
            coloured, px_per_mm = ray
            scales.append(px_per_mm)
            bridge = math.ceil(max(_BRIDGE_MM, _BRIDGE_PX / px_per_mm) / _STEP_MM)
            triple = _ring_run(coloured, TRIPLE_INNER_RADIUS, TRIPLE_OUTER_RADIUS, bridge)
            if triple is not None:
                edges["triple_inner"].append(triple[0])
                edges["triple_outer"].append(triple[1])
            double = _ring_run(coloured, DOUBLE_INNER_RADIUS, DOUBLE_OUTER_RADIUS, bridge)
            if double is not None:
                edges["double_inner"].append(double[0])
                edges["double_outer"].append(double[1])

    if not scales or statistics.median(scales) < _MIN_PX_PER_MM:
        return STANDARD_RINGS

    rays = SECTOR_COUNT * len(_RAY_OFFSETS)
    measured = {
        "triple_inner": _settle(edges["triple_inner"], TRIPLE_INNER_RADIUS, _EDGE_INSET_MM, rays),
        "triple_outer": _settle(edges["triple_outer"], TRIPLE_OUTER_RADIUS, -_EDGE_INSET_MM, rays),
        "double_inner": _settle(edges["double_inner"], DOUBLE_INNER_RADIUS, _EDGE_INSET_MM, rays),
        "double_outer": _settle(edges["double_outer"], DOUBLE_OUTER_RADIUS, -_EDGE_INSET_MM, rays),
    }
    radii = list(measured.values())
    if radii != sorted(radii):
        return STANDARD_RINGS
    return RingRadii(**measured)


def _settle(edges: list[float], standard: float, inset: float, rays: int) -> float:
    """The median edge moved by `inset`, or the standard if too few rays found it or it strays."""
    if len(edges) < _MIN_RAY_SHARE * rays:
        return standard
    radius = statistics.median(edges) + inset
    return radius if abs(radius - standard) <= _MAX_DEVIATION_MM else standard


def _sample_ray(
    colour: np.ndarray, inverse: np.ndarray, angle: float
) -> tuple[np.ndarray, float] | None:
    """Whether each sample along the ray is red or green, and the ray's px/mm; None off-image."""
    board = np.vstack(
        [_RAY_RADII * math.cos(angle), _RAY_RADII * math.sin(angle), np.ones_like(_RAY_RADII)]
    )
    image = inverse @ board
    xs, ys = image[0] / image[2], image[1] / image[2]
    columns, rows = np.round(xs).astype(int), np.round(ys).astype(int)

    height, width = colour.shape[:2]
    if columns.min() < 0 or rows.min() < 0 or columns.max() >= width or rows.max() >= height:
        return None

    px_per_mm = math.hypot(xs[-1] - xs[0], ys[-1] - ys[0]) / (_RAY_RADII[-1] - _RAY_RADII[0])
    return colour[rows, columns] > 0, px_per_mm


def _ring_run(
    coloured: np.ndarray, inner: float, outer: float, bridge: int
) -> tuple[float, float] | None:
    """Edges (mm) of the longest coloured run near the ring between `inner` and `outer`."""
    start = max(int((inner - _SEARCH_MM - _RAY_RADII[0]) / _STEP_MM), 0)
    end = min(int((outer + _SEARCH_MM - _RAY_RADII[0]) / _STEP_MM), len(coloured))
    window = coloured[start:end].copy()

    # Bridge short gaps so a wire shadow or a noisy pixel does not split the ring.
    gaps = _runs(~window)
    for first, last in gaps:
        if first > 0 and last < len(window) and last - first <= bridge:
            window[first:last] = True

    runs = [run for run in _runs(window) if (run[1] - run[0]) * _STEP_MM >= _MIN_RUN_MM]
    if not runs:
        return None
    first, last = max(runs, key=lambda run: run[1] - run[0])
    return (
        float(_RAY_RADII[start + first]) - _STEP_MM / 2,
        float(_RAY_RADII[start + last - 1]) + _STEP_MM / 2,
    )


def _runs(flags: np.ndarray) -> list[tuple[int, int]]:
    """Half-open index ranges where `flags` is true."""
    padded = np.concatenate([[False], flags, [False]]).astype(np.int8)
    changes = np.flatnonzero(np.diff(padded))
    return list(zip(changes[::2].tolist(), changes[1::2].tolist()))
