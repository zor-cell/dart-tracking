import pytest

from tests.api.support import X01

T20, T17, D5, MISS = (20, 3), (17, 3), (5, 2), (0, 0)
# 301 in three visits, finished on D5.
WINNING_LEG = ([T20, T20, T20], [T20, T17, D5])


@pytest.fixture
def alice(register):
    return register("alice")


@pytest.fixture
def bob(register):
    return register("bob")


def guest(name):
    return {"name": name}


def claimable(api, *games):
    claims = [{"gameId": game["id"], "token": game["claimToken"]} for game in games]
    response = api.post("/games/claimable", json={"claims": claims})
    assert response.status_code == 200, response.text
    return [game["id"] for game in response.json()]


def claim(api, game, seat=None, token=None):
    return api.post(
        f"/games/{game['id']}/claim", json={"token": token or game["claimToken"], "seat": seat}
    )


def book(api):
    return sorted(entry["name"] for entry in api.get("/players").json())


def test_only_anonymous_games_carry_a_claim_token(alice, anon):
    assert anon.new_game(guest("Ann"))["claimToken"]
    assert alice.new_game(guest("Ann"))["claimToken"] is None


def test_claimable_lists_ownerless_games_with_their_own_token(alice, anon):
    first = anon.new_game(guest("Ann"))
    second = anon.new_game(guest("Ben"))
    forged = {**second, "claimToken": first["claimToken"]}

    assert claimable(alice, first, forged, {"id": "not-a-uuid", "claimToken": "x"}) == [first["id"]]


def test_claimable_needs_an_account(anon):
    game = anon.new_game(guest("Ann"))
    response = anon.post(
        "/games/claimable", json={"claims": [{"gameId": game["id"], "token": game["claimToken"]}]}
    )
    assert response.status_code == 401


def test_claim_seats_the_account_and_files_the_guests(alice, anon, session):
    game = anon.new_game(guest("Philippe"), guest("Ben"))
    session.play(game["id"], WINNING_LEG[0], [MISS], WINNING_LEG[1])

    assert claim(alice, game, seat=0).status_code == 204

    summary = alice.get("/games").json()["items"][0]
    assert summary["id"] == game["id"]
    assert [player["isMe"] for player in summary["players"]] == [True, False]
    assert summary["players"][0]["name"] == "Alice"
    assert alice.get("/statistics").json()["legsWon"] == 1
    assert book(alice) == ["Alice", "Ben"]
    assert claimable(alice, game) == []


def test_claim_reuses_an_address_book_entry_of_the_same_name(alice, anon):
    ben = alice.add_player("Ben")
    game = anon.new_game(guest("ben"), guest("Ben"))

    assert claim(alice, game).status_code == 204

    detail = alice.get(f"/games/{game['id']}").json()
    assert detail["players"][0]["identityId"] == ben
    assert detail["players"][1]["identityId"] != ben
    assert book(alice) == ["Alice", "Ben", "Ben"]


def test_claim_without_a_seat_keeps_score_only(alice, anon, session):
    game = anon.new_game(guest("Ann"))
    session.play(game["id"], *WINNING_LEG)

    assert claim(alice, game).status_code == 204

    assert alice.get("/games").json()["items"][0]["id"] == game["id"]
    assert alice.get("/statistics").json()["legs"] == 0


def test_a_game_is_claimed_once(alice, bob, anon):
    game = anon.new_game(guest("Ann"))

    assert claim(alice, game, seat=0).status_code == 204
    assert claim(bob, game, seat=0).status_code == 404
    assert claim(alice, game, seat=0).status_code == 404


@pytest.mark.parametrize("seat", [-1, 2])
def test_claim_seat_must_exist(alice, anon, seat):
    game = anon.new_game(guest("Ann"), guest("Ben"))

    assert claim(alice, game, seat=seat).status_code == 422
    assert claimable(alice, game) == [game["id"]]


def test_claim_needs_the_token_and_an_account(alice, anon):
    game = anon.new_game(guest("Ann"))

    assert claim(alice, game, token="wrong").status_code == 404
    assert claim(alice, {**game, "id": "not-a-uuid"}).status_code == 404
    assert claim(anon, game).status_code == 401


def test_claiming_a_rematch_keeps_the_guests_filed_by_the_first(alice, anon):
    first = anon.new_game(guest("Philippe"), guest("Ben"))
    seats = [{"playerId": player["identityId"]} for player in first["players"]]
    rematch = anon.post("/games", json={"settings": X01, "players": seats, "rematchOf": first["id"]})
    assert rematch.status_code == 201

    assert claim(alice, first, seat=0).status_code == 204
    assert claim(alice, rematch.json(), seat=0).status_code == 204

    assert book(alice) == ["Alice", "Ben"]


def test_an_accounts_seat_cannot_be_taken_over(alice, bob, anon):
    first = alice.new_game(alice.own_entry()["id"], guest("Ann"))
    seats = [{"playerId": player["identityId"]} for player in first["players"]]
    rematch = anon.post(
        "/games", json={"settings": X01, "players": seats, "rematchOf": first["id"]}
    ).json()

    assert claim(bob, rematch, seat=0).status_code == 422
    assert claim(bob, rematch, seat=1).status_code == 204
    assert alice.get(f"/games/{rematch['id']}").json()["players"][0]["name"] == "Alice"
