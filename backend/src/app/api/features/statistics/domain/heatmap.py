"""The grid the tip heatmaps count located darts into."""

from collections.abc import Mapping

# Edge of a heatmap cell, in board millimetres.
HEATMAP_CELL = 2


def heatmap_cell(x: float, y: float) -> tuple[int, int]:
    """The cell a tip at board mm `(x, y)` falls into, as column and row."""
    return round(x / HEATMAP_CELL), round(y / HEATMAP_CELL)


def cell_centres(cells: Mapping[tuple[int, int], int]) -> list[tuple[int, int, int]]:
    """Each cell's centre in board mm with its count."""
    return [(column * HEATMAP_CELL, row * HEATMAP_CELL, n) for (column, row), n in cells.items()]
