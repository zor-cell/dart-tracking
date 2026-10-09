"""Render the client-side trigger episode of one recorded throw as a thesis figure.

Reads `<series>_<dart>_trigger.json` as written in test runs, plus the throw frame
for its aspect ratio.

Usage:
    uv run --with matplotlib python scripts/figures/trigger_figure.py testdata/evaluation/game_<id> throw3 dart1
"""

import argparse
import base64
import json
from pathlib import Path

import cv2
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Rectangle

# TrueType rather than Type 3, which the thesis template's PDF/A profile rejects.
matplotlib.rcParams["pdf.fonttype"] = 42

_BACKEND = Path(__file__).resolve().parents[2]
_DEFAULT_OUT = _BACKEND.parents[1] / "thesis" / "graphics" / "figures" / "trigger.pdf"

# Cells over the ambient level that arm a throw (ARM_BLOCK_EXCESS in throw-detector.ts).
_ARM_EXCESS = 1

# Time shown before the first snapshot, in seconds.
_LEAD_IN_S = 0.6

BLACK = "#1c1c1c"
_STATE_COLOURS = {"motion": "#f4c27a", "settling": "#9cc8e8"}
_CHANGED = np.array([255, 120, 0], dtype=np.uint8)  # orange
_CELL = "#39ff14"
_MOMENT_TITLES = {"arm": "Arming", "peak": "Peak", "capture": "Capture"}


def _unpack(snapshot: dict) -> tuple[np.ndarray, np.ndarray]:
    """Luma and change mask of a snapshot as (height, width) arrays."""
    width, height = snapshot["width"], snapshot["height"]
    luma = np.frombuffer(base64.b64decode(snapshot["luma"]), np.uint8).reshape(height, width)
    bits = np.unpackbits(np.frombuffer(base64.b64decode(snapshot["changed"]), np.uint8))
    return luma, bits[: width * height].reshape(height, width).astype(bool)


def _state_runs(timeline: list[dict], capture_ms: float) -> list[tuple[str, float, float]]:
    """Contiguous runs of one state as (state, start s, end s), each frame half a step wide.

    The capturing frame is logged after the reset, so it closes the run before it."""
    times = [sample["tMs"] / 1000 for sample in timeline]
    step = np.median(np.diff(times)) if len(times) > 1 else 0.06
    runs = []
    for sample, t in zip(timeline, times):
        captured = bool(runs) and sample["tMs"] == capture_ms
        state = runs[-1][0] if captured else sample["state"]
        end = t if captured else t + step / 2
        if runs and runs[-1][0] == state:
            runs[-1][2] = end
        else:
            runs.append([state, t - step / 2, end])
    return [tuple(run) for run in runs]


def _draw_timeline(ax, timeline: list[dict], moments: list[dict]) -> None:
    times = np.array([sample["tMs"] for sample in timeline]) / 1000
    active = [sample["activeBlocks"] for sample in timeline]
    ambient = np.array([sample["ambientBlocks"] for sample in timeline])

    for state, start, end in _state_runs(timeline, moments[-1]["tMs"]):
        if state in _STATE_COLOURS:
            ax.axvspan(start, end, color=_STATE_COLOURS[state], alpha=0.5, lw=0)
    ax.step(times, active, where="mid", color=BLACK, lw=1.0, label="Active cells")
    if ambient.any():
        ax.plot(times, ambient, color="#666666", lw=0.8, ls="--", label="Ambient level")
    ax.plot(times, ambient + _ARM_EXCESS, color="#666666", lw=0.6, ls=":",
            label="Arming threshold (ambient + 1)")

    for index, snapshot in enumerate(moments):
        t = snapshot["tMs"] / 1000
        ax.axvline(t, color=BLACK, lw=0.5)
        ax.text(t, 1.02, f"({chr(ord('b') + index)})", transform=ax.get_xaxis_transform(),
                ha="center", va="bottom", fontsize=6.5, color=BLACK)

    handles, _ = ax.get_legend_handles_labels()
    handles += [Patch(color=_STATE_COLOURS[s], alpha=0.5, label=s.capitalize()) for s in _STATE_COLOURS]
    ax.legend(handles=handles, fontsize=6, loc="upper left", frameon=False, ncol=1)
    ax.set_xlabel("Time relative to capture (s)", fontsize=7)
    ax.set_ylabel("Cells", fontsize=7)
    ax.set_ylim(0, max(max(active), ambient.max() + _ARM_EXCESS) * 2.2 + 1)
    start = max(times[0], moments[0]["tMs"] / 1000 - _LEAD_IN_S)
    ax.set_xlim(start - 0.03, times[-1] + 0.05)
    ax.tick_params(labelsize=6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _draw_snapshot(ax, snapshot: dict, sample: dict | None, grid: tuple[int, int], aspect: float) -> None:
    """The trigger's frame with changed pixels in orange and active cells outlined."""
    luma, changed = _unpack(snapshot)
    height, width = luma.shape
    rgb = np.repeat((luma * 0.8)[..., None], 3, axis=2).astype(np.uint8)
    rgb[changed] = _CHANGED
    # Shown at the camera's aspect: the client squeezed the whole frame into this grid.
    ax.imshow(rgb, interpolation="none", extent=(0, width, height, 0), aspect=width / (height * aspect))

    cols, rows = grid
    cell_w, cell_h = width / cols, height / rows
    for col in range(1, cols):
        ax.axvline(col * cell_w, color="white", lw=0.2, alpha=0.35)
    for row in range(1, rows):
        ax.axhline(row * cell_h, color="white", lw=0.2, alpha=0.35)
    for cell in (sample or {}).get("cells", []):
        col, row = cell % cols, cell // cols
        ax.add_patch(Rectangle((col * cell_w, row * cell_h), cell_w, cell_h, fill=False, ec=_CELL, lw=0.8))
    ax.set_axis_off()


def render_figure(folder: Path, series: str, dart: str, out: Path) -> None:
    trigger = json.loads((folder / f"{series}_{dart}_trigger.json").read_text())
    if not trigger.get("snapshots"):
        raise SystemExit("no snapshots in this trigger file (recorded outside a test run?)")
    frame = cv2.imread(str(folder / f"{series}_{dart}.jpg"))
    aspect = frame.shape[1] / frame.shape[0] if frame is not None else 16 / 9

    # Arming and peak are often the same frame; show it once.
    moments, seen = [], set()
    for snapshot in sorted(trigger["snapshots"], key=lambda s: s["tMs"]):
        if snapshot["tMs"] not in seen:
            seen.add(snapshot["tMs"])
            moments.append(snapshot)
    samples = {sample["tMs"]: sample for sample in trigger["timeline"]}
    grid = (trigger["gridCols"], trigger["gridRows"])

    # A portrait camera puts the frames beside the timeline, a landscape one below it.
    portrait = aspect < 1
    if portrait:
        fig = plt.figure(figsize=(6.3, 2.9))
        layout = fig.add_gridspec(1, 1 + len(moments), width_ratios=[2.4] + [1] * len(moments),
                                  wspace=0.08)
        timeline_ax = fig.add_subplot(layout[0, 0])
        frame_slots = [layout[0, 1 + i] for i in range(len(moments))]
    else:
        fig = plt.figure(figsize=(6.3, 4.4))
        layout = fig.add_gridspec(2, len(moments), height_ratios=[1, 1.5], hspace=0.5, wspace=0.05)
        timeline_ax = fig.add_subplot(layout[0, :])
        frame_slots = [layout[1, i] for i in range(len(moments))]
    _draw_timeline(timeline_ax, trigger["timeline"], moments)
    timeline_ax.text(0.5, -0.17 if portrait else -0.3, "(a) Trigger over time",
                     transform=timeline_ax.transAxes, ha="center", va="top", fontsize=8, color=BLACK)

    for index, snapshot in enumerate(moments):
        ax = fig.add_subplot(frame_slots[index])
        _draw_snapshot(ax, snapshot, samples.get(snapshot["tMs"]), grid, aspect)
        title = " and ".join(_MOMENT_TITLES[s["moment"]] for s in trigger["snapshots"]
                             if s["tMs"] == snapshot["tMs"])
        ax.text(0.5, -0.03, f"({chr(ord('b') + index)}) {title}",
                transform=ax.transAxes, ha="center", va="top", fontsize=8, color=BLACK)

    fig.subplots_adjust(left=0.07, right=0.99, top=0.93, bottom=0.22 if portrait else 0.05)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print(f"{len(trigger['timeline'])} samples, {len(moments)} snapshot(s), written to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path, help="a recorded game folder")
    parser.add_argument("series", help="e.g. throw3")
    parser.add_argument("dart", help="dart1, dart2 or dart3")
    parser.add_argument("out", nargs="?", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()
    render_figure(args.folder, args.series, args.dart, args.out)


if __name__ == "__main__":
    main()
