"""Which camera's detections are booked on the game.

A game may be filmed by several cameras, but a throw happens once. Without a
rule, every camera that sees it calls `register_dart` and the visit fills up at
twice the rate — silently, because a dart past the third is absorbed rather than
refused. So exactly one camera per game scores; the others detect, answer their
own `detection_result`, and roll their own reference frame forward.

That is deliberately not fusion. Merging two views of the same throw into one
better estimate is the open research question; this is what makes running two
cameras possible without it, and it yields the pairs of independent observations
that studying it needs.

**The claim is made on a successful calibration** — the first moment a camera
can actually detect anything — and is released only when the device stops being
a camera (`set_role`). A camera that drops and
comes back brings the same client id and keeps it, which is the point: handing
scoring over mid-visit would let a flapping connection book the throw in flight
twice. The cost is that a game whose scoring camera never returns stops being
scored automatically, exactly as a single-camera game would.

Redis-backed, so the claim also survives a server restart.
"""

from app.infrastructure import redis_client

# Matches the calibration's lifetime: the claim is made on a calibration and is
# worthless without one. Renewed on every read.
_TTL_SECONDS = 24 * 60 * 60


def _key(game_id: str) -> str:
    return f"game:{game_id}:scoring_camera"


class ScoringCameraStore:
    async def claim(self, game_id: str, client_id: str) -> bool:
        """Try to become the game's scoring camera; whether this device now is.

        `SET NX` is the atomic form of the old dict `setdefault`: exactly one of
        two cameras calibrating at the same moment can win, even across
        processes. Idempotent for the holder, so re-calibrating or reconnecting
        keeps it.
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
