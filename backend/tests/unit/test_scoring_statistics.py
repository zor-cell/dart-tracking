from datetime import UTC, datetime

from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.turn import Turn
from app.api.features.statistics.domain.heatmap import heatmap_cell
from app.api.features.statistics.domain.player_statistics import VisitRef
from app.api.features.statistics.domain.scoring_statistics import ScoringStatistics

PLAYED = datetime(2026, 11, 1, tzinfo=UTC)


def visit(*darts: tuple[int, int]) -> Turn:
    return Turn(player_id=0, darts=[Dart(value=value, multiplier=multiplier) for value, multiplier in darts])


def refs(game_id: str, count: int) -> list[VisitRef | None]:
    return [VisitRef(game_id, index, PLAYED) for index in range(count)]


def test_the_bands_include_every_higher_visit():
    statistics = ScoringStatistics()
    turns = [visit((20, 3), (20, 3), (20, 3)), visit((20, 3), (20, 3), (20, 1)), visit((20, 3))]

    statistics.add_game("a", PLAYED, turns, refs("a", 3))

    assert [statistics.visits_from(points) for points in (180, 140, 100, 60)] == [1, 2, 2, 3]
    assert statistics.average == 3 * 380 / 7


def test_a_tie_keeps_the_oldest_best_visit():
    statistics = ScoringStatistics()

    statistics.add_game("old", PLAYED, [visit((20, 3))], refs("old", 1))
    statistics.add_game("new", PLAYED, [visit((20, 3))], refs("new", 1))

    assert statistics.best_visit_at == VisitRef("old", 0, PLAYED)


def test_a_game_without_darts_is_left_out():
    statistics = ScoringStatistics()

    statistics.add_game("empty", PLAYED, [visit()], [None])

    assert (statistics.darts, statistics.games, dict(statistics.visit_scores)) == (0, [], {})


def test_the_hit_pattern_counts_every_dart_and_locates_those_with_a_tip():
    statistics = ScoringStatistics()
    located = Dart(value=20, multiplier=3, position=(0.0, 103.0))
    turn = Turn(player_id=0, darts=[located, Dart(value=20, multiplier=3), Dart(value=0, multiplier=0)])

    statistics.add_game("a", PLAYED, [turn], refs("a", 1))

    assert statistics.hits.fields == {"T20": 2, "0": 1}
    assert statistics.hits.located_fields == {"T20": 1}
    assert statistics.hits.cells == {heatmap_cell(0.0, 103.0): 1}
