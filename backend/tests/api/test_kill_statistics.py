import pytest

MISS = (0, 0)


@pytest.fixture
def alice(register):
    return register("alice")


def kills(api, **params):
    response = api.get("/statistics/kills", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def finish(session, game_id):
    session.sql("UPDATE games SET status = 'finished' WHERE id = :id", id=game_id)


def test_kill_statistics_need_an_account(anon):
    assert anon.get("/statistics/kills").status_code == 401


def test_killer_counts_the_lives_taken_and_lost(alice, session):
    game = alice.new_game(
        alice.own_entry()["id"], {"name": "Ben"}, settings={"variant": "killer", "lives": 2}
    )
    own, ben = (player["number"] for player in game["standing"]["players"])
    session.play(game["id"], [(own, 2), (ben, 2), (ben, 2)])
    finish(session, game["id"])

    found = kills(alice, variant="killer")

    assert (found["kills"], found["losses"], found["wins"], found["darts"]) == (2, 0, 1, 3)
    assert found["most"]["gameId"] == game["id"]
    assert [(entry["kills"], entry["won"]) for entry in found["games"]] == [(2, True)]


def test_elimination_counts_the_resets_either_way(alice, session):
    settings = {"variant": "elimination", "mode": 301}
    game_id = alice.new_game(alice.own_entry()["id"], {"name": "Ben"}, settings=settings)["id"]
    session.play(
        game_id,
        [(20, 1), MISS, MISS],
        [(20, 1), MISS, MISS],
        [(20, 1), MISS, MISS],
    )
    finish(session, game_id)

    found = kills(alice, variant="elimination")

    assert (found["kills"], found["losses"], found["wins"], found["darts"]) == (1, 1, 0, 6)


def test_only_finished_games_of_the_own_seat_count(alice, session):
    game = alice.new_game(
        alice.own_entry()["id"], {"name": "Ben"}, settings={"variant": "killer", "lives": 1}
    )
    own, ben = (player["number"] for player in game["standing"]["players"])
    session.play(game["id"], [MISS, MISS, MISS])

    assert kills(alice)["games"] == []
    session.play(game["id"], [(ben, 2), (own, 2)])
    found = kills(alice)
    assert (found["kills"], found["losses"], found["wins"], found["most"]) == (0, 1, 0, None)
