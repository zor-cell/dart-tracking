from typing import Literal, Self

from app.api.core.dto.base import CamelModel
from app.api.features.announcement.domain.calls import DartCall


class DartAnnouncementDto(CamelModel):
    """Server -> announcer: a booked dart with the clips that call it.

    `visit_points` is set once the visit ends; `eliminated` names whom it sent to zero.
    """

    type: Literal["dart_announcement"] = "dart_announcement"
    value: int
    multiplier: int
    visit_points: int | None
    busted: bool
    won: bool
    eliminated: list[str]
    clips: list[str]

    @classmethod
    def from_entity(cls, call: DartCall, clips: list[str]) -> Self:
        return cls(
            value=call.value,
            multiplier=call.multiplier,
            visit_points=call.visit_points,
            busted=call.busted,
            won=call.won,
            eliminated=list(call.eliminated),
            clips=clips,
        )
