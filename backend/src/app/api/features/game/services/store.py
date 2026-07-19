"""In-memory game store and DTO mapping.

State lives in a process-local dict: lost on restart, not shared across worker
processes — fine for the single-worker dev/RPi setup; Postgres comes later. The
server is the source of truth, since scores originate from the vision pipeline.
"""

from uuid import uuid4

from app.api.features.game.dto.game_state import GameStateResponse
from app.api.features.game.dto.player_state import PlayerState
from app.api.features.game.entity.game import Game, Player


class GameStore:
    def __init__(self) -> None:
        self._games: dict[str, Game] = {}

    def create(self, mode: int, player_names: list[str]) -> Game:
        players = [
            Player(id=index, name=name, remaining=mode)
            for index, name in enumerate(name.strip() for name in player_names if name.strip())
        ]
        game = Game(id=uuid4().hex, mode=mode, players=players)
        self._games[game.id] = game
        return game

    def get(self, game_id: str) -> Game | None:
        return self._games.get(game_id)


# Module-level singleton store.
store = GameStore()


def to_response(game: Game) -> GameStateResponse:
    return GameStateResponse(
        id=game.id,
        mode=game.mode,
        players=[
            PlayerState(id=player.id, name=player.name, remaining=player.remaining)
            for player in game.players
        ],
        current_player_index=game.current_player_index,
        darts_this_turn=list(game.darts_this_turn),
        darts_remaining=game.darts_remaining,
        winner_id=game.winner.id if game.winner is not None else None,
    )
