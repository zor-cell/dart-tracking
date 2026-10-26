import asyncio

import httpx2
import pytest

from app.api.features.player.persistence.player_repository import PlayerRepository
from app.main import app


@pytest.fixture
def alice(register):
    return register("alice")


@pytest.fixture
def bob(register):
    return register("bob")


def entries(api, **params):
    return {entry["name"]: entry for entry in api.get("/players/page", params=params).json()["items"]}


def links(api):
    return api.get("/players/links").json()


def history(api):
    return api.get("/games").json()["total"]


def link(inviter, invitee, name, reciprocal=False):
    """The inviter's entry `name`, linked to the invitee's account."""
    player_id = inviter.add_player(name)
    assert invitee.accept(inviter.invite(player_id), reciprocal).status_code == 204
    return player_id


def test_accepting_an_invitation_links_the_entry(alice, bob):
    player_id = alice.add_player("Bob")
    token = alice.invite(player_id)

    preview = bob.get(f"/players/invitations/{token}").json()
    assert preview == {"inviterName": "Alice", "playerName": "Bob", "gameCount": 0, "reciprocal": "create"}

    assert bob.accept(token).status_code == 204
    assert entries(alice)["Bob"]["linked"] is True
    assert links(bob) == [{"playerId": player_id, "ownerName": "Alice", "retired": False}]
    assert bob.accept(token).status_code == 404


def test_preview_counts_the_games_the_entry_played(alice, bob):
    player_id = alice.add_player("Bob")
    alice.new_game(alice.own_entry()["id"], player_id)

    preview = bob.get(f"/players/invitations/{alice.invite(player_id)}").json()

    assert preview["gameCount"] == 1


def test_reciprocal_creates_a_linked_entry_for_the_inviter(alice, bob):
    link(alice, bob, "Bob", reciprocal=True)

    assert entries(bob)["Alice"]["linked"] is True
    assert [entry["ownerName"] for entry in links(alice)] == ["Bob"]


def test_reciprocal_links_an_unlinked_entry_of_that_name(alice, bob):
    existing = bob.add_player("alice")
    token = alice.invite(alice.add_player("Bob"))
    assert bob.get(f"/players/invitations/{token}").json()["reciprocal"] == "link"

    bob.accept(token, reciprocal=True)

    book = entries(bob)
    assert list(book) == ["Bob", "alice"]
    assert book["alice"] == {"id": existing, "name": "alice", "isSelf": False, "linked": True}


def test_reciprocal_leaves_a_name_held_by_another_account_alone(alice, bob, register):
    carol = register("carol", display_name="Alice")
    link(bob, carol, "Alice")
    token = alice.invite(alice.add_player("Bob"))
    assert bob.get(f"/players/invitations/{token}").json()["reciprocal"] == "none"

    assert bob.accept(token, reciprocal=True).status_code == 204

    assert len(bob.get("/players/page").json()["items"]) == 2
    assert links(alice) == []


def test_reciprocal_is_nothing_once_the_inviter_is_already_linked(alice, bob):
    link(bob, alice, "Alice")
    token = alice.invite(alice.add_player("Bob"))

    assert bob.get(f"/players/invitations/{token}").json()["reciprocal"] == "none"


def test_without_reciprocal_the_invitee_book_stays_as_it_was(alice, bob):
    link(alice, bob, "Bob")

    assert list(entries(bob)) == ["Bob"]


def test_own_invitation_cannot_be_opened(alice):
    token = alice.invite(alice.add_player("Bob"))

    assert alice.get(f"/players/invitations/{token}").status_code == 400
    assert alice.accept(token).status_code == 400


def test_an_account_is_linked_at_most_once_per_address_book(alice, bob):
    link(alice, bob, "Bob")
    token = alice.invite(alice.add_player("Bobby"))

    assert bob.get(f"/players/invitations/{token}").status_code == 409
    assert bob.accept(token).status_code == 409


def test_new_invitation_voids_the_older_one(alice, bob):
    player_id = alice.add_player("Bob")
    older = alice.invite(player_id)
    newer = alice.invite(player_id)

    assert bob.accept(older).status_code == 404
    assert bob.accept(newer).status_code == 204


def test_invitation_to_a_removed_entry(alice, bob):
    player_id = alice.add_player("Bob")
    token = alice.invite(player_id)
    alice.delete(f"/players/{player_id}")

    assert bob.get(f"/players/invitations/{token}").status_code == 404
    assert bob.accept(token).status_code == 404


def test_a_linked_entry_cannot_be_invited_again(alice, bob):
    player_id = link(alice, bob, "Bob")
    assert alice.post(f"/players/{player_id}/invitation").status_code == 404


def test_unknown_invitation(bob):
    assert bob.get("/players/invitations/made-up").status_code == 404
    assert bob.accept("made-up").status_code == 404


def test_invitations_need_an_account(alice, anon):
    token = alice.invite(alice.add_player("Bob"))
    assert anon.get(f"/players/invitations/{token}").status_code == 401


def test_opening_invitations_is_limited(alice, bob):
    token = alice.invite(alice.add_player("Bob"))
    statuses = [bob.get(f"/players/invitations/{token}").status_code for _ in range(31)]
    assert statuses[-2:] == [200, 429]


def test_one_invitation_links_exactly_one_account(alice, bob, register, session, monkeypatch):
    carol = register("carol")
    player_id = alice.add_player("Bob")
    token = alice.invite(player_id)

    # Both requests read the entry before either writes it.
    read_entry = PlayerRepository._editable

    async def slow_read(self, *args):
        row = await read_entry(self, *args)
        await asyncio.sleep(0.05)
        return row

    monkeypatch.setattr(PlayerRepository, "_editable", slow_read)

    async def accept_both() -> list[int]:
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://testserver") as client:
            responses = await asyncio.gather(
                *(
                    client.post(
                        f"/api/players/invitations/{token}",
                        json={"reciprocal": False},
                        headers={"Authorization": f"Bearer {api.token}"},
                    )
                    for api in (bob, carol)
                )
            )
        return [response.status_code for response in responses]

    statuses = session.run(accept_both)

    linked_to = session.sql("SELECT user_id FROM players WHERE id = :id", id=player_id)[0][0]
    winners = [api for api, status in zip((bob, carol), statuses) if status == 204]
    assert len(winners) == 1, statuses
    assert str(linked_to) == winners[0].id
    assert [len(links(api)) for api in (bob, carol)] == [int(api is winners[0]) for api in (bob, carol)]


def test_unlinking_an_entry_without_games_keeps_it(alice, bob):
    player_id = link(alice, bob, "Bob")

    response = alice.delete(f"/players/{player_id}/link")

    assert response.json() == {"id": player_id, "name": "Bob", "isSelf": False, "linked": False}
    assert links(bob) == []


def test_unlinking_after_games_retires_the_entry_with_its_history(alice, bob):
    player_id = link(alice, bob, "Bob")
    alice.new_game(alice.own_entry()["id"], player_id)

    replacement = alice.delete(f"/players/{player_id}/link").json()

    assert replacement["id"] != player_id
    assert (replacement["name"], replacement["linked"]) == ("Bob", False)
    assert list(entries(alice)) == ["Alice", "Bob"]
    assert links(bob) == [{"playerId": player_id, "ownerName": "Alice", "retired": True}]
    assert history(bob) == history(alice) == 1


def test_unlink_needs_a_linked_entry(alice):
    player_id = alice.add_player("Bob")
    assert alice.delete(f"/players/{player_id}/link").status_code == 404


def test_leaving_without_history_takes_the_games_along(alice, bob):
    player_id = link(alice, bob, "Bob")
    alice.new_game(alice.own_entry()["id"], player_id)

    assert bob.delete(f"/players/links/{player_id}").status_code == 204

    assert entries(alice)["Bob"] == {"id": player_id, "name": "Bob", "isSelf": False, "linked": False}
    assert (links(bob), history(bob), history(alice)) == ([], 0, 1)


def test_leaving_with_history_keeps_the_games(alice, bob):
    player_id = link(alice, bob, "Bob")
    alice.new_game(alice.own_entry()["id"], player_id)

    assert bob.delete(f"/players/links/{player_id}", params={"keepHistory": True}).status_code == 204

    assert entries(alice)["Bob"]["linked"] is False
    assert entries(alice)["Bob"]["id"] != player_id
    assert links(bob) == [{"playerId": player_id, "ownerName": "Alice", "retired": True}]
    assert history(bob) == 1


def test_a_retired_link_can_only_be_dropped_with_its_history(alice, bob):
    player_id = link(alice, bob, "Bob")
    alice.new_game(alice.own_entry()["id"], player_id)
    alice.delete(f"/players/{player_id}/link")

    assert bob.delete(f"/players/links/{player_id}", params={"keepHistory": True}).status_code == 204

    assert (links(bob), history(bob)) == ([], 0)


def test_removing_a_linked_entry_leaves_the_account_its_games(alice, bob):
    player_id = link(alice, bob, "Bob")
    alice.new_game(alice.own_entry()["id"], player_id)

    assert alice.delete(f"/players/{player_id}").status_code == 204

    assert list(entries(alice)) == ["Alice"]
    assert links(bob) == [{"playerId": player_id, "ownerName": "Alice", "retired": True}]
    assert history(bob) == 1


def test_link_names_the_owner_as_the_own_address_book_does(alice, bob):
    bobs_entry = link(alice, bob, "Bob")
    alices_entry = link(bob, alice, "Mum")

    assert links(alice) == [{"playerId": alices_entry, "ownerName": "Bob", "retired": False}]
    assert links(bob) == [{"playerId": bobs_entry, "ownerName": "Mum", "retired": False}]


@pytest.mark.parametrize("player_id", ["self", "not-a-uuid"])
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("PUT", "/players/{id}"),
        ("DELETE", "/players/{id}"),
        ("POST", "/players/{id}/invitation"),
        ("DELETE", "/players/{id}/link"),
        ("DELETE", "/players/links/{id}"),
    ],
)
def test_own_entry_and_malformed_ids_are_not_found(alice, method, path, player_id):
    target = alice.own_entry()["id"] if player_id == "self" else player_id

    response = alice.request(method, path.format(id=target), json={"name": "Other"})

    assert response.status_code == 404


@pytest.mark.parametrize("name", ["bob", "  BOB ", "alice"])
def test_names_are_unique_per_address_book_ignoring_case(alice, name):
    alice.add_player("Bob")
    assert alice.post("/players", json={"name": name}).status_code == 409


def test_rename(alice):
    bob_id = alice.add_player("Bob")
    alice.add_player("Carol")

    assert alice.put(f"/players/{bob_id}", json={"name": "BOB"}).json()["name"] == "BOB"
    assert alice.put(f"/players/{bob_id}", json={"name": "carol"}).status_code == 409
    assert alice.put(f"/players/{bob_id}", json={"name": "   "}).status_code == 422


def test_rename_shows_in_past_games(alice):
    bob_id = alice.add_player("Bob")
    game = alice.new_game(bob_id)

    alice.put(f"/players/{bob_id}", json={"name": "Robert"})

    assert alice.get(f"/games/{game['id']}").json()["players"][0]["name"] == "Robert"


def test_same_name_in_two_address_books(alice, bob):
    alice.add_player("Carol")
    assert bob.post("/players", json={"name": "Carol"}).status_code == 201


def test_address_book_page_and_filters(alice, bob):
    link(alice, bob, "Bob")
    for name in ("Carol", "Dave", "Eve"):
        alice.add_player(name)

    first = alice.get("/players/page", params={"limit": 2}).json()
    second = alice.get("/players/page", params={"limit": 2, "offset": 2}).json()

    assert [entry["name"] for entry in first["items"] + second["items"]] == ["Alice", "Bob", "Carol", "Dave"]
    assert first["total"] == second["total"] == 5
    assert list(entries(alice, linked=True)) == ["Bob"]
    assert list(entries(alice, linked=False)) == ["Carol", "Dave", "Eve"]
    assert list(entries(alice, q="E")) == ["Alice", "Dave", "Eve"]
    assert alice.get("/players/page", params={"q": "%"}).json()["total"] == 0


def test_linked_players_come_before_the_rest(alice, bob):
    alice.add_player("Carol")
    link(alice, bob, "Zed")

    assert list(entries(alice)) == ["Alice", "Zed", "Carol"]
    assert [entry["name"] for entry in alice.get("/players").json()] == ["Alice", "Zed", "Carol"]


def test_search_matches_the_start_of_names_own_entry_first(alice):
    for name in ("Albert", "Bob", "alex"):
        alice.add_player(name)

    names = [entry["name"] for entry in alice.get("/players", params={"q": "al"}).json()]

    assert names == ["Alice", "Albert", "alex"]
