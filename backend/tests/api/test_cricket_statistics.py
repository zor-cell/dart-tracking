import pytest


@pytest.fixture
def alice(register):
    return register("alice")


def cricket(api, **params):
    response = api.get("/statistics/cricket", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def finish(session, game_id):
    session.sql("UPDATE games SET status = 'finished' WHERE id = :id", id=game_id)


def test_cricket_statistics_need_an_account(anon):
    assert anon.get("/statistics/cricket").status_code == 401


def test_cricket_counts_marks_per_round_and_the_visits(alice, session):
    game_id = alice.new_game(
        alice.own_entry()["id"], {"name": "Ben"}, settings={"variant": "cricket"}
    )["id"]
    session.play(game_id, [(20, 3), (19, 3), (0, 0)], [(0, 0)] * 3, [(20, 1), (0, 0), (0, 0)])
    finish(session, game_id)

    found = cricket(alice)

    assert (found["darts"], found["marks"], found["mpr"]) == (6, 7, 3.5)
    assert found["empty"] == 3
    assert found["visits"] == {"6": 1, "1": 1}
    assert (found["bestVisit"], found["bestVisitAt"]) == (6, {"gameId": game_id, "visit": 0})
    assert (found["gamesWithOpponent"], found["wins"]) == (1, 0)
    assert found["fields"] == {"T20": 1, "T19": 1, "0": 3, "20": 1}
    assert found["distance"] is None and found["heatmap"] == []


def test_only_finished_cricket_games_of_the_scoring_picked_count(alice, session):
    for scoring in ("standard", "no_score"):
        settings = {"variant": "cricket", "scoring": scoring}
        game_id = alice.new_game(alice.own_entry()["id"], {"name": "Ben"}, settings=settings)["id"]
        session.play(game_id, [(20, 1)])
        finish(session, game_id)
    unfinished = alice.new_game(
        alice.own_entry()["id"], {"name": "Ben"}, settings={"variant": "cricket"}
    )["id"]
    session.play(unfinished, [(20, 3)])
    x01 = alice.new_game(alice.own_entry()["id"], {"name": "Ben"})["id"]
    session.play(x01, [(20, 3)])
    finish(session, x01)

    assert len(cricket(alice)["games"]) == 2
    assert len(cricket(alice, scoring="no_score")["games"]) == 1
    assert len(cricket(alice, last=1)["games"]) == 1


def test_a_compared_player_is_read_instead(alice, session):
    ben = alice.add_player("Ben")
    game_id = alice.new_game(alice.own_entry()["id"], ben, settings={"variant": "cricket"})["id"]
    session.play(game_id, [(20, 3), (0, 0), (0, 0)], [(19, 1), (19, 1), (0, 0)])
    finish(session, game_id)

    found = cricket(alice, player=ben)

    assert (found["darts"], found["marks"]) == (3, 2)
    assert found["fields"] == {"19": 2, "0": 1}


def test_an_unknown_compared_player_is_not_found(alice):
    response = alice.get(
        "/statistics/cricket", params={"player": "00000000-0000-0000-0000-000000000000"}
    )

    assert response.status_code == 404
