"""The grid the tip heatmaps count located darts into."""

# Edge of a heatmap cell, in board millimetres.
HEATMAP_CELL = 2


def heatmap_cell(x: float, y: float) -> tuple[int, int]:
    """The cell a tip at board mm `(x, y)` falls into, as column and row."""
    return round(x / HEATMAP_CELL), round(y / HEATMAP_CELL)
