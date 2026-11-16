"""Which fields a player hits worst against their own average in that ring."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.api.features.game.domain.target import Target
from app.api.features.statistics.domain.target_statistics import FieldTally, TargetStatistics

# Darts at a field before its rate counts as telling.
MIN_DARTS = 10
# Darts at the ring's average a field's rate is pulled towards, so a thin record ranks calmly.
PRIOR_DARTS = 10


@dataclass(frozen=True)
class Weakness:
    target: Target
    darts: int
    hits: int
    # The ring's darts and hits over every field, the player's average there.
    ring_darts: int
    ring_hits: int

    @property
    def telling(self) -> bool:
        return self.darts >= MIN_DARTS

    @property
    def ring_rate(self) -> float:
        return 0.0 if self.ring_darts == 0 else self.ring_hits / self.ring_darts

    @property
    def score(self) -> float:
        """The rate pulled towards the ring's average, relative to it; lower is weaker."""
        rate = (self.hits + PRIOR_DARTS * self.ring_rate) / (self.darts + PRIOR_DARTS)
        return rate / self.ring_rate if self.ring_rate > 0 else rate


def weaknesses(
    statistics: TargetStatistics, rings: Sequence[int | None], extra: Sequence[Target] = ()
) -> list[Weakness]:
    """Every field of `rings` with a record, and `extra` without one, weakest first; the
    thin ones after the telling. The single (None) takes every ring of its number."""
    tallies = {_ringed(target): FieldTally() for target in extra}
    for target, tally in statistics.fields.items():
        merged = tallies.setdefault(_ringed(target), FieldTally())
        merged.darts += tally.darts
        merged.hits += tally.hits
    pools = {ring: [0, 0] for ring in rings}
    for target, tally in tallies.items():
        if target.multiplier in pools:
            pools[target.multiplier][0] += tally.darts
            pools[target.multiplier][1] += tally.hits
    found = [
        Weakness(
            target=target,
            darts=tally.darts,
            hits=tally.hits,
            ring_darts=pools[target.multiplier][0],
            ring_hits=pools[target.multiplier][1],
        )
        for target, tally in tallies.items()
        if target.multiplier in pools
    ]
    return sorted(found, key=lambda weak: (not weak.telling, weak.score, -weak.darts))


def _ringed(target: Target) -> Target:
    return Target(target.value, None) if target.multiplier == 1 else target
