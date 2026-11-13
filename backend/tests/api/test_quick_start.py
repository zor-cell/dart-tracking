import pytest

T20, MISS = (20, 3), (0, 0)


@pytest.fixture
def alice(register):
    return register("alice")


@pytest.fixture
def bob(register):
    return register("bob")


def quick_start(api):
    response = api.get("/games/quick-start")
    assert response.status_code == 200, response.text
    return response.json()


def test_an_account_that_has_not_played_gets_none(alice):
    assert quick_start(alice) is None
    assert alice.get("/games/quick-start", headers={"Authorization": ""}).status_code == 401


def test_the_setup_played_most_comes_with_the_last_players(alice, session):
    me = alice.own_entry()["id"]
    bob = alice.add_player("Bob")
    for _ in range(2):
        game = alice.new_game(me, bob, variant="cricket", cricket={"scoring": "cut_throat"})
        session.play(game["id"], [T20])
    latest = alice.new_game(bob, me, {"name": "Cid"}, variant="cricket", cricket={"scoring": "cut_throat"})
    session.play(latest["id"], [T20])
    session.play(alice.new_game(me)["id"], [T20])

    found = quick_start(alice)

    assert found["variant"] == "cricket"
    assert found["cricket"] == {"scoring": "cut_throat"}
    assert (found["mode"], found["killer"], found["aroundTheClock"], found["elimination"]) == (
        None, None, None, None
    )
    assert [seat["name"] for seat in found["players"]] == ["Bob", "Alice", "Cid"]
    assert [seat["playerId"] for seat in found["players"]][:2] == [bob, me]


def test_games_without_darts_or_hidden_ones_do_not_count(alice, session):
    me = alice.own_entry()["id"]
    alice.new_game(me, variant="killer", killer={"lives": 5}, players=[{"playerId": me}, {"name": "Ben"}])
    hidden = alice.new_game(me, variant="around_the_clock")["id"]
    session.play(hidden, [T20])
    alice.patch(f"/games/{hidden}", json={"status": "discarded"})

    assert quick_start(alice) is None


def test_killer_settings_come_without_the_dealt_numbers(alice, session):
    me = alice.own_entry()["id"]
    game = alice.post(
        "/games",
        json={
            "variant": "killer",
            "killer": {"lives": 5, "zone": "triple"},
            "players": [{"playerId": me}, {"name": "Ben"}],
        },
    ).json()
    session.play(game["id"], [MISS])

    found = quick_start(alice)

    assert found["killer"] == {"lives": 5, "zone": "triple"}
    assert alice.post("/games", json={**found, "players": [
        {"playerId": seat["playerId"]} if seat["playerId"] else {"name": seat["name"]}
        for seat in found["players"]
    ]}).status_code == 201


def test_a_seat_in_someone_elses_game_maps_to_the_own_entry(alice, bob, session):
    linked = bob.add_player("Alice")
    assert alice.accept(bob.invite(linked)).status_code == 204
    game = bob.new_game(bob.own_entry()["id"], linked)
    session.play(game["id"], [T20])

    found = quick_start(alice)

    assert found["players"] == [
        {"playerId": None, "name": "Bob"},
        {"playerId": alice.own_entry()["id"], "name": "Alice"},
    ]
    assert found["mode"] == 301


def test_elimination_settings_come_along(alice, session):
    me = alice.own_entry()["id"]
    game = alice.new_game(
        me, alice.add_player("Ben"), variant="elimination", mode=501, elimination={"kill": "double"}
    )
    session.play(game["id"], [MISS])

    found = quick_start(alice)

    assert (found["variant"], found["elimination"]) == ("elimination", {"kill": "double"})


def test_the_finish_rules_come_with_the_setup(alice, session):
    me = alice.own_entry()["id"]
    game = alice.new_game(me, {"name": "Ben"}, mode=501, catchUp=True, playOn=True)
    session.play(game["id"], [T20])

    found = quick_start(alice)

    assert (found["catchUp"], found["playOn"]) == (True, True)
