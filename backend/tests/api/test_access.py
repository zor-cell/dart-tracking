import re

import pytest

from app.main import app

PUBLIC = {
    ("GET", "/api/health"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/verify-email"),
    ("POST", "/api/auth/password-reset"),
    ("POST", "/api/auth/password-reset/confirm"),
    ("POST", "/api/auth/email-change/confirm"),
    ("POST", "/api/games"),
    ("GET", "/api/games/{game_id}"),
    ("GET", "/api/settings"),
}
SOME_ID = "00000000-0000-0000-0000-000000000000"

ROUTES = sorted(
    (method.upper(), path)
    for path, operations in app.openapi()["paths"].items()
    for method in operations
)


@pytest.mark.parametrize(("method", "path"), [r for r in ROUTES if r not in PUBLIC])
def test_every_other_route_needs_an_account(anon, method, path):
    url = re.sub(r"\{\w+\}", SOME_ID, path).removeprefix("/api")
    assert anon.request(method, url).status_code == 401


def test_public_routes_still_exist():
    assert PUBLIC <= set(ROUTES)


@pytest.fixture
def strangers_view(register):
    """Alice's linked entry, her game, and an account with nothing to do with either."""
    alice, bob, carol = register("alice"), register("bob"), register("carol")
    bob_id = alice.add_player("Bob")
    bob.accept(alice.invite(bob_id))
    game_id = alice.new_game(alice.own_entry()["id"], bob_id)["id"]
    return carol, bob_id, game_id


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("PUT", "/players/{player}"),
        ("DELETE", "/players/{player}"),
        ("POST", "/players/{player}/invitation"),
        ("DELETE", "/players/{player}/link"),
        ("DELETE", "/players/links/{player}"),
        ("PATCH", "/games/{game}"),
        ("GET", "/games/{game}/detail"),
    ],
)
def test_other_accounts_records_are_not_found(strangers_view, method, path):
    carol, player_id, game_id = strangers_view

    response = carol.request(
        method,
        path.format(player=player_id, game=game_id),
        json={"name": "Taken over", "status": "discarded"},
    )

    assert response.status_code == 404
