"""Redis-backed store of the device a game's players picked as announcer."""

from app.infrastructure import redis_client

# Same lifetime as the other game-scoped keys; renewed on every read.
_TTL_SECONDS = 24 * 60 * 60


def _key(game_id: str) -> str:
    return f"game:{game_id}:announcer"


class AnnouncerStore:
    async def choose(self, game_id: str, client_id: str) -> None:
        await redis_client.client().set(_key(game_id), client_id, ex=_TTL_SECONDS)

    async def chosen(self, game_id: str) -> str | None:
        chosen = await redis_client.client().getex(_key(game_id), ex=_TTL_SECONDS)
        return None if chosen is None else chosen.decode()


store = AnnouncerStore()
