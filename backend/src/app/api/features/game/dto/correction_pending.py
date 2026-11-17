from typing import Annotated, Literal, Self

from pydantic import Field

from app.api.core.dto.base import CamelModel
from app.api.features.game.domain.correction_consequence import CorrectionConsequence
from app.api.features.game.domain.game import Game
from app.api.features.game.dto.command.move_dart import MoveDartDto
from app.api.features.game.dto.command.remove_dart import RemoveDartDto
from app.api.features.game.dto.command.replace_dart import ReplaceDartDto

type Correction = Annotated[
    ReplaceDartDto | RemoveDartDto | MoveDartDto, Field(discriminator="type")
]


class CorrectionPendingDto(CamelModel):
    """Server -> client: a correction in a closed visit that waits for the device
    that sent it to accept what it changes; sent back confirmed, it is booked."""

    type: Literal["correction_pending"] = "correction_pending"
    command: Correction
    # The visit, from 0, that now wins the game, and who wins it; None without a win.
    won_at: int | None
    winner_id: int | None
    # Visits thrown after the winning one, which the win drops.
    dropped: int
    # Players now out or placed before visits they threw.
    out_ids: list[int]

    @classmethod
    def from_entity(cls, consequence: CorrectionConsequence, game: Game, command: Correction) -> Self:
        won_at = consequence.won_at
        return cls(
            command=command,
            won_at=won_at,
            winner_id=consequence.winner_id,
            dropped=0 if won_at is None else len(game.turns) - 1 - won_at,
            out_ids=list(consequence.out),
        )
