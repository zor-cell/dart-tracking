"""Redis-backed record of which device made a game's latest run of changes, so a
command made against a state another device has since changed can be refused."""

from app.infrastructure import redis_client

# Same lifetime as the other game-scoped keys; renewed on every write.
_TTL_SECONDS = 24 * 60 * 60


def _key(game_id: str) -> str:
    return f"game:{game_id}:writer"


class WriterStore:
    async def admits(self, game_id: str, client_id: str, seen: int | None, current: int) -> bool:
        """Whether a command made against revision `seen` may apply at `current`:
        nothing changed since, or only this device's own earlier commands did."""
        if seen is None or seen == current:
            return True
        writer = await self._writer(game_id)
        return writer is not None and writer[0] == client_id and writer[1] <= seen < current

    async def note(self, game_id: str, client_id: str, before: int) -> None:
        """Record that `client_id` just changed the game away from revision `before`."""
        writer = await self._writer(game_id)
        since = writer[1] if writer is not None and writer[0] == client_id else before
        await redis_client.client().set(_key(game_id), f"{since}:{client_id}", ex=_TTL_SECONDS)

    async def _writer(self, game_id: str) -> tuple[str, int] | None:
        """The device of the latest run of changes and the revision it started from."""
        raw = await redis_client.client().get(_key(game_id))
        if raw is None:
            return None
        since, client_id = raw.decode().split(":", 1)
        return client_id, int(since)


store = WriterStore()
