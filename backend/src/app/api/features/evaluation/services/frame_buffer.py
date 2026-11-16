"""Holds the scoring camera's frames of the open visit, written out as a throw
series in a test run. Process-local.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)

# Recorded evaluation frames, one subfolder per game.
_EVALUATION_ROOT = Path(__file__).resolve().parents[6] / "testdata" / "evaluation"


class FrameKind(StrEnum):
    """Why a frame is part of a series. Every kind moved the reference forward."""

    BOOKED = "booked"  # a located dart the game took
    ABSORBED = "absorbed"  # no dart found, or the darts pulled: nothing new in it
    UNBOOKED = "unbooked"  # a located dart the game did not take (visit full)


def folder_of(game_id: str) -> Path:
    """Where a game's kept throw series live. The prefix names what the id is,
    and doubles as the runner's `<board>_setup<n>` split, so every recorded
    setup groups under `game`."""
    return _EVALUATION_ROOT / f"game_{game_id}"


def recorded_files(game_id: str) -> list[tuple[Path, str]]:
    """A game's recorded files with their archive path, `testdata/evaluation/game_<id>/…`,
    leaving out the runners' `_results` folders."""
    folder = folder_of(game_id)
    if not folder.is_dir():
        return []
    files = []
    for file in sorted(folder.rglob("*")):
        relative = file.relative_to(folder)
        if file.is_file() and not any(part.startswith("_") for part in relative.parts):
            files.append((file, (Path("testdata") / "evaluation" / folder.name / relative).as_posix()))
    return files


def series_name(turn_index: int) -> str:
    """What one visit's frames are called. Shared with the report, which has to
    label the very same files."""
    return f"throw{turn_index}"


def manifest_of(folder: Path, series: str) -> Path:
    """The file naming the kind of each frame in a series."""
    return folder / f"{series}_frames.txt"


def read_manifest(folder: Path, series: str) -> list[FrameKind] | None:
    """The kinds of a series' frames in order, or None for a series written
    before manifests existed."""
    path = manifest_of(folder, series)
    if not path.is_file():
        return None
    return [FrameKind(line.split()[1]) for line in path.read_text().splitlines() if line.strip()]


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

    async def flush(self, game_id: str, turn_index: int, *, keep: bool = False) -> Path | None:
        """Write the open visit as `throwN_base.jpg` and `throwN_dartK.jpg` with its
        manifest and trigger episodes; returns the folder, or None if empty.
        `keep` leaves the visit open.
        """
        visit = self._visits.get(game_id) if keep else self._visits.pop(game_id, None)
        if visit is None or visit.base is None or not visit.frames:
            return None

        async with self._writing:
            return await asyncio.to_thread(
                _write_series, game_id, turn_index, visit.base, list(visit.frames)
            )


def _write_series(
    game_id: str,
    turn_index: int,
    base: bytes,
    frames: list[tuple[bytes, FrameKind, bytes | None]],
) -> Path | None:
    folder = folder_of(game_id)
    series = series_name(turn_index)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        # A rewritten series may hold fewer frames than an earlier write.
        for pattern in (f"{series}_dart*.jpg", f"{series}_dart*_trigger.json"):
            for stale in folder.glob(pattern):
                stale.unlink()
        (folder / f"{series}_base.jpg").write_bytes(base)
        lines = []
        for index, (jpeg, kind, trigger) in enumerate(frames, start=1):
            (folder / f"{series}_dart{index}.jpg").write_bytes(jpeg)
            if trigger is not None:
                (folder / f"{series}_dart{index}_trigger.json").write_bytes(trigger)
            lines.append(f"dart{index} {kind}")
        manifest_of(folder, series).write_text("\n".join(lines) + "\n")
    except OSError:
        logger.exception("[evaluation] could not write frames for %s", game_id)
        return None

    logger.info(
        "[evaluation] wrote %d frame(s) of turn %d to %s",
        len(frames) + 1,
        turn_index,
        folder,
    )
    return folder


def write_failed_calibration(game_id: str, jpeg: bytes, failure: str) -> Path | None:
    """Write a calibration shot the board was not found in, beside the game's
    throw series. Returns the file, or None when it could not be written."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_%f")
    path = folder_of(game_id) / f"calibration_{stamp}_{failure}.jpg"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(jpeg)
    except OSError:
        logger.exception("[evaluation] could not write a failed calibration for %s", game_id)
        return None
    logger.info("[evaluation] wrote failed calibration to %s", path)
    return path


store = FrameBuffer()
