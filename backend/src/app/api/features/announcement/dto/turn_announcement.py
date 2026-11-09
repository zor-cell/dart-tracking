from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.announcement.domain.calls import TurnCall


class TurnAnnouncementDto(CamelModel):
    """Server -> announcer: the next visit is ready to be thrown by `player`.
    `score` is the number the scoreboard shows for them."""

    type: Literal["turn_announcement"] = "turn_announcement"
    player: str
    score: int
    clips: list[str]

    @classmethod
    def from_entity(cls, call: TurnCall, clips: list[str]) -> Self:
        return cls(player=call.player, score=call.score, clips=clips)
