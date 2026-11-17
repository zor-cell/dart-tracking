"""What the darts thrown at a named field add up to: hits, and how far the others landed."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.target import Target
from app.api.features.statistics.domain.heatmap import heatmap_cell


@dataclass(frozen=True)
class AimedDart:
    target: Target
    dart: Dart

    @property
    def hit(self) -> bool:
        return self.target.hit_by(self.dart.value, self.dart.multiplier)


@dataclass
class TargetTally:
    """The rates stay pairs, so they add up and show how thin the sample is."""

    darts: int = 0
    hits: int = 0
    located: int = 0
    distance: float = 0.0  # summed mm of the located darts from the target, 0 for a hit

    @property
    def mean_distance(self) -> float | None:
        return None if self.located == 0 else self.distance / self.located

    def add(self, aimed: AimedDart) -> None:
        self.darts += 1
        self.hits += aimed.hit
        if aimed.dart.position is not None:
            self.located += 1
            self.distance += aimed.target.distance(*aimed.dart.position)


@dataclass
class FieldTally(TargetTally):
    """A target's tally with what its darts hit and where the located ones landed."""

    located_hits: int = 0
    # Called-out label of every dart's field, hits included.
    landed: Counter[str] = field(default_factory=Counter)
    # Located darts per heatmap cell.
    cells: Counter[tuple[int, int]] = field(default_factory=Counter)

    def add(self, aimed: AimedDart) -> None:
        super().add(aimed)
        self.landed[aimed.dart.label] += 1
        if aimed.dart.position is not None:
            self.located_hits += aimed.hit
            self.cells[heatmap_cell(*aimed.dart.position)] += 1


@dataclass
class GameTally(TargetTally):
    game_id: str = ""
    played_at: datetime | None = None
    # Whether the player got through every target of the game.
    through: bool = False


@dataclass
class TargetStatistics:
    totals: TargetTally = field(default_factory=TargetTally)
    fields: dict[Target, FieldTally] = field(default_factory=dict)
    # One per game with aimed darts, oldest first.
    games: list[GameTally] = field(default_factory=list)

    def add_game(
        self, game_id: str, played_at: datetime, darts: list[AimedDart], through: bool
    ) -> None:
        game = GameTally(game_id=game_id, played_at=played_at, through=through)
        for aimed in darts:
            self.totals.add(aimed)
            game.add(aimed)
            self.fields.setdefault(aimed.target, FieldTally()).add(aimed)
        self.games.append(game)

    @property
    def completed(self) -> list[GameTally]:
        return [game for game in self.games if game.through]

    @property
    def darts_to_finish(self) -> float | None:
        """Darts a game took that the player got through."""
        done = self.completed
        return None if not done else sum(game.darts for game in done) / len(done)

    @property
    def best(self) -> GameTally | None:
        """The game the player got through with the fewest darts, the oldest on a tie."""
        return min(self.completed, key=lambda game: game.darts, default=None)
