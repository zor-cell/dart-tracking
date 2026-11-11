import pytest

from tests.api.test_socket import room  # noqa: F401

T20, T19, T18, T17, T16, T15, BULLSEYE, BULL, MISS = (
    (20, 3), (19, 3), (18, 3), (17, 3), (16, 3), (15, 3), (25, 2), (25, 1), (0, 0)
)
CLOSE_ALL = ([T20, T19, T18], [T17, T16, T15], [BULLSEYE, BULL])


@pytest.fixture
def alice(register):
    return register("alice")


def guests(*names):
    return [{"name": name} for name in names]


def create(api, *names, **config):
    return api.post("/games", json={"players": guests(*names), **config})


@pytest.mark.parametrize(
    ("variant", "block"),
    [("cricket", "cricket"), ("killer", "killer"), ("around_the_clock", "aroundTheClock")],
)
def test_a_variant_game_keeps_no_points_and_carries_its_own_standing(anon, variant, block):
    response = create(anon, "Ann", "Ben", variant=variant, mode=501, checkoutMode="single_out")

    assert response.status_code == 201, response.text
    game = response.json()
    assert game["mode"] is None
    assert game["checkoutMode"] is None
    assert game["checkout"] is None
    assert [player["remaining"] for player in game["players"]] == [None, None]
    others = {"cricket", "killer", "aroundTheClock"} - {block}
    assert game[block] is not None
    assert all(game[other] is None for other in others)
    assert anon.get(f"/games/{game['id']}").json() == game


def test_a_points_game_needs_a_mode(anon):
    assert create(anon, "Ann", variant="x01").status_code == 422
    assert create(anon, "Ann", variant="elimination").status_code == 422


@pytest.mark.parametrize(
    "config",
    [
        {"variant": "killer"},
        {"variant": "killer", "killer": {"lives": 0}},
        {"variant": "cricket", "cricket": {"scoring": "golf"}},
        {"variant": "around_the_clock", "aroundTheClock": {"zone": "outer"}},
    ],
)
def test_impossible_settings_are_refused(anon, config):
    players = ["Ann"] if config == {"variant": "killer"} else ["Ann", "Ben"]

    assert create(anon, *players, **config).status_code == 422


def test_killer_needs_a_number_for_everyone(anon):
    names = [f"P{seat}" for seat in range(21)]

    assert create(anon, *names, variant="killer").status_code == 422
    assert create(anon, *names[:20], variant="killer").status_code == 201


def test_killer_deals_every_seat_its_own_number(anon):
    game = create(
        anon, "Ann", "Ben", "Cid", variant="killer", killer={"lives": 5, "zone": "triple"}
    ).json()

    killer = game["killer"]
    numbers = [player["number"] for player in killer["players"]]
    assert len(set(numbers)) == 3
    assert all(1 <= number <= 20 for number in numbers)
    assert (killer["lives"], killer["zone"]) == (5, "triple")
    assert [player["lives"] for player in killer["players"]] == [5, 5, 5]
    assert anon.get(f"/games/{game['id']}").json()["killer"] == killer


def test_settings_are_kept(anon):
    cricket = create(anon, "Ann", variant="cricket", cricket={"scoring": "cut_throat"}).json()
    clock = create(
        anon, "Ann", variant="around_the_clock", aroundTheClock={"zone": "double", "skip": True}
    ).json()

    assert anon.get(f"/games/{cricket['id']}").json()["cricket"]["scoring"] == "cut_throat"
    stored = anon.get(f"/games/{clock['id']}").json()["aroundTheClock"]
    assert (stored["zone"], stored["skip"]) == ("double", True)
    assert stored["players"][0]["target"] == 1


def test_a_won_cricket_game_is_finished_and_named_in_the_history(alice, session):
    me = alice.own_entry()["id"]
    game_id = alice.new_game(me, alice.add_player("Bob"), variant="cricket")["id"]
    session.play(game_id, CLOSE_ALL[0], [MISS], CLOSE_ALL[1], [MISS], CLOSE_ALL[2], hand_over=False)

    listed = alice.get("/games", params={"variant": "cricket"}).json()["items"]
    assert [game["id"] for game in listed] == [game_id]
    assert listed[0]["status"] == "finished"
    assert listed[0]["winnerIndex"] == 0
    assert listed[0]["mode"] is None
    assert [player["remaining"] for player in listed[0]["players"]] == [None, None]
    assert alice.get("/games", params={"mode": 301}).json()["total"] == 0

    detail = alice.get(f"/games/{game_id}/detail").json()
    assert detail["statistics"] == []
    assert all(visit["standings"] == [] for visit in detail["visits"])
    assert detail["game"]["winnerId"] == 0
    assert detail["game"]["cricket"]["players"][0]["marks"] == [3] * 7

    assert alice.get("/statistics").json()["legs"] == 0


def test_an_unfinished_variant_game_has_no_winner_in_the_history(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], variant="around_the_clock")["id"]
    session.play(game_id, [(1, 1), (2, 1), (3, 1)])

    listed = alice.get("/games").json()["items"][0]
    assert listed["winnerIndex"] is None
    assert listed["status"] == "active"


def test_a_knock_out_is_called_and_passed_over(room, anon):  # noqa: F811
    game = create(anon, "Ann", "Ben", "Cid", variant="killer", killer={"lives": 1}).json()
    ann, ben, _ = (player["number"] for player in game["killer"]["players"])
    with room(game["id"]) as announcer:
        announcer.throw(ann, 2)
        announcer.throw(ben, 2)
        calls = [announcer.next("dart_announcement") for _ in range(2)]
        announcer.send("next_player")
        state = announcer.next("game_state")
        while state["currentPlayerIndex"] == 0:
            state = announcer.next("game_state")
        turn = announcer.next("turn_announcement")

    assert [call["eliminated"] for call in calls] == [[], ["Ben"]]
    assert all(call["visitPoints"] is None for call in calls)
    assert state["currentPlayerIndex"] == 2
    assert state["players"][1]["justReset"] is True
    assert state["killer"]["players"][1]["lives"] == 0
    assert (turn["player"], turn["score"]) == ("Cid", None)


def test_the_last_one_standing_wins(room, anon):  # noqa: F811
    game = create(anon, "Ann", "Ben", variant="killer", killer={"lives": 1}).json()
    ann, ben = (player["number"] for player in game["killer"]["players"])
    with room(game["id"]) as device:
        device.throw(ann, 2)
        device.throw(ben, 2)
        state = device.next("game_state")
        while state["winnerId"] is None:
            state = device.next("game_state")
        device.throw(ben, 2)
        state = device.next("game_state")

    assert state["winnerId"] == 0
    assert [dart["label"] for dart in state["shadowDarts"]] == [f"D{ben}"]


def test_a_rematch_takes_the_settings_and_deals_again(anon):
    first = create(anon, "Ann", "Ben", variant="killer", killer={"lives": 2}).json()
    rematch = anon.post(
        "/games",
        json={
            "variant": "killer",
            "killer": {"lives": 2},
            "players": [{"playerId": player["identityId"]} for player in first["players"]],
            "rematchOf": first["id"],
        },
    )

    assert rematch.status_code == 201, rematch.text
    assert rematch.json()["killer"]["lives"] == 2
