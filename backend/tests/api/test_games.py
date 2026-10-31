from datetime import UTC, datetime, timedelta

import pytest

T20, T19, T17, D20, D5, S1, MISS = (20, 3), (19, 3), (17, 3), (20, 2), (5, 2), (1, 1), (0, 0)
# 301 in three visits, finished on D5.
WINNING_LEG = ([T20, T20, T20], [T20, T17, D5])


@pytest.fixture
def alice(register):
    return register("alice")


@pytest.fixture
def bob(register):
    return register("bob")


def seats(game):
    return [player["identityId"] for player in game["players"]]


def guest(name):
    return {"name": name}


def test_anonymous_game_with_guests(anon):
    game = anon.new_game(guest("Ann"), guest(" Ben "))

    assert [player["name"] for player in game["players"]] == ["Ann", "Ben"]
    assert anon.get(f"/games/{game['id']}").json()["id"] == game["id"]


@pytest.mark.parametrize(
    "players",
    [
        [],
        [{"playerId": None, "name": "  "}],
        [{"playerId": "00000000-0000-0000-0000-000000000000", "name": "Both"}],
    ],
)
def test_seats_must_be_well_formed(anon, players):
    assert anon.post("/games", json={"mode": 301, "players": players}).status_code == 422


def test_address_book_seats_need_an_account(alice, anon):
    entry = alice.add_player("Bob")
    assert anon.post("/games", json={"mode": 301, "players": [{"playerId": entry}]}).status_code == 401


@pytest.mark.parametrize("seat", ["foreign", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_only_own_address_book_entries_take_a_seat(alice, bob, seat):
    player_id = bob.add_player("Carol") if seat == "foreign" else seat
    response = alice.post("/games", json={"mode": 301, "players": [{"playerId": player_id}]})
    assert response.status_code == 422


def test_one_seat_per_player_whether_chosen_or_typed(alice):
    bob_id = alice.add_player("Bob")
    for players in ([{"playerId": bob_id}, {"playerId": bob_id}], [{"playerId": bob_id}, guest("BOB")]):
        response = alice.post("/games", json={"mode": 301, "players": players})
        assert response.status_code == 422


def test_typed_names_reuse_the_address_book(alice):
    bob_id = alice.add_player("Bob")

    game = alice.new_game(guest("bob"), guest("Carol"))

    assert seats(game)[0] == bob_id
    assert "Carol" in [entry["name"] for entry in alice.get("/players").json()]


def test_guests_of_anonymous_games_belong_to_nobody(anon, alice):
    anon.new_game(guest("Alice"))
    assert [entry["name"] for entry in alice.get("/players").json()] == ["Alice"]


def test_recent_rematch_keeps_the_seats_even_without_an_account(alice, anon):
    first = alice.new_game(alice.own_entry()["id"], alice.add_player("Bob"))

    rematch = anon.post(
        "/games",
        json={"mode": 301, "players": [{"playerId": s} for s in seats(first)], "rematchOf": first["id"]},
    )

    assert rematch.status_code == 201
    assert seats(rematch.json()) == seats(first)


def test_late_rematch_seats_by_name(alice, bob, session):
    first = bob.new_game(bob.own_entry()["id"], bob.add_player("Carol"))
    session.age_game(first["id"], hours=25)

    rematch = alice.new_game(*seats(first), rematchOf=first["id"])

    assert [player["name"] for player in rematch["players"]] == ["Bob", "Carol"]
    assert not set(seats(rematch)) & set(seats(first))
    assert {entry["name"] for entry in alice.get("/players").json()} == {"Alice", "Bob", "Carol"}


def test_rematch_cannot_seat_identities_of_another_game(alice, bob):
    first = alice.new_game(alice.own_entry()["id"])
    other = bob.new_game(bob.own_entry()["id"])

    response = alice.post(
        "/games", json={"mode": 301, "players": [{"playerId": seats(other)[0]}], "rematchOf": first["id"]}
    )

    assert response.status_code == 422


@pytest.mark.parametrize(("admin", "enabled"), [(False, False), (True, True)])
def test_only_admins_start_an_evaluation_run(alice, session, admin, enabled):
    if admin:
        session.make_admin(alice)

    game = alice.new_game(guest("Ann"), evaluationEnabled=True)

    assert game["evaluationEnabled"] is enabled


def status_of(api, game_id):
    listed = [api.get("/games", params=params).json()["items"] for params in ({}, {"status": "discarded"})]
    return next(game for items in listed for game in items if game["id"] == game_id)


@pytest.mark.parametrize(("legs", "restored"), [((), "active"), (WINNING_LEG, "finished")])
def test_discard_and_restore(alice, session, legs, restored):
    game_id = alice.new_game(alice.own_entry()["id"])["id"]
    session.play(game_id, *legs)

    assert alice.patch(f"/games/{game_id}", json={"status": "discarded"}).status_code == 204
    discarded = status_of(alice, game_id)
    assert (discarded["status"], discarded["counted"]) == ("discarded", False)

    assert alice.patch(f"/games/{game_id}", json={"status": "active"}).status_code == 204
    assert status_of(alice, game_id)["status"] == restored


def test_discarded_game_stays_discarded_while_played_on(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"])["id"]
    alice.patch(f"/games/{game_id}", json={"status": "discarded"})

    session.play(game_id, *WINNING_LEG)

    assert status_of(alice, game_id)["status"] == "discarded"


def test_only_the_owner_discards(alice, bob, anon):
    bob_id = alice.add_player("Bob")
    bob.accept(alice.invite(bob_id))
    game_id = alice.new_game(bob_id)["id"]
    anonymous_game = anon.new_game(guest("Ann"))["id"]

    assert bob.patch(f"/games/{game_id}", json={"status": "discarded"}).status_code == 404
    assert alice.patch(f"/games/{anonymous_game}", json={"status": "discarded"}).status_code == 404
    assert alice.patch(f"/games/{game_id}", json={"status": "finished"}).status_code == 422


def test_detail_for_owner_and_seated_accounts_only(alice, bob, register, session):
    carol = register("carol")
    bob_id = alice.add_player("Bob")
    bob.accept(alice.invite(bob_id))
    game_id = alice.new_game(alice.own_entry()["id"], bob_id)["id"]
    session.play(game_id, [T20, S1, MISS], [D20])

    detail = bob.get(f"/games/{game_id}/detail")

    assert detail.status_code == 200
    assert len(detail.json()["visits"]) == 2
    assert [entry["darts"] for entry in detail.json()["statistics"]] == [3, 3]
    assert alice.get(f"/games/{game_id}/detail").status_code == 200
    assert carol.get(f"/games/{game_id}/detail").status_code == 404


def test_unknown_game(anon):
    assert anon.get("/games/00000000-0000-0000-0000-000000000000").status_code == 404
    assert anon.get("/games/not-a-uuid").status_code == 404


def test_history_holds_games_owned_and_games_seated_in(alice, bob, anon):
    bob_id = alice.add_player("Bob")
    bob.accept(alice.invite(bob_id))
    alice.new_game(bob_id)
    bob.new_game(bob.own_entry()["id"])
    alice.new_game(guest("Kept score for"))
    anon.new_game(guest("Nobody's"))

    assert alice.get("/games").json()["total"] == 2
    assert bob.get("/games").json()["total"] == 2


def test_history_filters_and_paging(alice, session):
    me = alice.own_entry()["id"]
    bob = alice.add_player("Bob")
    finished = alice.new_game(me, bob)["id"]
    session.play(finished, WINNING_LEG[0], [MISS], WINNING_LEG[1])
    elimination = alice.new_game(me, variant="elimination", mode=501)["id"]
    abandoned = alice.new_game(me, alice.add_player("Carol"), bob)["id"]
    session.play(abandoned, [S1, S1, S1], [S1, S1, S1], [S1, S1, S1])
    session.age_game(abandoned, hours=48)
    discarded = alice.new_game(me)["id"]
    alice.patch(f"/games/{discarded}", json={"status": "discarded"})

    def ids(**params):
        page = alice.get("/games", params=params).json()
        assert page["total"] == len(page["items"])
        return {game["id"] for game in page["items"]}

    assert ids(variant="elimination") == {elimination}
    assert ids(mode=501) == {elimination}
    assert ids(status="finished") == {finished}
    assert ids(status="abandoned") == {abandoned}
    assert ids(status="active") == {elimination}
    assert ids(status="discarded") == {discarded}
    assert ids(opponent=bob) == {finished, abandoned}
    assert ids(minPlayers=2) == {finished, abandoned}
    assert ids(maxPlayers=1) == {elimination}
    assert ids(minPlayers=3, maxPlayers=3) == {abandoned}
    assert ids(until=(datetime.now(UTC) - timedelta(hours=1)).isoformat()) == {abandoned}
    assert ids(since=(datetime.now(UTC) - timedelta(hours=1)).isoformat()) == {finished, elimination}

    first = alice.get("/games", params={"limit": 2}).json()
    rest = alice.get("/games", params={"limit": 2, "offset": 2}).json()
    assert first["total"] == rest["total"] == 3
    assert len({g["id"] for g in first["items"] + rest["items"]}) == 3


def test_history_filters_by_a_visit_of_the_accounts_own(alice, session):
    me = alice.own_entry()["id"]
    bob = alice.add_player("Bob")
    ton_eighty = alice.new_game(me, bob)["id"]
    session.play(ton_eighty, [T20, T20, T20], [S1])
    only_bob = alice.new_game(me, bob)["id"]
    session.play(only_bob, [S1], [T20, T20, T20])
    busted = alice.new_game(me)["id"]
    session.play(busted, [T20, T20, T19], [T20, T20, T20])

    def ids(**params):
        return {game["id"] for game in alice.get("/games", params=params).json()["items"]}

    assert ids(minVisit=180) == {ton_eighty}
    assert ids(minVisit=177) == {ton_eighty, busted}
    assert alice.get("/games", params={"minVisit": 181}).status_code == 422


def test_history_hides_discarded_and_short_abandoned_games_by_default(alice, session):
    me = alice.own_entry()["id"]
    played = alice.new_game(me)["id"]
    session.play(played, [S1, S1, S1], [S1, S1, S1], [S1, S1, S1])
    session.age_game(played, hours=48)
    short = alice.new_game(me)["id"]
    session.play(short, [S1, S1, S1], [S1, S1, S1], [S1, S1], hand_over=False)
    session.age_game(short, hours=48)
    discarded = alice.new_game(me)["id"]
    alice.patch(f"/games/{discarded}", json={"status": "discarded"})

    def ids(**params):
        return {game["id"] for game in alice.get("/games", params=params).json()["items"]}

    assert ids() == {played}
    assert ids(status="abandoned") == {played, short}
    assert ids(status="discarded") == {discarded}


def test_history_search_by_player_name(alice):
    me = alice.own_entry()["id"]
    with_bob = alice.new_game(me, alice.add_player("Bob"))["id"]
    with_bobby = alice.new_game(guest("Bobby"))["id"]
    alice.new_game(me, alice.add_player("Carol"))

    def ids(q):
        page = alice.get("/games", params={"q": q}).json()
        assert page["total"] == len(page["items"])
        return {game["id"] for game in page["items"]}

    assert ids("bob") == {with_bob, with_bobby}
    assert ids("  BOBBY ") == {with_bobby}
    assert ids("%") == set()
    assert len(ids("")) == 3
    assert alice.get("/games", params={"q": "x" * 65}).status_code == 422


def test_summary_scores_and_winner(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], alice.add_player("Bob"))["id"]
    session.play(game_id, WINNING_LEG[0], [T20, T20, T20], [T20, T20, T20], [MISS])

    summary = status_of(alice, game_id)

    assert [(p["name"], p["remaining"], p["isMe"]) for p in summary["players"]] == [
        ("Alice", 121, True),
        ("Bob", 121, False),
    ]
    assert summary["dartCount"] == 12
    assert summary["winnerIndex"] is None


def test_elimination_summary_replays_the_resets(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], alice.add_player("Bob"), variant="elimination")["id"]
    session.play(game_id, [T20], [T20])

    assert [p["remaining"] for p in status_of(alice, game_id)["players"]] == [301, 241]


def test_anonymous_games_are_limited_per_address(anon):
    statuses = [anon.post("/games", json={"mode": 301, "players": [guest("Ann")]}).status_code for _ in range(31)]
    assert statuses[-2:] == [201, 429]


def test_malformed_game_ids_are_not_found(alice):
    assert alice.patch("/games/not-a-uuid", json={"status": "discarded"}).status_code == 404
    assert alice.get("/games/not-a-uuid/detail").status_code == 404


@pytest.mark.parametrize("rematch_of", ["not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_rematch_of_an_unknown_game_is_a_new_game(anon, rematch_of):
    response = anon.post("/games", json={"mode": 301, "players": [guest("Ann")], "rematchOf": rematch_of})
    assert response.status_code == 201
