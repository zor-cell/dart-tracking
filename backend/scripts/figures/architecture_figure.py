"""Render the architecture overview figure for the thesis.

Usage:
    uv run --with matplotlib python scripts/figures/architecture_figure.py
"""

import argparse
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

# TrueType rather than Type 3, which the thesis template's PDF/A profile rejects.
matplotlib.rcParams["pdf.fonttype"] = 42

_BACKEND = Path(__file__).resolve().parents[2]
_DEFAULT_OUT = _BACKEND.parents[1] / "thesis" / "graphics" / "figures" / "architecture.pdf"

BLACK = "#1c1c1c"
ACCENT = "#1f4e79"
MUTED = "#6b6b6b"
FILL = "#f4f6f9"
STATE_FILL = "#e8ecf2"


def _box(ax, x0, y0, x1, y1, facecolor=FILL, edgecolor=BLACK, linewidth=0.9):
    ax.add_patch(
        FancyBboxPatch(
            (x0, y0),
            x1 - x0,
            y1 - y0,
            boxstyle="round,pad=0,rounding_size=1.2",
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
            zorder=2,
        )
    )


def _title(ax, x, y, text):
    ax.text(x, y, text, ha="center", va="center", fontsize=8.5, color=BLACK, zorder=3)


def _item(ax, x, y, text, size=7.0, colour=BLACK):
    ax.text(x, y, text, ha="left", va="center", fontsize=size, color=colour, zorder=3)


def _arrow(ax, x0, y0, x1, y1, dashed=False, colour=ACCENT):
    ax.add_patch(
        FancyArrowPatch(
            (x0, y0),
            (x1, y1),
            arrowstyle="-|>",
            mutation_scale=8,
            linewidth=0.9,
            color=colour,
            linestyle=(0, (3, 2)) if dashed else "solid",
            shrinkA=0,
            shrinkB=0,
            zorder=4,
        )
    )


def _lane_label(ax, x, y, lines, colour=ACCENT):
    ax.text(
        x,
        y,
        "\n".join(lines),
        ha="center",
        va="bottom",
        fontsize=6.5,
        color=colour,
        linespacing=1.35,
        zorder=5,
    )


def render(out_path: Path) -> None:
    figure, ax = plt.subplots(figsize=(7.0, 4.2))

    capture = (0.0, 30.0, 28.0, 59.0)
    server = (39.0, 4.0, 72.0, 59.0)
    board = (82.0, 30.0, 100.0, 59.0)

    _box(ax, *capture)
    _title(ax, (capture[0] + capture[2]) / 2, 55.5, "Capture device")
    for offset, text in enumerate(
        (
            "camera frames",
            "frame differencing",
            "trigger once the scene settles",
        )
    ):
        _item(ax, capture[0] + 2.0, 49.5 - offset * 4.2, f"· {text}")

    _box(ax, *server)
    _title(ax, (server[0] + server[2]) / 2, 55.5, "Application server")
    for offset, text in enumerate(
        (
            "board calibration $\\rightarrow$ homography",
            "dart detection $\\rightarrow$ board coordinates",
            "scoring and game rules",
        )
    ):
        _item(ax, server[0] + 2.0, 49.5 - offset * 4.2, f"· {text}")

    ax.plot([server[0] + 2.0, server[2] - 2.0], [32.5, 32.5], color=MUTED, linewidth=0.6, zorder=3)
    _box(ax, server[0] + 2.0, 6.5, server[2] - 2.0, 29.5, facecolor=STATE_FILL, edgecolor=MUTED, linewidth=0.6)
    ax.text(
        (server[0] + server[2]) / 2,
        26.7,
        "Server-held state, by lifetime",
        ha="center",
        va="center",
        fontsize=7.5,
        color=BLACK,
        zorder=3,
    )
    for offset, (tier, content) in enumerate(
        (
            ("persisted", "games, visits, darts"),
            ("session-scoped", "calibrations"),
            ("process-local", "connections, reference frame"),
        )
    ):
        y = 21.7 - offset * 4.6
        _item(ax, server[0] + 4.0, y, tier, size=7, colour=BLACK)
        _item(ax, server[0] + 4.0, y - 1.9, content, size=6.5, colour=MUTED)

    _box(ax, *board)
    _title(ax, (board[0] + board[2]) / 2, 55.5, "Scoreboard device")
    for offset, text in enumerate(("game state", "virtual board", "manual correction")):
        _item(ax, board[0] + 1.6, 49.5 - offset * 4.2, f"· {text}")

    _arrow(ax, capture[2], 48.0, server[0], 48.0)
    _lane_label(ax, 33.5, 49.0, ["still image"])

    _arrow(ax, server[0], 40.0, capture[2], 40.0)
    _lane_label(ax, 33.5, 41.0, ["result"])

    _arrow(ax, board[0], 48.0, server[2], 48.0)
    _lane_label(ax, 77.0, 49.0, ["commands"])

    _arrow(ax, server[2], 35.0, board[0], 35.0, dashed=True)
    _arrow(ax, server[0], 35.0, capture[2], 35.0, dashed=True)
    _lane_label(ax, 77.0, 36.0, ["game state"])
    _lane_label(ax, 33.5, 36.0, ["game state"])

    ax.set_xlim(0, 100)
    ax.set_ylim(1, 61)
    ax.set_aspect("equal")
    ax.axis("off")

    figure.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out_path, format=out_path.suffix.lstrip("."), transparent=False)
    plt.close(figure)
    print(f"wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", nargs="?", type=Path, default=_DEFAULT_OUT)
    render(parser.parse_args().out)


if __name__ == "__main__":
    main()
