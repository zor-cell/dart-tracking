from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.dto.player import PlayerDto
from app.api.features.game.dto.turn import TurnDto
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_mode import GameMode


class GameStateDto(CamelModel):
    """The authoritative game state: both the answer to an HTTP call and the
    message pushed over the socket, so it looks the same however it arrived.

    Pushed right after connecting (a joining or reconnecting device is then in
    sync) and after every change any device makes.
    """

    type: Literal["game_state"] = "game_state"
    id: str
    # Version of this snapshot; rises with every state change (see Game).
    revision: int
    mode: GameMode
    checkout_mode: CheckoutMode
    players: list[PlayerDto]
    current_player_index: int
    turns: list[TurnDto]
    darts_remaining: int
    can_undo: bool
    winner_id: int | None
    # Suggested finish for the current player this turn, ordered as thrown, or
    # None when there is none within the remaining darts.
    checkout: list[str] | None

    @classmethod
    def from_entity(cls, game: Game) -> Self:
        return cls(
            id=game.id,
            revision=game.revision,
            mode=game.mode,
            checkout_mode=game.checkout_mode,
            players=[
                PlayerDto.from_entity(player, game.remaining(player.id), game.last_turn(player.id))
                for player in game.players
            ],
            current_player_index=game.current_player_index,
            turns=[TurnDto.from_entity(turn) for turn in game.turns],
            darts_remaining=game.darts_remaining,
            can_undo=game.can_undo,
            winner_id=game.winner.id if game.winner is not None else None,
            checkout=game.checkout,
        )
