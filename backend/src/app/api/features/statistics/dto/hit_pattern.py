"""The wire fields every statistics view with a hit pattern carries."""

from typing import Any

from app.api.core.dto.base import CamelModel
from app.api.features.statistics.domain.heatmap import HitPattern, cell_centres


class HitPatternDto(CamelModel):
    # Darts per called-out label; the located ones apart, as the heatmaps take them.
    fields: dict[str, int]
    located_fields: dict[str, int]
    # Centre of each heatmap cell in board mm and its located darts.
    heatmap: list[tuple[int, int, int]]


def hit_pattern(hits: HitPattern) -> dict[str, Any]:
    """The `HitPatternDto` fields of `hits`, to spread into a subclass's constructor."""
    return {
        "fields": dict(hits.fields),
        "located_fields": dict(hits.located_fields),
        "heatmap": cell_centres(hits.cells),
    }
