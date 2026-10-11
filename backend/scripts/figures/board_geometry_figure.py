"""Render the board-geometry figure for the thesis from the detector's constants.

Usage:
    uv run --with matplotlib python scripts/figures/board_geometry_figure.py
"""

import argparse
import math
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, FancyArrowPatch, Rectangle, Wedge

# TrueType rather than Type 3, which the thesis template's PDF/A profile rejects.
matplotlib.rcParams["pdf.fonttype"] = 42

# Import app.* from src/ (as `--app-dir src` does at runtime), regardless of
# where this script is launched from.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND / "src"))

from app.api.features.calibration.domain.board_geometry import (  # noqa: E402
    BULL_RADIUS,
    BULLSEYE_RADIUS,
    DOUBLE_INNER_RADIUS,
    DOUBLE_OUTER_RADIUS,
    SECTOR_COUNT,
    SECTOR_ORDER,
    TRIPLE_INNER_RADIUS,
    TRIPLE_OUTER_RADIUS,
    is_red_sector,
    sector_centre_angle,
)

_DEFAULT_OUT = _BACKEND.parents[1] / "thesis" / "graphics" / "figures" / "board-geometry.pdf"

RED = "#b8232f"
GREEN = "#1a7a43"
BLACK = "#1c1c1c"
CREAM = "#efe3c2"
WIRE = "#8a8a8a"
ACCENT = "#1f4e79"

NUMBER_RADIUS = 186.0
AXIS_LENGTH = 88.0


def _draw_board(ax) -> None:
    for index in range(SECTOR_COUNT):
        centre = math.degrees(sector_centre_angle(index))
        start, end = centre - 9.0, centre + 9.0
        ring = RED if is_red_sector(index) else GREEN
        single = BLACK if is_red_sector(index) else CREAM
        for inner, outer, colour in (
            (BULL_RADIUS, TRIPLE_INNER_RADIUS, single),
            (TRIPLE_INNER_RADIUS, TRIPLE_OUTER_RADIUS, ring),
            (TRIPLE_OUTER_RADIUS, DOUBLE_INNER_RADIUS, single),
            (DOUBLE_INNER_RADIUS, DOUBLE_OUTER_RADIUS, ring),
        ):
            ax.add_patch(
                Wedge(
                    (0, 0),
                    outer,
                    start,
                    end,
                    width=outer - inner,
                    facecolor=colour,
                    edgecolor=WIRE,
                    linewidth=0.4,
                )
            )
        angle = math.radians(centre)
        ax.text(
            NUMBER_RADIUS * math.cos(angle),
            NUMBER_RADIUS * math.sin(angle),
            str(SECTOR_ORDER[index]),
            ha="center",
            va="center",
            fontsize=8.5,
            color=BLACK,
        )

    ax.add_patch(
        Wedge(
            (0, 0),
            BULL_RADIUS,
            0,
            360,
            width=BULL_RADIUS - BULLSEYE_RADIUS,
            facecolor=GREEN,
            edgecolor=WIRE,
            linewidth=0.4,
        )
    )
    ax.add_patch(
        Wedge((0, 0), BULLSEYE_RADIUS, 0, 360, facecolor=RED, edgecolor=WIRE, linewidth=0.4)
    )


def _label(ax, x, y, text, size=8.5, colour=ACCENT):
    ax.text(
        x,
        y,
        text,
        color=colour,
        fontsize=size,
        ha="center",
        va="center",
        zorder=7,
        bbox=dict(boxstyle="round,pad=0.14", facecolor="white", edgecolor="none", alpha=0.9),
    )


def _draw_coordinate_system(ax) -> None:
    # Drawn inside the board: axes reaching past the double ring would collide
    # with the number ring at both cardinal directions.
    for dx, dy, label, offset in ((1, 0, "$x$", (17, 0)), (0, 1, "$y$", (0, 16))):
        ax.add_patch(
            FancyArrowPatch(
                (0, 0),
                (AXIS_LENGTH * dx, AXIS_LENGTH * dy),
                arrowstyle="-|>",
                mutation_scale=9,
                linewidth=1.1,
                color=ACCENT,
                zorder=6,
            )
        )
        _label(ax, AXIS_LENGTH * dx + offset[0], AXIS_LENGTH * dy + offset[1], label, size=10)

    ax.add_patch(Arc((0, 0), 104, 104, theta1=0, theta2=90, linewidth=0.9, color=ACCENT, zorder=6))
    _label(ax, 40.0, 40.0, r"$\theta$", size=10)
    ax.plot(0, 0, marker="o", markersize=2.6, color=ACCENT, zorder=7)
    _label(ax, 0.0, -30.0, "origin", size=7.5)

    # Sector angle, called out inside a cream sector so the wires stay visible.
    centre = math.degrees(sector_centre_angle(3))
    for bound in (centre - 9.0, centre + 9.0):
        angle = math.radians(bound)
        ax.plot(
            [TRIPLE_OUTER_RADIUS * math.cos(angle), DOUBLE_INNER_RADIUS * math.cos(angle)],
            [TRIPLE_OUTER_RADIUS * math.sin(angle), DOUBLE_INNER_RADIUS * math.sin(angle)],
            color=ACCENT,
            linewidth=1.0,
            zorder=6,
        )
    ax.add_patch(
        Arc(
            (0, 0),
            2 * 148.0,
            2 * 148.0,
            theta1=centre - 9.0,
            theta2=centre + 9.0,
            linewidth=1.0,
            color=ACCENT,
            zorder=6,
        )
    )
    angle = math.radians(centre)
    _label(ax, 134.0 * math.cos(angle), 134.0 * math.sin(angle), r"$18^\circ$", size=8.0)


def _draw_ruler(ax) -> None:
    # Last field is the y the name is written at; None means it fits inside the band.
    bands = (
        (0.0, BULLSEYE_RADIUS, RED, "inner bull", "50", 2.0),
        (BULLSEYE_RADIUS, BULL_RADIUS, GREEN, "outer bull", "25", 15.0),
        (BULL_RADIUS, TRIPLE_INNER_RADIUS, BLACK, "single", r"$\times 1$", None),
        (TRIPLE_INNER_RADIUS, TRIPLE_OUTER_RADIUS, RED, "triple ring", r"$\times 3$", 103.0),
        (TRIPLE_OUTER_RADIUS, DOUBLE_INNER_RADIUS, BLACK, "single", r"$\times 1$", None),
        (DOUBLE_INNER_RADIUS, DOUBLE_OUTER_RADIUS, RED, "double ring", r"$\times 2$", 166.0),
    )
    bar_right = 1.6
    bar_centre = bar_right / 2

    for inner, outer, colour, name, multiplier, label_y in bands:
        ax.add_patch(
            Rectangle(
                (0.0, inner),
                bar_right,
                outer - inner,
                facecolor=colour,
                edgecolor=WIRE,
                linewidth=0.4,
            )
        )
        if label_y is None:
            ax.text(
                bar_centre,
                (inner + outer) / 2,
                f"{name}  {multiplier}",
                ha="center",
                va="center",
                fontsize=8,
                color="white",
            )
            continue
        ax.annotate(
            f"{name}  {multiplier}",
            xy=(bar_right, (inner + outer) / 2),
            xytext=(bar_right + 0.22, label_y),
            fontsize=8,
            va="center",
            ha="left",
            color=BLACK,
            arrowprops=dict(arrowstyle="-", linewidth=0.6, color="#777777", shrinkA=0, shrinkB=2),
        )

    ax.text(
        bar_centre,
        182,
        "surround: no score",
        ha="center",
        va="center",
        fontsize=8,
        color="#555555",
        style="italic",
    )

    # Nudges keep the labels of bands only 10 mm apart from touching.
    ticks = (
        (0.0, "0", -3.5),
        (BULLSEYE_RADIUS, "6.35", 3.5),
        (BULL_RADIUS, "15.9", 10.0),
        (TRIPLE_INNER_RADIUS, f"{TRIPLE_INNER_RADIUS:.1f}", -4.5),
        (TRIPLE_OUTER_RADIUS, f"{TRIPLE_OUTER_RADIUS:.1f}", 4.5),
        (DOUBLE_INNER_RADIUS, f"{DOUBLE_INNER_RADIUS:.1f}", -4.5),
        (DOUBLE_OUTER_RADIUS, f"{DOUBLE_OUTER_RADIUS:.1f}", 4.5),
    )
    for radius, label, nudge in ticks:
        ax.plot(
            [0.0, -0.16, -0.30, -0.46],
            [radius, radius, radius + nudge, radius + nudge],
            color="#777777",
            linewidth=0.6,
            zorder=1,
        )
        ax.text(-0.50, radius + nudge, label, ha="right", va="center", fontsize=8)

    ax.add_patch(
        FancyArrowPatch(
            (-1.40, 0),
            (-1.40, DOUBLE_OUTER_RADIUS),
            arrowstyle="<|-|>",
            mutation_scale=7,
            linewidth=0.8,
            color=BLACK,
            shrinkA=0,
            shrinkB=0,
        )
    )
    ax.text(
        -1.54,
        DOUBLE_OUTER_RADIUS / 2,
        "radius from the center [mm]",
        rotation=90,
        ha="center",
        va="center",
        fontsize=8,
    )


def render(out_path: Path) -> None:
    figure, (board_ax, ruler_ax) = plt.subplots(
        1, 2, figsize=(7.0, 3.9), gridspec_kw={"width_ratios": [1.55, 1.0]}
    )

    _draw_board(board_ax)
    _draw_coordinate_system(board_ax)
    board_ax.set_xlim(-236, 236)
    board_ax.set_ylim(-236, 236)
    board_ax.set_aspect("equal")

    _draw_ruler(ruler_ax)
    ruler_ax.set_xlim(-1.80, 3.40)
    ruler_ax.set_ylim(-16, 200)

    for axis, title in ((board_ax, "(a)"), (ruler_ax, "(b)")):
        axis.axis("off")
        axis.set_title(title, fontsize=9, loc="left")

    figure.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.02, wspace=0.05)
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
