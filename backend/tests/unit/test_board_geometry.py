import math

import pytest

from app.api.features.calibration.domain.board_geometry import (
    BULL_RADIUS,
    BULLSEYE_RADIUS,
    DOUBLE_INNER_RADIUS,
    DOUBLE_OUTER_RADIUS,
    SECTOR_ANGLE,
    SECTOR_ORDER,
    TRIPLE_INNER_RADIUS,
    TRIPLE_OUTER_RADIUS,
    Segment,
    distance_to_segment,
    sector_centre_angle,
    segment_at,
    segment_from_label,
)

EPSILON = 1e-6


def polar(radius: float, angle: float) -> tuple[float, float]:
    return radius * math.cos(angle), radius * math.sin(angle)


@pytest.mark.parametrize("index", range(20))
def test_every_ring_of_every_sector(index):
    value = SECTOR_ORDER[index]
    angle = sector_centre_angle(index)
    rings = {
        (BULL_RADIUS + TRIPLE_INNER_RADIUS) / 2: 1,
        (TRIPLE_INNER_RADIUS + TRIPLE_OUTER_RADIUS) / 2: 3,
        (TRIPLE_OUTER_RADIUS + DOUBLE_INNER_RADIUS) / 2: 1,
        (DOUBLE_INNER_RADIUS + DOUBLE_OUTER_RADIUS) / 2: 2,
    }
    for radius, multiplier in rings.items():
        assert segment_at(*polar(radius, angle)) == Segment(value, multiplier)


def test_twenty_is_on_top_and_six_on_the_right():
    assert segment_at(0, 100).value == 20
    assert segment_at(100, 0).value == 6
    assert segment_at(0, -100).value == 3
    assert segment_at(-100, 0).value == 11


@pytest.mark.parametrize(
    ("radius", "label"),
    [
        (0, "BULL"),
        (BULLSEYE_RADIUS, "BULL"),
        (BULLSEYE_RADIUS + EPSILON, "25"),
        (BULL_RADIUS, "25"),
        (BULL_RADIUS + EPSILON, "S20"),
        (TRIPLE_INNER_RADIUS, "T20"),
        (TRIPLE_OUTER_RADIUS, "T20"),
        (TRIPLE_OUTER_RADIUS + EPSILON, "S20"),
        (DOUBLE_INNER_RADIUS, "D20"),
        (DOUBLE_OUTER_RADIUS, "D20"),
        (DOUBLE_OUTER_RADIUS + EPSILON, "MISS"),
    ],
)
def test_ring_edges_go_to_the_inner_field(radius, label):
    assert segment_at(0, radius).label == label


def test_wire_between_twenty_and_one():
    wire = math.pi / 2 - SECTOR_ANGLE / 2
    assert segment_at(*polar(50, wire + 0.001)).value == 20
    assert segment_at(*polar(50, wire - 0.001)).value == 1


@pytest.mark.parametrize(
    "segment",
    [Segment(0, 0), Segment(25, 1), Segment(25, 2)]
    + [Segment(value, multiplier) for value in SECTOR_ORDER for multiplier in (1, 2, 3)],
)
def test_label_round_trip(segment):
    assert segment_from_label(segment.label) == segment
    assert segment_from_label(f" {segment.label.lower()} ") == segment


@pytest.mark.parametrize("label", ["", "S", "S21", "D0", "X5", "T2O", "50", "BULLS"])
def test_unknown_labels(label):
    assert segment_from_label(label) is None


def test_distance_is_zero_inside_the_segment():
    assert distance_to_segment(0, 100, Segment(20, 3)) == 0
    assert distance_to_segment(0, 0, Segment(25, 2)) == 0
    assert distance_to_segment(0, 200, Segment(0, 0)) == 0


def test_distance_across_a_wire_and_across_the_board():
    wire = math.pi / 2 - SECTOR_ANGLE / 2
    just_in_one = polar(50, wire - 0.01)
    assert 0 < distance_to_segment(*just_in_one, Segment(20, 1)) < 1

    assert distance_to_segment(0, 0, Segment(20, 2)) == pytest.approx(DOUBLE_INNER_RADIUS)
    assert distance_to_segment(0, 0, Segment(0, 0)) == pytest.approx(DOUBLE_OUTER_RADIUS)
    assert distance_to_segment(0, 50, Segment(25, 1)) == pytest.approx(50 - BULL_RADIUS)
