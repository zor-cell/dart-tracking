from app.api.features.game.dto.game_state import GameStateDto


class GameCreatedDto(GameStateDto):
    """A new game's state; an anonymous one also carries the token that can claim it later."""

    claim_token: str | None = None
