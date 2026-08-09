"""Which camera's detections are booked on the game.

A game may be filmed by several cameras, but a throw happens once. Without a
rule, every camera that sees it calls `register_dart` and the visit fills up at
twice the rate — silently, because a dart past the third is absorbed rather than
refused. So exactly one camera per game scores; the others detect, answer their
own `detection_result`, and roll their own reference frame forward.

That is deliberately not fusion. Merging two views of the same throw into one
better estimate is the open research question (see docs/feature/multi-device.md
§5); this is what makes running two cameras possible without it, and it yields
the pairs of independent observations that studying it needs.

**The claim is made on a successful calibration** — the first moment a camera
can actually detect anything — and is never released. A camera that drops and
comes back brings the same client id and keeps it, which is the point: handing
scoring over mid-visit would let a flapping connection book the throw in flight
twice. The cost is that a game whose scoring camera never returns stops being
scored automatically, exactly as a single-camera game would.

Process-local, lost on restart, like every other store here.
"""


class ScoringCameraStore:
    def __init__(self) -> None:
        self._cameras: dict[str, str] = {}

    def claim(self, game_id: str, client_id: str) -> bool:
        """Try to become the game's scoring camera; whether this device now is.

        Idempotent for the holder, so re-calibrating or reconnecting keeps it.
        """
        return self._cameras.setdefault(game_id, client_id) == client_id

    def is_scoring(self, game_id: str, client_id: str) -> bool:
        return self._cameras.get(game_id) == client_id


store = ScoringCameraStore()
