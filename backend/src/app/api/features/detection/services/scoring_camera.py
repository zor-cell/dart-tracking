"""Which camera's detections are booked on the game: the first to calibrate claims
it until it stops being a camera; the others still detect. Stored in Redis.
"""

from app.infrastructure import redis_client

# Matches the calibration's lifetime: the claim is made on a calibration and is
# worthless without one. Renewed on every read.
_TTL_SECONDS = 24 * 60 * 60


def _key(game_id: str) -> str:
    return f"game:{game_id}:scoring_camera"


class ScoringCameraStore:
    async def claim(self, game_id: str, client_id: str) -> bool:
        """Try to become the game's scoring camera with an atomic `SET NX`; returns whether
        this device holds it, idempotently for the holder.
        """
        claimed = await redis_client.client().set(
            _key(game_id), client_id, nx=True, ex=_TTL_SECONDS
        )
        return bool(claimed) or await self.is_scoring(game_id, client_id)

    async def release(self, game_id: str, client_id: str) -> None:
        """Give up the scoring role, if this camera holds it."""
        if await self.is_scoring(game_id, client_id):
            await redis_client.client().delete(_key(game_id))

    async def is_scoring(self, game_id: str, client_id: str) -> bool:
        holder = await self.holder(game_id)
        return holder is not None and holder == client_id

    async def holder(self, game_id: str) -> str | None:
        """Which camera scores this game, if one has claimed it."""
        holder = await redis_client.client().getex(_key(game_id), ex=_TTL_SECONDS)
        return None if holder is None else holder.decode()


store = ScoringCameraStore()
