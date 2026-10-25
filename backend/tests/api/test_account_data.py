import pytest

T20, T17, D5, S1, MISS = (20, 3), (17, 3), (5, 2), (1, 1), (0, 0)
WINNING_LEG = ([T20, T20, T20], [T20, T17, D5])

DEFAULTS = {
    "confirmThrowEnabled": True,
    "evaluationEnabled": False,
    "preferredDoubles": [],
}
EVERYTHING_ON = {key: True for key in DEFAULTS if key != "preferredDoubles"} | {"preferredDoubles": []}


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


def test_preferred_doubles(alice):
    stored = alice.put("/settings", json=DEFAULTS | {"preferredDoubles": [16, 25, 16, 8]}).json()
    assert stored["preferredDoubles"] == [16, 25, 8]

    for invalid in ([0], [21], [24]):
        assert alice.put("/settings", json=DEFAULTS | {"preferredDoubles": invalid}).status_code == 422


def test_preferred_doubles_steer_the_checkout(alice, session):
    alice.put("/settings", json=DEFAULTS | {"preferredDoubles": [16]})
    game_id = alice.new_game(alice.own_entry()["id"])["id"]

    session.play(game_id, [T20, T20, T20], [T20, S1])

    assert alice.get(f"/games/{game_id}").json()["checkout"] == ["D14", "D16"]


def statistics(api):
    return api.get("/statistics").json()


def own_game(api, **config):
    return api.new_game(api.own_entry()["id"], **config)["id"]


def test_statistics_count_finished_legs(alice, session):
    session.play(own_game(alice), *WINNING_LEG)

    tally = statistics(alice)

    assert (tally["legs"], tally["legsWon"], tally["darts"]) == (1, 1, 6)


def test_statistics_leave_out_what_does_not_count(alice, session, register):
    session.play(own_game(alice, variant="elimination"), *WINNING_LEG)
    session.play(own_game(alice), [T20, T20])
    discarded = own_game(alice)
    session.play(discarded, *WINNING_LEG)
    alice.patch(f"/games/{discarded}", json={"status": "discarded"})
    short = own_game(alice)
    session.play(short, [S1] * 3, [S1] * 3, [S1, S1], hand_over=False)
    session.age_game(short, hours=48)
    session.play(alice.new_game(alice.add_player("Bob"))["id"], *WINNING_LEG)

    assert statistics(alice)["legs"] == 0


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


def test_accuracy_report_is_for_admins(alice, anon, session):
    assert anon.get("/evaluation/accuracy").status_code == 401
    assert alice.get("/evaluation/accuracy").status_code == 403

    session.make_admin(alice)
    assert alice.get("/evaluation/accuracy").status_code == 200
