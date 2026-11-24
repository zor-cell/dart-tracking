from datetime import UTC, datetime, timedelta

import pytest

from tests.api.support import X01

MISS = (0, 0)


@pytest.fixture
def alice(register):
    return register("alice")


def overall(api, **params):
    response = api.get("/statistics/all", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def finish(session, game_id, day="2026-11-02 10:00", minutes=20):
    """Ends the game, set up at `day` (UTC) and finished `minutes` later."""
    start = datetime.strptime(day, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
    session.sql(
        "UPDATE games SET status = 'finished', created_at = :day,"
        " finished_at = :end WHERE id = :id",
        id=game_id,
        day=start,
        end=start + timedelta(minutes=minutes),
    )


def test_overall_statistics_need_an_account(anon):
    assert anon.get("/statistics/all").status_code == 401


def test_every_kind_of_game_adds_up(alice, session):
    duel = alice.new_game(alice.own_entry()["id"], {"name": "Ben"}, settings=X01)["id"]
    session.play(duel, [(20, 3), (20, 1), MISS], [(5, 1), (1, 1), (20, 2)])
    finish(session, duel, "2026-11-02 10:00")
    clock = alice.new_game(alice.own_entry()["id"], settings={"variant": "around_the_clock"})["id"]
    session.play(clock, [(1, 1), (2, 2), (25, 2)])
    finish(session, clock, "2026-11-03 18:00", minutes=10)
    session.sql(
        "UPDATE game_darts SET pos_x = 0, pos_y = 103 WHERE game_id = :id AND dart_index = 0",
        id=duel,
    )

    found = overall(alice)

    assert (found["games"], found["darts"], found["seconds"]) == (2, 6, 1800)
    assert (found["misses"], found["located"]) == (1, 1)
    assert found["fields"] == {"T20": 1, "20": 1, "0": 1, "1": 1, "D2": 1, "50": 1}
    assert found["locatedFields"] == {"T20": 1}
    assert found["rings"] == {"triple": 1, "single": 2, "miss": 1, "double": 2}
    assert found["activity"] == {
        "unit": "day",
        "buckets": [
            {"start": "2026-11-02", "variants": {"x01": {"darts": 3, "games": 1, "seconds": 1200}}},
            {
                "start": "2026-11-03",
                "variants": {"around_the_clock": {"darts": 3, "games": 1, "seconds": 600}},
            },
        ],
    }
    assert (found["gamesWithOpponent"], found["wins"]) == (1, 0)
    assert "rival" not in found and "opponents" not in found


def test_a_won_duel_and_the_days_between(alice, session):
    game = alice.new_game(
        alice.own_entry()["id"], {"name": "Ben"}, settings={"variant": "killer", "lives": 1}
    )
    own, ben = (player["number"] for player in game["standing"]["players"])
    session.play(game["id"], [(own, 2), (ben, 2)])
    finish(session, game["id"], "2026-10-20 10:00")
    solo = alice.new_game(alice.own_entry()["id"], settings={"variant": "around_the_clock"})["id"]
    session.play(solo, [MISS])
    finish(session, solo, "2026-11-04 10:00")

    found = overall(alice)

    assert (found["gamesWithOpponent"], found["wins"]) == (1, 1)
    buckets = found["activity"]["buckets"]
    assert (found["activity"]["unit"], len(buckets)) == ("day", 16)
    assert buckets[0]["variants"]["killer"]["darts"] == 2
    assert all(bucket["variants"] == {} for bucket in buckets[1:-1])
    assert buckets[-1]["variants"]["around_the_clock"]["darts"] == 3


def test_the_last_games_are_the_newest_the_filters_let_through(alice, session):
    clock = {"variant": "around_the_clock"}
    for day, settings, visits in (
        ("2026-11-02 10:00", clock, 1),
        ("2026-11-03 10:00", clock, 2),
        ("2026-11-04 10:00", X01, 3),
    ):
        game_id = alice.new_game(alice.own_entry()["id"], settings=settings)["id"]
        session.play(game_id, *[[MISS] * 3] * visits)
        finish(session, game_id, day)

    assert overall(alice, last=2)["darts"] == 15
    assert overall(alice, last=2, variant="around_the_clock")["darts"] == 9
    assert overall(alice, last=1, variant="around_the_clock")["activity"]["buckets"] == [
        {
            "start": "2026-11-03",
            "variants": {"around_the_clock": {"darts": 6, "games": 1, "seconds": 1200}},
        }
    ]


def test_unfinished_games_and_other_seats_stay_out(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], {"name": "Ben"}, settings=X01)["id"]
    session.play(game_id, [(20, 1)], [(19, 1), (19, 1), (19, 1)])

    assert overall(alice)["games"] == 0
    finish(session, game_id)
    found = overall(alice)
    assert (found["games"], found["darts"]) == (1, 3)
    assert overall(alice, players="solo")["games"] == 0


def test_a_picked_range_bounds_the_activity_from_local_midnight(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], settings=X01)["id"]
    session.play(game_id, [MISS] * 3)
    finish(session, game_id, "2026-03-10 18:00")

    activity = overall(
        alice,
        since="2026-02-28T23:00:00.000Z",
        until="2026-03-31T22:00:00.000Z",
        tz="Europe/Vienna",
    )["activity"]

    starts = [bucket["start"] for bucket in activity["buckets"]]
    assert (activity["unit"], starts[0], starts[-1]) == ("day", "2026-03-01", "2026-03-31")
    assert activity["buckets"][9]["variants"]["x01"]["darts"] == 3


def test_a_game_just_after_local_midnight_counts_on_that_local_day(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], settings=X01)["id"]
    session.play(game_id, [MISS] * 3)
    finish(session, game_id, "2026-02-28 23:30")
    week = {"since": "2026-02-28T23:00:00.000Z", "until": "2026-03-07T23:00:00.000Z"}

    activity = overall(alice, **week, tz="Europe/Vienna")["activity"]

    starts = [bucket["start"] for bucket in activity["buckets"]]
    assert (activity["unit"], starts[0], starts[-1]) == ("day", "2026-03-01", "2026-03-07")
    assert activity["buckets"][0]["variants"]["x01"]["darts"] == 3


def test_summer_time_moves_the_day_by_two_hours(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], settings=X01)["id"]
    session.play(game_id, [MISS] * 3)
    finish(session, game_id, "2026-07-14 22:30")

    local = overall(alice, tz="Europe/Vienna")["activity"]["buckets"]
    utc = overall(alice)["activity"]["buckets"]

    assert [bucket["start"] for bucket in local] == ["2026-07-15"]
    assert [bucket["start"] for bucket in utc] == ["2026-07-14"]


@pytest.mark.parametrize("zone", ["Mars/Olympus", "../etc", "Europe", ""])
def test_an_unknown_time_zone_is_refused(alice, zone):
    assert alice.get("/statistics/all", params={"tz": zone}).status_code == 422


def test_a_longer_range_counts_in_weeks_and_months(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], settings=X01)["id"]
    session.play(game_id, [MISS] * 3)
    finish(session, game_id, "2026-03-10 18:00")

    weeks = overall(alice, since="2026-02-01T00:00:00Z", until="2026-04-01T00:00:00Z")
    months = overall(alice, since="2025-12-01T00:00:00Z", until="2026-06-01T00:00:00Z")

    assert weeks["activity"]["unit"] == "week"
    assert weeks["activity"]["buckets"][0]["start"] == "2026-01-26"
    assert months["activity"]["unit"] == "month"
    assert [bucket["start"] for bucket in months["activity"]["buckets"]] == [
        "2025-12-01",
        "2026-01-01",
        "2026-02-01",
        "2026-03-01",
        "2026-04-01",
        "2026-05-01",
    ]


def test_without_a_game_there_is_no_activity(alice):
    assert overall(alice)["activity"] is None
