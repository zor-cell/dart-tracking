"""The grid the tip heatmaps count located darts into."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.api.features.game.domain.dart import Dart

# Edge of a heatmap cell, in board millimetres.
HEATMAP_CELL = 2


def heatmap_cell(x: float, y: float) -> tuple[int, int]:
    """The cell a tip at board mm `(x, y)` falls into, as column and row."""
    return round(x / HEATMAP_CELL), round(y / HEATMAP_CELL)


def cell_centres(cells: Mapping[tuple[int, int], int]) -> list[tuple[int, int, int]]:
    """Each cell's centre in board mm with its count."""
    return [(column * HEATMAP_CELL, row * HEATMAP_CELL, n) for (column, row), n in cells.items()]


@dataclass
class HitPattern:
    """Darts per called-out label, and the located ones per label and per heatmap cell."""

    fields: Counter[str] = field(default_factory=Counter)
    located_fields: Counter[str] = field(default_factory=Counter)
    cells: Counter[tuple[int, int]] = field(default_factory=Counter)

    def add(self, dart: Dart) -> None:
        self.fields[dart.label] += 1
        if dart.position is not None:
            self.located_fields[dart.label] += 1
            self.cells[heatmap_cell(*dart.position)] += 1
