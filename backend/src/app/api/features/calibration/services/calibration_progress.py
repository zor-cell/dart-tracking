"""Which games have a calibration attempt in flight.

Process-local, like the hub: an attempt ends on a timer, and a timer lives here.
"""

import asyncio
from collections.abc import Awaitable, Callable

# How long an attempt may stay unanswered before it no longer counts, in seconds.
_TIMEOUT_SECONDS = 8.0


class CalibrationProgress:
    def __init__(self) -> None:
        self._timers: dict[str, asyncio.Task[None]] = {}

    def start(self, game_id: str, on_timeout: Callable[[], Awaitable[None]]) -> bool:
        """Mark an attempt as running and restart its timer; whether none was before."""
        was_running = self.running(game_id)
        self._cancel(game_id)
        self._timers[game_id] = asyncio.create_task(self._expire(game_id, on_timeout))
        return not was_running

    def finish(self, game_id: str) -> None:
        self._cancel(game_id)

    def running(self, game_id: str) -> bool:
        return game_id in self._timers

    async def _expire(self, game_id: str, on_timeout: Callable[[], Awaitable[None]]) -> None:
        await asyncio.sleep(_TIMEOUT_SECONDS)
        self._timers.pop(game_id, None)
        await on_timeout()

    def _cancel(self, game_id: str) -> None:
        timer = self._timers.pop(game_id, None)
        if timer is not None:
            timer.cancel()


progress = CalibrationProgress()
