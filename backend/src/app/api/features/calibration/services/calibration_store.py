"""Redis-backed calibration store, keyed by game and camera.

Kept alongside the game rather than on the WebSocket connection: a calibration
outlives any single socket (a reconnecting client must not have to re-aim the
camera). It is per **camera in a position**, though, not per game — two phones
filming the same board from two angles have nothing in common to share, so the
client id is part of the key (see docs/feature/multi-device.md §5).

Stored as JSON rather than pickled: readable in `redis-cli`, and a shared store
must never be a source of arbitrary objects to unpickle.
"""

import json

import numpy as np

from app.api.features.calibration.domain.calibration import Calibration
from app.infrastructure import redis_client

# Long enough to survive a paused game; renewed on every read.
_TTL_SECONDS = 24 * 60 * 60


def _key(game_id: str, client_id: str) -> str:
    return f"game:{game_id}:calibration:{client_id}"


class CalibrationStore:
    async def set(self, game_id: str, client_id: str, calibration: Calibration) -> None:
        """Store a calibration, replacing this camera's earlier one for the game."""
        payload = json.dumps(
            {
                "homography": calibration.homography.tolist(),
                "image_width": calibration.image_width,
                "image_height": calibration.image_height,
            }
        )
        await redis_client.client().set(_key(game_id, client_id), payload, ex=_TTL_SECONDS)

    async def get(self, game_id: str, client_id: str) -> Calibration | None:
        raw = await redis_client.client().getex(_key(game_id, client_id), ex=_TTL_SECONDS)
        if raw is None:
            return None

        data = json.loads(raw)
        return Calibration(
            homography=np.asarray(data["homography"], dtype=np.float64),
            image_width=data["image_width"],
            image_height=data["image_height"],
        )


store = CalibrationStore()
