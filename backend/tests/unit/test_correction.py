import math

import pytest

from app.api.features.calibration.domain.board_geometry import (
    BULLSEYE_RADIUS,
    DOUBLE_OUTER_RADIUS,
    SECTOR_ANGLE,
    Segment,
    distance_to_segment,
    point_inside,
    sector_centre_angle,
)
from app.api.features.game.domain.correction import SNAP_INSET_MM, corrected
from app.api.features.game.domain.dart import Dart
from tests.unit.darts import dart, new_game

D20, S20 = Segment(20, 2), Segment(20, 1)


def polar(radius: float, angle: float) -> tuple[float, float]:
    return radius * math.cos(angle), radius * math.sin(angle)


@pytest.mark.parametrize(
    ("point", "segment"),
    [
        ((0.0, DOUBLE_OUTER_RADIUS + 1), D20),
        (polar(140, sector_centre_angle(1) + 0.3 * SECTOR_ANGLE), S20),
        ((0.0, BULLSEYE_RADIUS + 1), Segment(25, 2)),
        ((0.0, 3.0), Segment(25, 1)),
    ],
)
def test_the_point_moves_just_inside_the_nearest_edge(point, segment):
    inside = point_inside(*point, segment, SNAP_INSET_MM)

    assert distance_to_segment(*inside, segment) == 0
    assert math.dist(point, inside) <= distance_to_segment(*point, segment) + SNAP_INSET_MM + 0.01


def test_a_point_already_inside_stays_where_it_is():
    point = (0.0, 165.0)

    assert point_inside(*point, D20, SNAP_INSET_MM) == pytest.approx(point)


def test_a_tip_just_outside_the_booked_field_is_kept_inside_it():
    tracked = Dart(value=20, multiplier=1, position=(0.0, 158.5))

    fixed = corrected(tracked, Dart(value=20, multiplier=2))

    assert fixed.snapped
    assert fixed.position == pytest.approx((0.0, 160.5))


def test_a_tip_just_outside_the_board_is_kept_in_the_double_it_was_entered_as():
    tracked = Dart(value=0, multiplier=0, position=(0.0, DOUBLE_OUTER_RADIUS + 1.5))

    fixed = corrected(tracked, Dart(value=20, multiplier=2))

    assert fixed.snapped
    assert distance_to_segment(*fixed.position, D20) == 0


@pytest.mark.parametrize(
    ("tracked", "entered"),
    [
        (Dart(value=20, multiplier=1, position=(0.0, 150.0)), Dart(value=20, multiplier=2)),
        (Dart(value=20, multiplier=1, position=(0.0, 165.0)), Dart(value=0, multiplier=0)),
        (Dart(value=20, multiplier=2, position=(0.0, DOUBLE_OUTER_RADIUS - 1)), Dart(value=0, multiplier=0)),
        (Dart(value=20, multiplier=1), Dart(value=20, multiplier=2)),
        (Dart(value=20, multiplier=2, position=(0.0, 160.5), snapped=True), Dart(value=20, multiplier=1)),
    ],
)
def test_a_far_tip_a_miss_no_tip_or_a_moved_tip_leaves_the_correction_without_one(tracked, entered):
    assert corrected(tracked, entered) == entered


def test_replacing_a_dart_on_the_wire_keeps_its_tip():
    wire = sector_centre_angle(0) - SECTOR_ANGLE / 2
    game = new_game(1)
    game.register_dart(Dart(value=1, multiplier=1, position=polar(140, wire - 0.005)))
    game.register_dart(dart("0"))

    game.replace_dart(0, Dart(value=20, multiplier=1))

    replaced = game.current_turn.darts[0]
    assert (replaced.value, replaced.snapped) == (20, True)
    assert distance_to_segment(*replaced.position, S20) == 0
