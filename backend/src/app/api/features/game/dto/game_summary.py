from datetime import datetime
from typing import Self

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_status import GameStatus
from app.api.features.game.domain.game_summary import GameSummary, GameSummaryPlayer


class GameSummaryPlayerDto(CamelModel):
    name: str
    remaining: int
    is_me: bool

    @classmethod
    def from_entity(cls, player: GameSummaryPlayer) -> Self:
        return cls(name=player.name, remaining=player.remaining, is_me=player.is_me)


class GameSummaryDto(CamelModel):
    id: str
    mode: GameMode
    checkout_mode: CheckoutMode
    status: GameStatus
    players: list[GameSummaryPlayerDto]
    winner_index: int | None
    dart_count: int
    created_at: datetime
    # Whether this game moves the statistics — the same rule the dashboard
    # applies, so the two can never disagree.
    counted: bool

    @classmethod
    def from_entity(cls, summary: GameSummary) -> Self:
        return cls(
            id=summary.id,
            mode=summary.mode,
            checkout_mode=summary.checkout_mode,
            status=summary.status,
            players=[GameSummaryPlayerDto.from_entity(p) for p in summary.players],
            winner_index=summary.winner_index,
            dart_count=summary.dart_count,
            created_at=summary.created_at,
            counted=summary.counted,
        )
