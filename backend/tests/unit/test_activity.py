from datetime import date

from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.statistics.domain.activity import ActivityTally, ActivityUnit, activity

X01 = GameVariant.X01
CRICKET = GameVariant.CRICKET


def test_a_month_is_shown_day_by_day_with_the_empty_days():
    played = {
        (date(2026, 11, 2), X01): ActivityTally(30, 1, 600),
        (date(2026, 11, 4), CRICKET): ActivityTally(45, 2, 900),
    }

    found = activity(played, date(2026, 11, 1), date(2026, 12, 1))

    assert found.unit is ActivityUnit.DAY
    assert len(found.buckets) == 31
    assert found.buckets[0].start == date(2026, 11, 1)
    assert found.buckets[-1].start == date(2026, 12, 1)
    assert found.buckets[1].variants == {X01: ActivityTally(30, 1, 600)}
    assert found.buckets[2].variants == {}
    assert found.buckets[3].variants == {CRICKET: ActivityTally(45, 2, 900)}


def test_past_a_month_the_weeks_start_on_monday():
    played = {
        (date(2026, 11, 4), X01): ActivityTally(10, 1, 60),
        (date(2026, 11, 8), X01): ActivityTally(20, 2, 120),
        (date(2026, 11, 9), X01): ActivityTally(5, 1, 30),
    }

    found = activity(played, date(2026, 11, 4), date(2026, 12, 5))

    assert found.unit is ActivityUnit.WEEK
    assert [bucket.start for bucket in found.buckets] == [
        date(2026, 11, 2),
        date(2026, 11, 9),
        date(2026, 11, 16),
        date(2026, 11, 23),
        date(2026, 11, 30),
    ]
    assert found.buckets[0].variants == {X01: ActivityTally(30, 3, 180)}
    assert found.buckets[1].variants == {X01: ActivityTally(5, 1, 30)}


def test_past_four_months_the_buckets_are_months_across_the_new_year():
    played = {
        (date(2026, 10, 31), X01): ActivityTally(10, 1, 60),
        (date(2027, 1, 1), X01): ActivityTally(20, 1, 60),
        (date(2027, 1, 31), CRICKET): ActivityTally(5, 1, 60),
    }

    found = activity(played, date(2026, 10, 15), date(2027, 2, 20))

    assert found.unit is ActivityUnit.MONTH
    assert [bucket.start for bucket in found.buckets] == [
        date(2026, 10, 1),
        date(2026, 11, 1),
        date(2026, 12, 1),
        date(2027, 1, 1),
        date(2027, 2, 1),
    ]
    assert found.buckets[3].variants == {
        X01: ActivityTally(20, 1, 60),
        CRICKET: ActivityTally(5, 1, 60),
    }


def test_the_unit_changes_right_after_its_longest_span():
    assert activity({}, date(2026, 1, 1), date(2026, 1, 31)).unit is ActivityUnit.DAY
    assert activity({}, date(2026, 1, 1), date(2026, 2, 1)).unit is ActivityUnit.WEEK
    assert activity({}, date(2026, 1, 1), date(2026, 5, 2)).unit is ActivityUnit.WEEK
    assert activity({}, date(2026, 1, 1), date(2026, 5, 3)).unit is ActivityUnit.MONTH


def test_days_outside_the_span_stay_out():
    played = {(date(2026, 10, 1), X01): ActivityTally(10, 1, 60)}

    found = activity(played, date(2026, 11, 1), date(2026, 11, 7))

    assert all(bucket.variants == {} for bucket in found.buckets)
