"""Deletes the kept frames of games that no longer keep them: queued ones, and
those past the retention period."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.api.features.evaluation.persistence.frame_deletion_repository import repository
from app.api.features.evaluation.services import frame_store
from app.infrastructure import database
from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)

# Seconds between two sweeps when nothing wakes the sweeper earlier.
_INTERVAL = 3600

_wake = asyncio.Event()
# One sweep at a time, so two never delete the same folder at once.
_sweeping = asyncio.Lock()


def wake() -> None:
    """Sweep now rather than at the next interval, after a deletion was queued."""
    _wake.set()


async def sweep() -> int:
    """Expire old frames and delete everything queued; returns the games swept."""
    async with _sweeping:
        return await _sweep()


async def _sweep() -> int:
    retention = get_settings().frame_retention_days
    swept = 0
    async with database.session_scope() as session:
        if retention > 0:
            await repository.expire(session, datetime.now(UTC) - timedelta(days=retention))
    while True:
        async with database.session_scope() as session:
            game_ids = await repository.pending(session)
        if not game_ids:
            return swept
        for game_id in game_ids:
            await asyncio.to_thread(frame_store.delete, game_id)
        async with database.session_scope() as session:
            await repository.done(session, game_ids)
        swept += len(game_ids)


async def run() -> None:
    """Sweep every interval and whenever woken, until cancelled."""
    while True:
        try:
            await sweep()
        except Exception:  # noqa: BLE001 - the next sweep tries again
            logger.exception("[evaluation] frame sweep failed")
        try:
            await asyncio.wait_for(_wake.wait(), _INTERVAL)
        except TimeoutError:
            pass
        _wake.clear()
