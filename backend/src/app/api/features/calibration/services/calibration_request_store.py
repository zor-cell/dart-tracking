"""Who asked the game's cameras to calibrate again, and is waiting to hear back.

A recalibration is performed by one device and asked for by another, so the
answer has no sender to return to. This is what remembers the address: the
device that issued `request_calibration` gets a `calibration_status` per camera
that answers; nobody else does.

Nobody else, specifically **not the camera that just calibrated** — it already
has the full `calibration_result`, and a second message would be the only thing
it hears. The client tracks the socket through a signal, which holds the latest
value rather than a queue, so two messages arriving in the same frame collapse
into one and the result is the one that gets lost.

An automatic recalibration (the end of a visit) has no requester at all and
clears whatever is stored: nobody asked, so nobody is waiting. A camera that
fails there still reports it on its own screen, which is where the board has to
be re-aimed anyway.

Process-local, lost on restart, like every other store here.
"""


class CalibrationRequestStore:
    def __init__(self) -> None:
        self._requesters: dict[str, str] = {}

    def set(self, game_id: str, client_id: str) -> None:
        """Note that this device is waiting for the game's cameras to answer."""
        self._requesters[game_id] = client_id

    def clear(self, game_id: str) -> None:
        self._requesters.pop(game_id, None)

    def get(self, game_id: str) -> str | None:
        """The device waiting on this game's cameras, if any.

        Not cleared when a camera answers: a game may be filmed by several, and
        the requester wants to hear from each. It is dropped by the next
        automatic recalibration instead, so a request nobody ever answered
        cannot outlive the visit it was made in.
        """
        return self._requesters.get(game_id)


store = CalibrationRequestStore()
