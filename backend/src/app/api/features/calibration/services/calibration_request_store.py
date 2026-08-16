"""Who asked the game's cameras to recalibrate, and is waiting to hear back.

Process-local, lost on restart. See docs/feature/multi-device.md §5c.
"""


class CalibrationRequestStore:
    def __init__(self) -> None:
        self._requesters: dict[str, str] = {}

    def set(self, game_id: str, client_id: str) -> None:
        self._requesters[game_id] = client_id

    def clear(self, game_id: str) -> None:
        self._requesters.pop(game_id, None)

    def get(self, game_id: str) -> str | None:
        """Not cleared when a camera answers — a game may be filmed by several.
        The next automatic recalibration drops it."""
        return self._requesters.get(game_id)


store = CalibrationRequestStore()
