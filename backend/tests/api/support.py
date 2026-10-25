"""Callers and shortcuts for the integration tests: accounts over the real
endpoints, and direct database access where a test needs a state the API cannot make."""

import re
from collections.abc import Callable
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx2
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.persistence.game_repository import repository as games
from app.infrastructure import database, redis_client

PASSWORD = "correct horse battery"
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
_TOKEN = re.compile(r"token=([\w-]+)")


class Api:
    """The app as seen by one caller: anonymous, or holding an account's tokens."""

    def __init__(
        self,
        client: TestClient,
        token: str | None = None,
        user: dict[str, Any] | None = None,
        refresh_token: str | None = None,
    ) -> None:
        self.client = client
        self.token = token
        self.user = user or {}
        self.refresh_token = refresh_token

    @property
    def id(self) -> str:
        return self.user["id"]

    def request(
        self, method: str, path: str, *, refresh: str | None = None, **kwargs: Any
    ) -> httpx2.Response:
        headers = dict(kwargs.pop("headers", {}))
        if self.token is not None:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        if refresh is not None:
            headers["Cookie"] = f"refresh_token={refresh}"
        response = self.client.request(method, f"/api{path}", headers=headers, **kwargs)
        # The jar would mix the refresh cookies of several accounts; each one keeps its own.
        self.client.cookies.clear()
        return response

    def get(self, path: str, **kwargs: Any) -> httpx2.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx2.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx2.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> httpx2.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx2.Response:
        return self.request("DELETE", path, **kwargs)

    def adopt(self, response: httpx2.Response) -> None:
        """Take over the session a sign-in, refresh or password change handed out."""
        assert response.status_code in (200, 201), response.text
        body = response.json()
        self.token = body["accessToken"]
        self.user = body["user"]
        self.refresh_token = response.cookies.get("refresh_token")

    # Address book and games, the shortcuts most tests set their scene with.

    def own_entry(self) -> dict[str, Any]:
        return next(entry for entry in self.get("/players").json() if entry["isSelf"])

    def add_player(self, name: str) -> str:
        response = self.post("/players", json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def invite(self, player_id: str) -> str:
        response = self.post(f"/players/{player_id}/invitation")
        assert response.status_code == 201, response.text
        return response.json()["token"]

    def accept(self, token: str, reciprocal: bool = False) -> httpx2.Response:
        return self.post(f"/players/invitations/{token}", json={"reciprocal": reciprocal})

    def new_game(self, *seats: str | dict[str, str], **config: Any) -> dict[str, Any]:
        """A game seating each entry: a player id from the address book, or a typed name."""
        players = [seat if isinstance(seat, dict) else {"playerId": seat} for seat in seats]
        response = self.post("/games", json={"mode": 301, "players": players, **config})
        assert response.status_code == 201, response.text
        return response.json()


class Session:
    """Accounts and direct database access, all on the app's own event loop."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def run(self, function: Callable[..., Any], *args: Any) -> Any:
        return self.client.portal.call(function, *args)

    def register(self, name: str, *, display_name: str | None = None) -> Api:
        api = Api(self.client)
        api.adopt(
            api.post(
                "/auth/register",
                json={
                    "email": f"{name}@darts.example.org",
                    "username": name,
                    "displayName": display_name or name.capitalize(),
                    "password": PASSWORD,
                },
            )
        )
        return api

    def sql(self, statement: str, **params: Any) -> list[Any]:
        async def execute() -> list[Any]:
            async with database.session_scope() as session:
                result = await session.execute(text(statement), params)
                return list(result.all()) if result.returns_rows else []

        return self.run(execute)

    def make_admin(self, api: Api) -> None:
        self.sql("UPDATE users SET role = 'admin' WHERE id = :id", id=api.id)

    def redis(self, method: str, *args: Any) -> Any:
        async def call() -> Any:
            return await getattr(redis_client.client(), method)(*args)

        return self.run(call)

    def play(self, game_id: str, *visits: list[tuple[int, int]], hand_over: bool = True) -> Game:
        """Throw each visit as (value, multiplier) darts, handing over after it
        unless `hand_over` is off for the last one."""

        async def apply() -> Game:
            async with database.session_scope() as session:
                game = await games.lock(session, game_id)
                assert game is not None
                for number, visit in enumerate(visits, start=1):
                    for value, multiplier in visit:
                        game.add_dart(Dart(value=value, multiplier=multiplier))
                    if hand_over or number < len(visits):
                        game.next_player()
                await games.save(session, game)
                return game

        return self.run(apply)

    def age_game(self, game_id: str, hours: int) -> None:
        """Move a game's last change into the past, as if nobody had touched it since."""
        self.sql(
            "UPDATE games SET updated_at = now() - make_interval(hours => :hours),"
            " created_at = now() - make_interval(hours => :hours) WHERE id = :id",
            hours=hours,
            id=game_id,
        )


def alembic_config() -> Config:
    return Config(str(ALEMBIC_INI))


def token_in(mail: EmailMessage) -> str:
    """The token of the link in an account mail."""
    body = mail.get_body(preferencelist=("plain",))
    assert body is not None
    match = _TOKEN.search(body.get_content())
    assert match is not None, body.get_content()
    return match.group(1)
