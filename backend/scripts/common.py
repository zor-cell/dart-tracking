"""Shared plumbing for the calibration and detection test scripts.

Both walk a folder of photos — now nested in per-setup subfolders — replay each
through the client's downscale + JPEG so the pipeline sees what it would receive
live, and write annotated copies into a `_results` tree that mirrors the input.
Only the pipeline they run and what they report differs; everything else is here.
"""

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


def clear_overlays(out_dir: Path, suffix: str) -> None:
    """Delete stale annotated copies from a previous run, recursively.

    Or a photo that has since been renamed, or that now fails, leaves its old
    picture behind and the folder shows a result this run never produced.
    """
    if out_dir.is_dir():
        for stale in out_dir.rglob(f"*{suffix}"):
            stale.unlink()
