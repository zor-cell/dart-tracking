"""Writes the tracking events, and never lets a failure there reach the game.

An event that accompanies a state change is appended inside its transaction; the
rest get one of their own.
"""

import logging

from app.api.features.detection.debug.trace import DetectionTrace
from app.api.features.evaluation.domain.tracking_event import TrackingEvent
from app.api.features.evaluation.persistence.evaluation_repository import repository
from app.infrastructure import database

logger = logging.getLogger(__name__)


async def record(game_id: str, event: TrackingEvent) -> None:
    """Append one event on its own. A failure here loses a measurement, not a
    throw, so it is logged rather than raised."""
    try:
        async with database.session_scope() as session:
            repository.append(session, game_id, event)
    except Exception:  # noqa: BLE001 - diagnostics must not break the game
        logger.exception("[evaluation] could not record %s", event.kind)


def metrics_of(trace: DetectionTrace) -> dict[str, float]:
    """Detector figures worth keeping per throw: how the dart arrived, how big
    it was, how far the camera had moved (docs/feature/erkennung.md §4)."""
    return {
        "fragment_count": float(trace.fragment_count),
        "largest_fragment_share": round(trace.largest_fragment_share, 4),
        "anchor_to_tip_mm": round(trace.anchor_to_tip_mm, 2),
        "dart_length_mm": round(trace.dart_length_mm, 2),
        "dart_width_mm": round(trace.dart_width_mm, 2),
        "dart_area_mm2": round(trace.dart_area_mm2, 2),
        "alignment_shift_px": round(trace.alignment_shift_px, 2),
        "alignment_inliers": float(trace.alignment_inliers),
        "region_clipped": round(trace.region_clipped, 4),
        "pixels_per_mm": round(trace.pixels_per_mm, 4),
    }
