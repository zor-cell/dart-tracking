"""In-memory game store.

State lives in a process-local dict: lost on restart, not shared across worker
processes — fine for the single-worker dev/RPi setup; Postgres comes later. The
server is the source of truth, since scores originate from the vision pipeline.
"""

from uuid import uuid4

from app.api.features.game.entity.game import Game
from app.api.features.game.entity.game_mode import GameMode
from app.api.features.game.entity.player import Player


class GameStore:
    def __init__(self) -> None:
        self._games: dict[str, Game] = {}

    def create(self, mode: GameMode, player_names: list[str]) -> Game:
        """Names are expected to be validated and non-empty (see the router)."""
        players = [Player(id=index, name=name) for index, name in enumerate(player_names)]
        game = Game(id=uuid4().hex, mode=mode, players=players)
        self._games[game.id] = game
        return game

    def get(self, game_id: str) -> Game | None:
        return self._games.get(game_id)


# Module-level singleton store.
store = GameStore()