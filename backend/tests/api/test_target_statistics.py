import pytest

CLOCK = {"variant": "around_the_clock"}
# 1 to 20 in visits of three, then the bull.
ROUND = [[(n, 1) for n in range(start, min(start + 3, 21))] for start in range(1, 21, 3)] + [[(25, 1)]]
MISS = (0, 0)
D20 = {"variant": "training", "goal": "fields", "fields": [{"value": 20, "multiplier": 2}]}


@pytest.fixture
def alice(register):
    return register("alice")


def clock_game(api, session, *visits, settings=CLOCK, end=False):
    game_id = api.new_game(api.own_entry()["id"], settings=settings)["id"]
    session.play(game_id, *visits, hand_over=False)
    if end:
        session.sql("UPDATE games SET status = 'finished' WHERE id = :id", id=game_id)
    return game_id


def targets(api, **params):
    response = api.get("/statistics/targets", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def locate(session, game_id, dart_index, x, y):
    session.sql(
        "UPDATE game_darts SET pos_x = :x, pos_y = :y"
        " WHERE game_id = :id AND turn_index = 0 AND dart_index = :dart",
        x=x,
        y=y,
        id=game_id,
        dart=dart_index,
    )


def test_target_statistics_need_an_account(anon):
    assert anon.get("/statistics/targets").status_code == 401


def test_a_round_of_the_clock_counts_every_dart_at_its_target(alice, session):
    opening = [[MISS, (1, 1), (5, 1)], [MISS, MISS, (2, 1)], [(3, 1)]]
    game_id = clock_game(alice, session, *opening, *ROUND[1:])

    found = targets(alice, variant="around_the_clock")

    assert (found["darts"], found["hits"]) == (28, 21)
    by_field = {(entry["value"], entry["multiplier"]): entry for entry in found["fields"]}
    assert (by_field[1, None]["darts"], by_field[1, None]["hits"]) == (2, 1)
    assert (by_field[2, None]["darts"], by_field[2, None]["hits"]) == (4, 1)
    assert [entry["value"] for entry in found["fields"]] == [*range(1, 21), 25]
    assert found["dartsToFinish"] == 28
    assert found["best"]["gameId"] == game_id
    assert [(game["through"], game["darts"]) for game in found["games"]] == [(True, 28)]


def test_unfinished_and_hidden_games_and_other_variants_stay_out(alice, session):
    clock_game(alice, session, [(1, 1)])
    hidden = clock_game(alice, session, [(1, 1)], end=True)
    alice.patch(f"/games/{hidden}", json={"status": "discarded"})
    training = {"variant": "training", "goal": "fields", "fields": [{"value": 19, "multiplier": 3}]}
    clock_game(alice, session, [(19, 3), (19, 1)], settings=training, end=True)

    assert targets(alice, variant="around_the_clock")["darts"] == 0
    found = targets(alice)
    assert (found["darts"], found["hits"], found["dartsToFinish"]) == (2, 1, None)
    assert found["fields"][0] | {"value": 19, "multiplier": 3} == found["fields"][0]


def test_only_the_own_seat_counts(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], {"name": "Ben"}, settings=CLOCK)["id"]
    session.play(game_id, [(1, 1), MISS, MISS], [MISS, MISS, MISS])
    session.sql("UPDATE games SET status = 'finished' WHERE id = :id", id=game_id)

    found = targets(alice)

    assert (found["darts"], found["hits"]) == (3, 1)


def test_the_settings_of_a_variant_filter_its_games(alice, session):
    clock_game(alice, session, [(1, 2)], settings=CLOCK | {"zone": "double"}, end=True)
    clock_game(alice, session, [(1, 1), (2, 1)], end=True)

    assert targets(alice, clockZone="double")["darts"] == 1
    assert targets(alice, clockZone="any")["darts"] == 2
    assert targets(alice, clockZone=["any", "double"])["darts"] == 3
    assert targets(alice, trainingGoal="random")["darts"] == 0
    assert alice.get("/statistics/targets", params={"clockZone": "outer"}).status_code == 422


def test_the_last_games_keep_the_newest_with_aimed_darts(alice, session):
    old = clock_game(alice, session, [(1, 1)], end=True)
    session.age_game(old, hours=2)
    clock_game(alice, session, [MISS, MISS], end=True)

    assert targets(alice, last=1)["darts"] == 2
    assert [game["darts"] for game in targets(alice)["games"]] == [1, 2]


def test_located_darts_measure_the_distance_to_the_target(alice, session):
    game_id = clock_game(alice, session, [(20, 1), (20, 1), MISS], settings=D20, end=True)
    locate(session, game_id, 0, 0.0, 150.0)
    locate(session, game_id, 1, 0.0, 165.0)

    found = targets(alice)

    assert (found["located"], found["distance"]) == (2, 5.0)


def test_x01_counts_the_darts_at_a_finishing_double(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"])["id"]
    session.play(game_id, [(20, 3)] * 3, [(20, 3), (15, 3), MISS], [(8, 1), (4, 2)], hand_over=False)

    fields = targets(alice, variant="x01")["fields"]

    assert [entry["value"] for entry in fields] == [4, 8]
    assert (fields[1]["darts"], fields[1]["hits"]) == (2, 0)


def test_a_compared_player_is_read_instead(alice, session):
    ben = alice.add_player("Ben")
    game_id = alice.new_game(alice.own_entry()["id"], ben, settings=CLOCK)["id"]
    session.play(game_id, [(1, 1), MISS, MISS], [MISS, MISS, MISS])
    session.sql("UPDATE games SET status = 'finished' WHERE id = :id", id=game_id)

    assert targets(alice, player=ben)["hits"] == 0
    assert targets(alice, player=ben)["darts"] == 3


def test_each_target_carries_what_its_darts_hit_and_where_they_landed(alice, session):
    game_id = clock_game(alice, session, [(20, 2), (5, 1), MISS], settings=D20, end=True)
    locate(session, game_id, 0, 0, 165)
    locate(session, game_id, 1, -30, 150)

    entry = targets(alice)["fields"][0]

    assert (entry["value"], entry["multiplier"]) == (20, 2)
    assert entry["fields"] == {"D20": 1, "5": 1, "0": 1}
    assert (entry["located"], entry["locatedHits"]) == (2, 1)
    assert sorted(entry["cells"]) == [[-30, 150, 1], [0, 164, 1]]
