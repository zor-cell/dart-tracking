"""Shared plumbing for the calibration and detection scripts.

The folder walking, the client replay (downscale + JPEG, so the pipeline sees what
it would receive live) and the report rendering — everything the `run_all` and
`run_debug` scripts have in common; only the pipeline they run differs. Batch runs
write to `_results`, debug runs to a separate `_results_debug`, kept apart so a
batch run's wipe does not take the debug dumps with it.
"""

import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, TypeVar

import cv2
import numpy as np

T = TypeVar("T")

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Folders under a test tree that hold outputs, not inputs — never walked, or a
# run would re-ingest its own annotated copies, the per-stage debug dumps, or the
# socket's debug dumps.
_EXCLUDED_DIRS = frozenset({"_results", "_results_debug", "_socket_debug"})

# The browser captures at most this edge length and re-encodes as JPEG; replaying
# it here keeps the tests honest about what the pipeline actually receives.
CAPTURE_MAX_EDGE = 1280
CAPTURE_JPEG_QUALITY = 85


def as_client_would_send(image: np.ndarray) -> np.ndarray:
    """Downscale and re-encode a photo the way the browser would.

    One already within the capture size is handed back untouched: it is what the
    client sends, and a second q85 pass is loss the pipeline never sees live.
    """
    height, width = image.shape[:2]
    scale = CAPTURE_MAX_EDGE / max(height, width)
    if scale >= 1:
        return image

    image = cv2.resize(
        image,
        (round(width * scale), round(height * scale)),
        interpolation=cv2.INTER_AREA,
    )
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, CAPTURE_JPEG_QUALITY])
    if not ok:
        return image
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def load_image(path: Path, raw: bool) -> np.ndarray | None:
    """Read a photo, replaying the client's downscale/JPEG unless `raw`."""
    image = cv2.imread(str(path))
    if image is None:
        return None
    return image if raw else as_client_would_send(image)


def collect_images(root: Path, out_dir: Path) -> list[Path]:
    """Every input photo under `root`, recursively, in sorted order.

    Skips `out_dir` and the results/debug folders, so a run never re-ingests its
    own annotated copies.
    """
    images = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if out_dir in path.parents:
            continue
        if _EXCLUDED_DIRS & set(path.relative_to(root).parts):
            continue
        images.append(path)
    return images


def mirrored_dir(path: Path, root: Path, out_dir: Path) -> Path:
    """The output subfolder for `path`, mirroring its place under `root` (created)."""
    target = out_dir / path.parent.relative_to(root)
    target.mkdir(parents=True, exist_ok=True)
    return target


def clear_results(out_dir: Path, root: Path) -> None:
    """Wipe the entire results tree before a run, then leave it recreated empty.

    Whole tree, not files of one suffix: otherwise a renamed throw keeps its old
    overlay and the folder no longer shows *this* run alone. Refuses if `out_dir`
    is the input root or an ancestor of it, which would take the photos with it.
    """
    out_dir = out_dir.resolve()
    root = root.resolve()
    if out_dir == root or out_dir in root.parents:
        raise ValueError(
            f"refusing to clear {out_dir}: it contains the input photos ({root}). "
            "Point --out at a dedicated results folder."
        )
    if out_dir.is_dir():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)


def debug_dir(input_path: Path, test_root: Path, out_override: Path | None) -> Path:
    """Where a `run_debug` run writes its per-stage images for `input_path`.

    Mirrors the input's setup subfolder under `_results_debug`, so `pz_setup/center.jpg`
    becomes `_results_debug/pz_setup/center`. An explicit `--out` wins; an input
    outside the test tree falls back to a `_results_debug` beside it.
    """
    if out_override is not None:
        return out_override

    input_path = input_path.resolve()
    test_root = test_root.resolve()
    if test_root in input_path.parents:
        relative = input_path.parent.relative_to(test_root)
        return test_root / "_results_debug" / relative / input_path.stem
    return input_path.parent / "_results_debug" / input_path.stem


def setup_of(key: str) -> str:
    """The capture setup a series/image belongs to: its top-level folder.

    Keys are paths relative to the test root, so the first component is the setup.
    A key with no folder is ".".
    """
    return key.split("/")[0] if "/" in key else "."


def location_of(key: str) -> str:
    """The physical board a series/image belongs to.

    A setup folder is named `<board>_setup<n>` — board first, so the part before
    the first underscore is the board (`pz` across `pz_setup1`..`pz_setup4`).
    `setup1_pz` would group by setup number instead, hence the naming order.
    """
    return setup_of(key).split("_")[0]


def rate_table(
    items: list[T],
    key: Callable[[T], str],
    hit: Callable[[T], bool],
    header: str,
    hit_label: str = "ok",
) -> list[str]:
    """A `| header | hit_label | total | rate |` table, grouped by `key`.

    One row per group: how many of its items satisfy `hit`, as a percentage.
    Best rate first, so the groups that need work sit at the bottom where the
    eye lands last; name breaks ties to keep the order stable between runs.
    """
    groups: dict[str, list[T]] = defaultdict(list)
    for item in items:
        groups[key(item)].append(item)

    rows = []
    for name, group in groups.items():
        hits = sum(1 for item in group if hit(item))
        rows.append((hits / len(group), name, hits, len(group)))
    rows.sort(key=lambda row: (-row[0], row[1]))

    lines = [f"| {header} | {hit_label} | total | rate |", "|---|---|---|---|"]
    lines += [f"| {name} | {hits} | {total} | {100 * rate:.0f}% |" for rate, name, hits, total in rows]
    return lines


def count_table(items: list[T], key: Callable[[T], str], header: str) -> list[str]:
    """A `| header | count |` table over `items`, most frequent group first."""
    counts = Counter(key(item) for item in items)
    lines = [f"| {header} | count |", "|---|---|"]
    for name, total in counts.most_common():
        lines.append(f"| {name} | {total} |")
    return lines


def write_markdown(out_dir: Path, name: str, lines: list[str]) -> Path:
    """Write report lines as a Markdown file under `out_dir` and return its path."""
    path = out_dir / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
