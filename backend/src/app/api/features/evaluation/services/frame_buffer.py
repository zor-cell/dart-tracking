"""Holds the scoring camera's frames of the open visit.

An accepted visit is thrown away, a corrected one written out as a throw series
(docs/feature/auswertung.md §4). Process-local, about a megabyte per game.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Among the recorded test data, so `scripts/detection/run_all.py` walks it. One
# folder per game, named for the runner's `<board>_setup<n>` convention: every
# live capture groups under the board `live`, each game its own setup.
_LIVE_ROOT = Path(__file__).resolve().parents[6] / "testdata" / "detection"


def folder_of(game_id: str) -> Path:
    """Where a game's kept throw series live."""
    return _LIVE_ROOT / f"live_{game_id}"


@dataclass
class _Visit:
    base: bytes | None = None
    throws: list[bytes] = field(default_factory=list)


class FrameBuffer:
    def __init__(self) -> None:
        # The camera's last frame, which is the base image of the next visit.
        self._previous: dict[str, bytes] = {}
        self._visits: dict[str, _Visit] = {}
        # Games whose open visit the players have touched by hand.
        self._corrected: set[str] = set()

    def remember(self, game_id: str, jpeg: bytes) -> None:
        """Note a frame that opens a visit rather than belonging to one — the
        calibration shot of the empty board."""
        self._previous[game_id] = jpeg

    def add_throw(self, game_id: str, jpeg: bytes) -> None:
        """Add a located throw to the open visit.

        Scored frames only: a failed detection leaves the reference where it
        was, so a series holding it would chain differently offline.
        """
        visit = self._visits.setdefault(game_id, _Visit())
        if visit.base is None:
            visit.base = self._previous.get(game_id)
        visit.throws.append(jpeg)
        self._previous[game_id] = jpeg

    def mark_corrected(self, game_id: str) -> None:
        """Note that the open visit was undone or entered by hand — the only
        visits whose frames are worth keeping."""
        self._corrected.add(game_id)

    def was_corrected(self, game_id: str) -> bool:
        return game_id in self._corrected

    def discard(self, game_id: str) -> None:
        self._visits.pop(game_id, None)
        self._corrected.discard(game_id)

    def forget(self, game_id: str) -> None:
        """Drop everything held for a game."""
        self._previous.pop(game_id, None)
        self.discard(game_id)

    def flush(self, game_id: str, turn_index: int) -> Path | None:
        """Write the open visit as `turnNNN_base.jpg` + `turnNNN_dartK.jpg` and
        clear it. Returns the folder, or None when there was nothing to write.

        The `ground_truth.txt` is the report script's job: which frame carries
        which label only follows from the alignment.
        """
        visit = self._visits.pop(game_id, None)
        self._corrected.discard(game_id)
        if visit is None or visit.base is None or not visit.throws:
            return None

        folder = folder_of(game_id)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            series = f"turn{turn_index:03d}"
            (folder / f"{series}_base.jpg").write_bytes(visit.base)
            for index, throw in enumerate(visit.throws, start=1):
                (folder / f"{series}_dart{index}.jpg").write_bytes(throw)
        except OSError:
            logger.exception("[evaluation] could not write frames for %s", game_id)
            return None

        logger.info(
            "[evaluation] wrote %d frame(s) of turn %d to %s",
            len(visit.throws) + 1,
            turn_index,
            folder,
        )
        return folder


store = FrameBuffer()
