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
    assert found["variants"] == {"x01": 1, "around_the_clock": 1}
    assert (found["misses"], found["located"]) == (1, 1)
    assert found["fields"] == {"T20": 1, "20": 1, "0": 1, "1": 1, "D2": 1, "50": 1}
    assert found["locatedFields"] == {"T20": 1}
    assert found["rings"] == {"triple": 1, "single": 2, "miss": 1, "double": 2}
    assert found["weeks"] == [{"week": "2026-11-02", "darts": 6}]
    assert found["longestStreak"] == 2
    assert found["busiestDay"] == {"day": "2026-11-02", "darts": 3}
    assert (found["gamesWithOpponent"], found["wins"], found["opponents"]) == (1, 0, 1)
    assert found["rival"] | {"name": "Ben", "games": 1} == found["rival"]


def test_a_won_duel_and_the_weeks_between(alice, session):
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

    assert (found["wins"], found["rival"]["wins"], found["rival"]["losses"]) == (1, 1, 0)
    assert [week["darts"] for week in found["weeks"]] == [2, 0, 3]
    assert found["longestStreak"] == 1


def test_unfinished_games_and_other_seats_stay_out(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], {"name": "Ben"}, settings=X01)["id"]
    session.play(game_id, [(20, 1)], [(19, 1), (19, 1), (19, 1)])

    assert overall(alice)["games"] == 0
    finish(session, game_id)
    found = overall(alice)
    assert (found["games"], found["darts"]) == (1, 3)
    assert overall(alice, players="solo")["games"] == 0
