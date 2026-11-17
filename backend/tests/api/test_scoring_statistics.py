import pytest

FREE = {"variant": "training", "goal": "free"}
RANDOM = {"variant": "training", "goal": "random"}
T20 = (20, 3)
MISS = (0, 0)


@pytest.fixture
def alice(register):
    return register("alice")


def training(api, session, *visits, settings=FREE, end=True):
    game_id = api.new_game(api.own_entry()["id"], settings=settings)["id"]
    session.play(game_id, *visits, hand_over=False)
    if end:
        session.sql("UPDATE games SET status = 'finished' WHERE id = :id", id=game_id)
    return game_id


def scoring(api, **params):
    response = api.get("/statistics/scoring", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_scoring_statistics_need_an_account(anon):
    assert anon.get("/statistics/scoring").status_code == 401


def test_a_free_training_counts_its_points_like_x01(alice, session):
    game_id = training(alice, session, [T20, T20, T20], [T20, (20, 1), MISS], [(1, 1), MISS, MISS])

    found = scoring(alice, variant="training")

    assert (found["darts"], found["average"], found["bestVisit"]) == (9, 87.0, 180)
    assert found["bestVisitAt"] == {"gameId": game_id, "visit": 0}
    bands = [found[key] for key in ("visits180", "visits140Plus", "visits100Plus", "visits60Plus")]
    assert bands == [1, 1, 1, 2]
    assert found["visitScores"] == {"180": 1, "80": 1, "1": 1}
    assert [(game["gameId"], game["darts"], game["average"]) for game in found["games"]] == [
        (game_id, 9, 87.0)
    ]


def test_trainings_with_a_target_and_unfinished_ones_stay_out(alice, session):
    training(alice, session, [T20, T20, T20], end=False)
    training(alice, session, [T20, T20, T20], settings=RANDOM)

    assert scoring(alice)["darts"] == 0


def test_a_goal_or_ring_that_leaves_out_free_trainings_empties_it(alice, session):
    training(alice, session, [T20, MISS, MISS])

    assert scoring(alice, trainingGoal="free")["darts"] == 3
    assert scoring(alice, trainingGoal="random")["darts"] == 0
    assert scoring(alice, trainingRing="double")["darts"] == 0
    assert scoring(alice, variant="x01")["darts"] == 0


def test_the_last_games_count_trainings_of_any_goal(alice, session):
    old = training(alice, session, [T20, MISS, MISS])
    session.age_game(old, hours=2)
    training(alice, session, [(20, 1), MISS, MISS], settings=RANDOM)

    assert scoring(alice, last=1)["darts"] == 0
    assert scoring(alice, last=2)["darts"] == 3


def test_the_targets_count_a_free_training_among_the_last_games(alice, session):
    old = training(alice, session, [(20, 1), MISS, MISS], settings=RANDOM)
    session.age_game(old, hours=2)
    training(alice, session, [T20, MISS, MISS])

    found = alice.get("/statistics/targets", params={"variant": "training", "last": 1}).json()

    assert found["darts"] == 0


def test_a_compared_player_is_read_instead(alice, session):
    ben = alice.add_player("Ben")
    game_id = alice.new_game(alice.own_entry()["id"], ben, settings=FREE)["id"]
    session.play(game_id, [T20, MISS, MISS], [(20, 1), MISS, MISS], hand_over=False)
    session.sql("UPDATE games SET status = 'finished' WHERE id = :id", id=game_id)

    assert scoring(alice)["bestVisit"] == 60
    assert scoring(alice, player=ben)["bestVisit"] == 20
    assert scoring(alice, player=ben)["bestVisitAt"]["visit"] == 1
