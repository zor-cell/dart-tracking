import numpy as np
import pytest

from app.api.features.detection.debug.trace import DetectionTrace
from app.api.features.detection.domain.change_region import ChangeRegion
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.detection.dto.throw_trigger import ThrowTriggerDto
from app.api.features.detection.services import dart_detector
from app.api.features.evaluation.services.recorder import trigger_metrics_of

TRIGGER = {
    "peakBlocks": 3, "peakExcess": 2, "spanCols": 2, "spanRows": 2, "frames": 6,
    "timedOut": False, "gridCols": 16, "gridRows": 9,
}


def two_darts() -> np.ndarray:
    """A wide dart left of the board and a narrow one in two fragments right of it."""
    mask = np.zeros((120, 200), np.uint8)
    mask[20:60, 20:32] = 255
    mask[20:50, 150:154] = 255
    mask[56:90, 150:154] = 255
    return mask


def fuse(mask, box=None):
    dart_detector.trace = DetectionTrace()
    return dart_detector._fuse_dart_fragments(mask, mask.astype(np.float32), 1.0, box)


def test_without_a_change_box_the_widest_fragment_anchors():
    blob = fuse(two_darts())

    assert blob[:, 0].max() < 100
    assert dart_detector.trace.outside_change_fragments == 0


def test_the_change_box_keeps_the_dart_that_just_landed():
    blob = fuse(two_darts(), (140.0, 10.0, 165.0, 100.0))

    assert blob[:, 0].min() >= 150
    assert len(blob) == 4 * 30 + 4 * 34
    assert dart_detector.trace.outside_change_fragments == 1


def test_a_change_box_with_no_dart_in_it_is_ignored():
    blob = fuse(two_darts(), (60.0, 10.0, 100.0, 100.0))

    assert blob[:, 0].max() < 100
    assert dart_detector.trace.outside_change_fragments == 0


def test_the_region_spans_the_whole_frame_in_grid_cells():
    corners = ChangeRegion(4, 2, 2, 1, 16, 9).corners(160, 90)

    assert corners.reshape(-1, 2).tolist() == [[40, 20], [60, 20], [60, 30], [40, 30]]


@pytest.mark.parametrize(
    ("change", "region"),
    [(None, None), ({"col": 1, "row": 2, "cols": 3, "rows": 4}, ChangeRegion(1, 2, 3, 4, 16, 9))],
)
def test_the_trigger_names_its_change_region(change, region):
    trigger = ThrowTriggerDto.model_validate({**TRIGGER, "change": change})

    assert trigger.change_region() == region
    assert "trigger_change" not in trigger_metrics_of(trigger)
    assert trigger_metrics_of(trigger)["trigger_grid_cols"] == 16.0

