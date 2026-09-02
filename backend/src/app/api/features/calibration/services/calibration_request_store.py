"""Who asked the game's cameras to recalibrate, and is waiting to hear back.

Redis-backed. See docs/feature/multi-device.md §5c.
"""

from app.infrastructure import redis_client

# A pending request belongs to one visit. Deliberately not renewed on read: an
# answer nobody is waiting for any more should age out.
_TTL_SECONDS = 60 * 60


def _key(game_id: str) -> str:
    return f"game:{game_id}:calibration_request"


class CalibrationRequestStore:
    async def set(self, game_id: str, client_id: str) -> None:
        await redis_client.client().set(_key(game_id), client_id, ex=_TTL_SECONDS)

    async def clear(self, game_id: str) -> None:
        await redis_client.client().delete(_key(game_id))

    async def get(self, game_id: str) -> str | None:
        """Not cleared when a camera answers — a game may be filmed by several.
        The next automatic recalibration drops it."""
        requester = await redis_client.client().get(_key(game_id))
        return requester.decode() if requester is not None else None


store = CalibrationRequestStore()
