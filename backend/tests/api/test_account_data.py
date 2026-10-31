from datetime import UTC, datetime, timedelta

import pytest

T20, T17, D5, S1, MISS = (20, 3), (17, 3), (5, 2), (1, 1), (0, 0)
WINNING_LEG = ([T20, T20, T20], [T20, T17, D5])

DEFAULTS = {
    "advanceOnPull": True,
    "evaluationEnabled": False,
    "preferredDoubles": [],
}
EVERYTHING_ON = DEFAULTS | {"evaluationEnabled": True}


@pytest.fixture
def alice(register):
    return register("alice")


def test_anonymous_session_runs_on_the_defaults(anon):
    assert anon.get("/settings").json() == DEFAULTS
    assert anon.put("/settings", json=DEFAULTS).status_code == 401


@pytest.mark.parametrize("admin", [False, True])
def test_diagnostics_are_an_admin_switch(alice, session, admin):
    if admin:
        session.make_admin(alice)

    stored = alice.put("/settings", json=EVERYTHING_ON).json()

    assert stored["evaluationEnabled"] is admin
    assert alice.get("/settings").json() == stored


def test_diagnostics_stored_as_admin_are_masked_once_demoted(alice, session):
    session.make_admin(alice)
    alice.put("/settings", json=EVERYTHING_ON)
    session.sql("UPDATE users SET role = 'user' WHERE id = :id", id=alice.id)

    assert alice.get("/settings").json()["evaluationEnabled"] is False


def test_advancing_on_pull_can_be_turned_off(alice):
    alice.put("/settings", json=DEFAULTS | {"advanceOnPull": False})

    assert alice.get("/settings").json()["advanceOnPull"] is False


def test_preferred_doubles(alice):
    stored = alice.put("/settings", json=DEFAULTS | {"preferredDoubles": [16, 25, 16, 8]}).json()
    assert stored["preferredDoubles"] == [16, 25, 8]

    for invalid in ([0], [21], [24]):
        assert alice.put("/settings", json=DEFAULTS | {"preferredDoubles": invalid}).status_code == 422


def test_preferred_doubles_steer_the_checkout(alice, session):
    alice.put("/settings", json=DEFAULTS | {"preferredDoubles": [16]})
    game_id = alice.new_game(alice.own_entry()["id"])["id"]

    session.play(game_id, [T20, T20, T20], [T20, D5])

    assert alice.get(f"/games/{game_id}").json()["checkout"] == ["19", "D16"]


def filter_use(value='"finished"', view="games", key="status"):
    return {"view": view, "key": key, "value": value, "score": 2.5, "lastUsedAt": "2026-10-26T20:00:00Z"}


def test_filter_usage_is_kept_per_account(alice, register):
    bob = register("bob")
    uses = [filter_use(), filter_use("501", key="mode")]

    assert alice.put("/settings/filter-usage", json={"uses": uses}).status_code == 204

    assert alice.get("/settings/filter-usage").json()["uses"] == uses
    assert bob.get("/settings/filter-usage").json()["uses"] == []


def test_filter_usage_and_settings_leave_each_other_alone(alice):
    alice.put("/settings/filter-usage", json={"uses": [filter_use()]})
    assert alice.get("/settings").json() == DEFAULTS

    alice.put("/settings", json=DEFAULTS | {"advanceOnPull": False})
    assert len(alice.get("/settings/filter-usage").json()["uses"]) == 1


def test_filter_usage_is_bounded_and_needs_an_account(alice, anon):
    too_many = [filter_use(f'"{n}"') for n in range(51)]

    assert alice.put("/settings/filter-usage", json={"uses": too_many}).status_code == 422
    assert alice.put("/settings/filter-usage", json={"uses": [filter_use("x" * 129)]}).status_code == 422
    assert anon.get("/settings/filter-usage").status_code == 401


def statistics(api):
    return api.get("/statistics").json()


def own_game(api, **config):
    return api.new_game(api.own_entry()["id"], **config)["id"]


def test_statistics_count_finished_legs(alice, session):
    session.play(own_game(alice), *WINNING_LEG)

    tally = statistics(alice)

    assert (tally["legs"], tally["legsWon"], tally["darts"]) == (1, 1, 6)


def test_statistics_leave_out_what_does_not_count(alice, session, register):
    session.play(own_game(alice), [T20, T20])
    discarded = own_game(alice)
    session.play(discarded, *WINNING_LEG)
    alice.patch(f"/games/{discarded}", json={"status": "discarded"})
    short = own_game(alice)
    session.play(short, [S1] * 3, [S1] * 3, [S1, S1], hand_over=False)
    session.age_game(short, hours=48)
    session.play(alice.new_game(alice.add_player("Bob"))["id"], *WINNING_LEG)

    assert statistics(alice)["legs"] == 0


def test_elimination_counts_against_what_the_others_reset(alice, session):
    game_id = alice.new_game(
        alice.own_entry()["id"], alice.add_player("Bob"), variant="elimination"
    )["id"]
    # Bob draws level at 180 and resets me, so my 121 after it finishes nothing.
    session.play(game_id, [T20] * 3, [T20] * 3, WINNING_LEG[1], [S1] * 3, [S1] * 3)
    session.age_game(game_id, hours=48)

    tally = statistics(alice)

    assert (tally["legs"], tally["legsWon"], tally["darts"]) == (1, 0, 9)
    assert (tally["points"], tally["checkoutAttempts"]) == (304, 0)
    assert alice.get("/statistics", params={"variant": "x01"}).json()["legs"] == 0


def test_abandoned_game_counts_from_nine_own_darts(alice, session):
    game_id = own_game(alice)
    session.play(game_id, [S1] * 3, [S1] * 3, [S1] * 3)
    session.age_game(game_id, hours=48)

    assert statistics(alice)["legs"] == 1


def test_statistics_follow_the_link(alice, register, session):
    bob = register("bob")
    bob_id = alice.add_player("Bob")
    session.play(alice.new_game(bob_id)["id"], *WINNING_LEG)
    assert statistics(bob)["legs"] == 0

    bob.accept(alice.invite(bob_id))
    assert statistics(bob)["legs"] == 1

    bob.delete(f"/players/links/{bob_id}")
    assert statistics(bob)["legs"] == 0


def test_statistics_filter_the_games(alice, session):
    session.play(own_game(alice), *WINNING_LEG)
    single_out = own_game(alice, checkoutMode="single_out")
    session.play(single_out, *WINNING_LEG)
    session.age_game(single_out, hours=48)
    bob = alice.add_player("Bob")
    session.play(alice.new_game(alice.own_entry()["id"], bob)["id"], WINNING_LEG[0], [MISS] * 3, WINNING_LEG[1])

    def legs(**params):
        return alice.get("/statistics", params=params).json()["legs"]

    an_hour_ago = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert legs() == 3
    assert legs(since=an_hour_ago) == 2
    assert legs(until=an_hour_ago) == 1
    assert legs(checkoutMode="single_out") == 1
    assert legs(maxPlayers=1) == 2
    assert legs(minPlayers=2, opponent=bob) == 1
    assert legs(mode=501) == 0


def test_statistics_of_the_last_games_skip_what_does_not_count(alice, session):
    oldest = own_game(alice)
    session.play(oldest, [MISS] * 3, *WINNING_LEG)
    session.age_game(oldest, hours=72)
    middle = own_game(alice)
    session.play(middle, *WINNING_LEG)
    session.age_game(middle, hours=48)
    discarded = own_game(alice)
    session.play(discarded, *WINNING_LEG)
    alice.patch(f"/games/{discarded}", json={"status": "discarded"})
    session.play(own_game(alice), *WINNING_LEG)

    def darts(last):
        return alice.get("/statistics", params={"last": last}).json()["darts"]

    assert (darts(1), darts(2), darts(3)) == (6, 12, 21)
    assert alice.get("/statistics", params={"last": 0}).status_code == 422


def test_best_visit_and_finish_point_into_the_oldest_game_that_threw_them(alice, session):
    oldest = alice.new_game(alice.own_entry()["id"], alice.add_player("Bob"))["id"]
    session.play(oldest, [MISS] * 3, [S1], WINNING_LEG[0], [S1], WINNING_LEG[1])
    session.age_game(oldest, hours=48)
    session.play(own_game(alice), *WINNING_LEG)

    tally = statistics(alice)
    detail = alice.get(f"/games/{oldest}/detail").json()

    assert tally["bestVisitAt"] == {"gameId": oldest, "visit": 2}
    assert tally["highestFinishAt"] == {"gameId": oldest, "visit": 4}
    assert [detail["visits"][i]["points"] for i in (2, 4)] == [180, 121]


def test_accuracy_report_is_for_admins(alice, anon, session):
    assert anon.get("/evaluation/accuracy").status_code == 401
    assert alice.get("/evaluation/accuracy").status_code == 403

    session.make_admin(alice)
    assert alice.get("/evaluation/accuracy").status_code == 200
