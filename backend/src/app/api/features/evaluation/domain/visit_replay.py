"""Rebuilds the visits of a game from its event log.

Replays register/undo/removal/handover exactly as `Game` applies them, but keeps a
second list per visit that undo never touches: what the camera claimed.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.api.features.evaluation.domain.game_event import (
    GameEvent,
    GameEventKind,
)


@dataclass
class Visit:
    """One trip to the oche, from both sides: every dart the camera booked into
    it — the ones taken back again included — and the darts standing at the end,
    which is what the players signed off on."""

    turn_index: int
    player_index: int
    claimed: list[GameEvent] = field(default_factory=list)
    accepted: list[GameEvent] = field(default_factory=list)
    attempts: int = 0  # detections tried, successful or not
    corrected: bool = False
    camera_armed: bool = False

    @property
    def tracked(self) -> bool:
        """Whether this visit says anything about the tracker. A visit nobody
        filmed would otherwise read as three darts it failed to see."""
        return self.camera_armed or self.attempts > 0 or bool(self.claimed)


def replay(events: Iterable[GameEvent]) -> list[Visit]:
    """The visits of one game, in order.

    Addressed by slot, not identity: undoing across a handover drops the open
    visit, and the next handover reopens that slot for the same throws.
    """
    claimed: dict[int, list[GameEvent]] = defaultdict(list)
    accepted: dict[int, list[GameEvent]] = defaultdict(list)
    attempts: dict[int, int] = defaultdict(int)
    corrected: dict[int, bool] = defaultdict(bool)
    armed: dict[int, bool] = defaultdict(bool)
    players: dict[int, int] = {}

    open_index = 0
    for event in events:
        players.setdefault(open_index, event.player_index)

        match event.kind:
            case GameEventKind.DETECTION_FAILED:
                attempts[open_index] += 1
            case GameEventKind.DETECTED:
                attempts[open_index] += 1
                if event.accepted:
                    claimed[open_index].append(event)
                    accepted[open_index].append(event)
            case GameEventKind.MANUAL:
                if event.accepted:
                    accepted[open_index].append(event)
                    corrected[open_index] = True
            case GameEventKind.UNDO if event.accepted:
                open_index = _undo(accepted, corrected, open_index)
            case GameEventKind.DART_REMOVED if event.accepted:
                if event.dart_index is not None and event.dart_index < len(accepted[open_index]):
                    accepted[open_index].pop(event.dart_index)
                corrected[open_index] = True
            case GameEventKind.NEXT_PLAYER if event.accepted:
                # The event carries the player who just finished, so the
                # new slot's owner is left to the first event that lands in it.
                open_index += 1
                armed[open_index] = event.camera_armed

    return [
        Visit(
            turn_index=index,
            player_index=players[index],
            claimed=claimed[index],
            accepted=accepted[index],
            attempts=attempts[index],
            corrected=corrected[index],
            camera_armed=armed[index],
        )
        for index in sorted(players)
    ]


def _undo(
    accepted: dict[int, list[GameEvent]], corrected: dict[int, bool], open_index: int
) -> int:
    """Take back the last dart, across visit boundaries — `Game.undo`'s rule:
    an empty visit holds nothing to take back, so it is dropped and the previous
    visit's last dart goes instead."""
    while True:
        corrected[open_index] = True
        if accepted[open_index]:
            accepted[open_index].pop()
            return open_index
        if open_index == 0:
            return 0
        open_index -= 1
