import pytest

from tests.api.test_socket import room  # noqa: F401

T19 = {"value": 19, "multiplier": 3}
D16 = {"value": 16, "multiplier": 2}


def create(api, *names, **training):
    players = [{"name": name} for name in names]
    return api.post("/games", json={"players": players, "variant": "training", "training": training})


def test_a_training_starts_free_and_carries_its_own_standing(anon):
    response = api_game = create(anon, "Ann")

    assert response.status_code == 201, response.text
    game = api_game.json()
    assert game["mode"] is None
    assert game["ended"] is False
    assert game["training"]["goal"] == "free"
    assert game["training"]["players"][0]["target"] is None
    assert anon.get(f"/games/{game['id']}").json() == game


def test_own_fields_are_kept_and_come_back_with_the_game(anon):
    game = create(anon, "Ann", goal="fields", fields=[T19, D16]).json()

    assert game["training"]["fields"] == [T19, D16]
    assert game["training"]["players"][0]["target"] == T19
    assert anon.get(f"/games/{game['id']}").json()["training"] == game["training"]


@pytest.mark.parametrize(
    "training",
    [
        {"goal": "fields"},
        {"goal": "fields", "fields": [{"value": 25, "multiplier": 3}]},
        {"goal": "fields", "fields": [{"value": 21, "multiplier": 1}]},
        {"goal": "fields", "fields": [T19, T19]},
        {"goal": "random", "repeats": 0},
        {"goal": "random", "ring": "outer"},
    ],
)
def test_impossible_training_settings_are_refused(anon, training):
    assert create(anon, "Ann", **training).status_code == 422


def test_hits_are_counted_and_the_next_field_is_called(room, anon):  # noqa: F811
    game = create(anon, "Ann", goal="fields", fields=[T19, D16]).json()
    with room(game["id"]) as device:
        device.throw(19, 3)
        device.throw(19, 1)
        device.send("next_player")
        state = device.next("game_state")
        while len(state["turns"]) == 1:
            state = device.next("game_state")
        call = device.next("turn_announcement")

    player = state["training"]["players"][0]
    assert (player["hits"], player["darts"], player["lastVisit"]) == (1, 3, 1)
    assert player["target"] == D16
    assert player["tallies"] == [{**T19, "darts": 1, "hits": 1}, {**D16, "darts": 2, "hits": 0}]
    assert len(call["clips"]) == 1


def test_ending_finishes_the_game_without_a_winner_and_it_can_be_reopened(room, alice, session):  # noqa: F811
    game_id = alice.new_game(alice.own_entry()["id"], variant="training")["id"]
    with room(game_id) as device:
        device.throw(20, 3)
        device.send("set_ended", ended=True)
        state = device.next("game_state")
        while not state["ended"]:
            state = device.next("game_state")

        assert state["winnerId"] is None
        assert state["dartsRemaining"] == 0
        listed = alice.get("/games").json()["items"][0]
        assert (listed["status"], listed["winnerIndex"]) == ("finished", None)
        assert alice.get(f"/games/{game_id}").json()["ended"] is True

        device.send("set_ended", ended=False)
        state = device.next("game_state")
        while state["ended"]:
            state = device.next("game_state")

    assert alice.get("/games").json()["items"][0]["status"] == "active"


def test_a_game_with_a_winner_ignores_the_end_command(room, anon):  # noqa: F811
    game = anon.post("/games", json={"players": [{"name": "Ann"}], "mode": 301}).json()
    with room(game["id"]) as device:
        device.send("set_ended", ended=True)
        device.throw(20, 1)
        state = device.next("game_state")

    assert state["ended"] is False


def test_the_most_played_training_is_offered_as_quick_start(alice, session):
    for _ in range(2):
        game_id = alice.new_game(
            alice.own_entry()["id"], variant="training", training={"goal": "random", "ring": "triple"}
        )["id"]
        session.play(game_id, [(20, 3)])

    quick = alice.get("/games/quick-start").json()

    assert quick["variant"] == "training"
    assert quick["training"] == {
        "goal": "random", "ring": "triple", "fields": [], "repeats": 1, "shuffle": False
    }


@pytest.fixture
def alice(register):
    return register("alice")
