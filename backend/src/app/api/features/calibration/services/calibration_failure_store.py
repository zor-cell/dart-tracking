"""Whether the scoring camera's latest calibration attempt failed.

Redis-backed. See docs/feature/done/multi-device.md §5c.
"""

from app.infrastructure import redis_client

# Matches the scoring claim's lifetime, which this flag qualifies.
_TTL_SECONDS = 24 * 60 * 60


def _key(game_id: str) -> str:
    return f"game:{game_id}:calibration_failed"


class CalibrationFailureStore:
    async def set(self, game_id: str) -> None:
        await redis_client.client().set(_key(game_id), 1, ex=_TTL_SECONDS)

    async def clear(self, game_id: str) -> None:
        await redis_client.client().delete(_key(game_id))

    async def failed(self, game_id: str) -> bool:
        return bool(await redis_client.client().exists(_key(game_id)))


store = CalibrationFailureStore()
