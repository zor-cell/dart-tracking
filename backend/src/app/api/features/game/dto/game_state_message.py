from typing import Literal

from app.api.core.dto.base import CamelModel
from app.api.features.game.dto.game_state import GameStateDto


class GameStateMessage(CamelModel):
    """Server -> client: authoritative game state.

    Pushed right after connecting (so a (re-)connecting client is in sync —
    there is no separate WS-side session to persist, `game_id` in the URL is
    the only thing tying the socket to a game) and, once real dart scoring
    lands, again after every scored throw.
    """

    type: Literal["game_state"] = "game_state"
    state: GameStateDto
