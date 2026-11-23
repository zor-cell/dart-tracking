"""Holds the scoring camera's frames of the open visit, written out as a throw
series when the game keeps its frames. Process-local.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from app.api.features.evaluation.services.frame_store import FrameStore, store as frame_store

logger = logging.getLogger(__name__)


class FrameKind(StrEnum):
    """Why a frame is part of a series. Every kind moved the reference forward."""

    BOOKED = "booked"  # a located dart the game took
    ABSORBED = "absorbed"  # no dart found, or the darts pulled: nothing new in it
    UNBOOKED = "unbooked"  # a located dart the game did not take (visit full)


def series_name(turn_index: int) -> str:
    """What one visit's frames are called. Shared with the report, which has to
    label the very same files."""
    return f"throw{turn_index}"


def manifest_name(series: str) -> str:
    """The file naming the kind of each frame in a series."""
    return f"{series}_frames.txt"


def read_manifest(files: FrameStore, game_id: str, series: str) -> list[FrameKind] | None:
    """The kinds of a series' frames in order, or None for a series written
    before manifests existed."""
    text = files.read(game_id, manifest_name(series))
    if text is None:
        return None
    return [FrameKind(line.split()[1]) for line in text.decode().splitlines() if line.strip()]


@dataclass
class _Visit:
    base: bytes | None = None
    # JPEG, why it is kept, and the client's trigger episode as JSON if it sent one.
    frames: list[tuple[bytes, FrameKind, bytes | None]] = field(default_factory=list)


class FrameBuffer:
    def __init__(self) -> None:
        # The camera's last frame, which is the base image of the next visit.
        self._previous: dict[str, bytes] = {}
        self._visits: dict[str, _Visit] = {}
        # One write at a time, in the order they were asked for.
        self._writing = asyncio.Lock()

    def remember(self, game_id: str, jpeg: bytes) -> None:
        """Note a frame that opens a visit rather than belonging to one — the
        calibration shot of the empty board."""
        self._previous[game_id] = jpeg

    def add(self, game_id: str, jpeg: bytes, kind: FrameKind, trigger: bytes | None = None) -> None:
        """Add a frame that moved the camera's reference forward."""
        visit = self._visits.setdefault(game_id, _Visit())
        if visit.base is None:
            visit.base = self._previous.get(game_id)
        visit.frames.append((jpeg, kind, trigger))
        self._previous[game_id] = jpeg

    def discard(self, game_id: str) -> None:
        self._visits.pop(game_id, None)

    def forget(self, game_id: str) -> None:
        """Drop everything held for a game."""
        self._previous.pop(game_id, None)
        self.discard(game_id)

    async def flush(self, game_id: str, turn_index: int, *, keep: bool = False) -> bool:
        """Write the open visit as `throwN_base.jpg` and `throwN_dartK.jpg`, exactly as
        sent, with its manifest and trigger episodes; whether anything was written.
        `keep` leaves the visit open.
        """
        visit = self._visits.get(game_id) if keep else self._visits.pop(game_id, None)
        if visit is None or visit.base is None or not visit.frames:
            return False

        async with self._writing:
            return await asyncio.to_thread(
                _write_series, game_id, turn_index, visit.base, list(visit.frames)
            )


def _write_series(
    game_id: str,
    turn_index: int,
    base: bytes,
    frames: list[tuple[bytes, FrameKind, bytes | None]],
) -> bool:
    files = frame_store()
    series = series_name(turn_index)
    try:
        # A rewritten series may hold fewer frames than an earlier write.
        stale = [name for name in files.names(game_id) if name.startswith(f"{series}_dart")]
        files.remove(game_id, stale)
        files.write(game_id, f"{series}_base.jpg", base)
        lines = []
        for index, (jpeg, kind, trigger) in enumerate(frames, start=1):
            files.write(game_id, f"{series}_dart{index}.jpg", jpeg)
            if trigger is not None:
                files.write(game_id, f"{series}_dart{index}_trigger.json", trigger)
            lines.append(f"dart{index} {kind}")
        files.write(game_id, manifest_name(series), ("\n".join(lines) + "\n").encode())
    except Exception:  # noqa: BLE001 - diagnostics must not break the game
        logger.exception("[evaluation] could not write frames for %s", game_id)
        return False

    logger.info("[evaluation] wrote %d frame(s) of turn %d of %s", len(frames) + 1, turn_index, game_id)
    return True


def write_failed_calibration(game_id: str, jpeg: bytes, failure: str) -> str | None:
    """Write a calibration shot the board was not found in, beside the game's
    throw series. Returns its name, or None when it could not be written."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_%f")
    name = f"calibration_{stamp}_{failure}.jpg"
    try:
        frame_store().write(game_id, name, jpeg)
    except Exception:  # noqa: BLE001 - diagnostics must not break the game
        logger.exception("[evaluation] could not write a failed calibration for %s", game_id)
        return None
    logger.info("[evaluation] wrote failed calibration %s of %s", name, game_id)
    return name


store = FrameBuffer()
