"""Shared plumbing for the calibration and detection test scripts.

Both walk a folder of photos — now nested in per-setup subfolders — replay each
through the client's downscale + JPEG so the pipeline sees what it would receive
live, and write annotated copies into a `_results` tree that mirrors the input.
Only the pipeline they run and what they report differs; everything else is here.
"""

import shutil
from pathlib import Path

import cv2
import numpy as np

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Folders under a test tree that hold outputs, not inputs — never walked, or a
# run would re-ingest its own annotated copies (and the socket's debug dumps).
_EXCLUDED_DIRS = frozenset({"_results", "socket_debug"})

# The browser captures at most this edge length and re-encodes as JPEG; replaying
# it here keeps the tests honest about what the pipeline actually receives.
CAPTURE_MAX_EDGE = 1280
CAPTURE_JPEG_QUALITY = 85


def as_client_would_send(image: np.ndarray) -> np.ndarray:
    """Downscale and re-encode a photo the way the browser would."""
    height, width = image.shape[:2]
    scale = CAPTURE_MAX_EDGE / max(height, width)
    if scale < 1:
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

    Skips the output tree (`out_dir`) and any results/debug folders, so a run
    never re-ingests its own annotated copies.
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

    Clearing only files of one suffix left orphans behind: a renamed or deleted
    throw kept its old overlay, an emptied subfolder lingered, and a report from
    a wider previous run stayed put. Removing the whole tree is the only way the
    folder is guaranteed to show *this* run and nothing else.

    Guarded against a mis-pointed `--out`: if `out_dir` is the input root or an
    ancestor of it, wiping it would take the source photos with it, so refuse.
    The normal case — `root/_results` — is a child of `root` and always safe.
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
