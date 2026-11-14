import pytest

from app.api.core.domain.language import Language
from app.api.features.announcement.domain.calls import DartCall, TurnCall
from app.api.features.announcement.services.phrases import (
    calibration_phrase,
    dart_phrases,
    field_phrase,
    fixed_phrases,
    turn_phrase,
)
from app.api.features.game.domain.around_the_clock import ClockOptions, ClockZone
from app.api.features.game.domain.cricket import CricketHit, CricketOptions, CricketScoring
from app.api.features.game.domain.game_variant import GameVariant
from tests.unit.darts import new_game, play

EN, DE = Language.EN, Language.DE


def call(
    value=20, multiplier=1, *, points=None, busted=False, won=False, eliminated=(), cricket=None
):
    return DartCall(value, multiplier, points, busted, won, tuple(eliminated), cricket)


@pytest.mark.parametrize(
    ("value", "multiplier", "en", "de"),
    [
        (20, 1, "Single 20", "Single 20"),
        (16, 2, "Double 16", "Doppel 16"),
        (19, 3, "Triple 19", "Trippel 19"),
        (25, 1, "25", "25"),
        (25, 2, "Bull", "Bull"),
        (0, 0, "Miss", "Daneben"),
    ],
)
def test_fields_are_worded_per_language(value, multiplier, en, de):
    assert field_phrase(value, multiplier, EN) == en
    assert field_phrase(value, multiplier, DE) == de


def test_a_dart_inside_the_visit_is_only_its_field():
    assert dart_phrases(call(), EN) == ["Single 20"]


def test_a_full_visit_ends_with_its_points():
    assert dart_phrases(call(20, 3, points=180), EN) == ["Triple 20", "180"]


def test_a_bust_and_a_win_replace_the_points():
    assert dart_phrases(call(points=0, busted=True), DE) == ["Single 20", "Überworfen"]
    assert dart_phrases(call(points=0, busted=True), EN) == ["Single 20", "Bust!"]
    assert dart_phrases(call(25, 2, points=90, won=True), EN) == ["Bull", "Game shot"]
    assert dart_phrases(call(25, 2, points=90, won=True), DE) == ["Bull", "Spiel gewonnen"]


def test_eliminated_players_are_named_together():
    phrases = dart_phrases(call(points=60, eliminated=["Anna", "Ben"]), DE)
    assert phrases == ["Single 20", "Anna und Ben eliminiert", "60"]


def test_the_turn_and_calibration_calls():
    assert turn_phrase(TurnCall("Anna", 301), EN) == "Anna, 301"
    assert calibration_phrase(False, DE) == "Kalibrierung fehlgeschlagen"


@pytest.mark.parametrize("language", list(Language))
def test_fixed_phrases_cover_every_field_and_visit_score(language):
    phrases = fixed_phrases(language)

    assert len(phrases) == len(set(phrases))
    assert {"25", "Bull", "0", "180"} <= set(phrases)
    for value, multiplier in [(1, 1), (20, 3), (25, 1), (25, 2), (0, 0)]:
        assert field_phrase(value, multiplier, language) in phrases


def clock_call(zone, *visits):
    game = new_game(1, variant=GameVariant.AROUND_THE_CLOCK, options=ClockOptions(zone))
    play(game, *visits, "")
    return TurnCall.of(game)


def test_around_the_clock_calls_the_field_to_hit_next():
    assert turn_phrase(clock_call(ClockZone.ANY, "1 2 0"), DE) == "P0, 3"
    assert turn_phrase(clock_call(ClockZone.DOUBLE, "D1"), DE) == "P0, Doppel 2"
    assert turn_phrase(clock_call(ClockZone.TRIPLE, "T1"), EN) == "P0, Triple 2"


def test_the_last_field_is_the_25_for_singles_and_the_bull_otherwise():
    assert turn_phrase(TurnCall("Anna", None, (25, 1)), EN) == "Anna, 25"
    assert turn_phrase(TurnCall("Anna", None, (25, 2)), EN) == "Anna, Bull"


def cricket_call(*visits, scoring=CricketScoring.STANDARD, index=-1):
    game = new_game(variant=GameVariant.CRICKET, options=CricketOptions(scoring))
    play(game, *visits)
    thrown = game.current_turn.darts[index]
    return DartCall.of(thrown, game, set(), index)


def test_a_cricket_dart_says_what_its_number_still_needs():
    assert dart_phrases(cricket_call("17"), DE) == ["Single 17", "noch 2"]
    assert dart_phrases(cricket_call("17 D17"), EN) == ["Double 17", "closed"]
    assert dart_phrases(cricket_call("T20"), DE) == ["Trippel 20", "zu"]


def test_marks_past_closing_are_called_as_points():
    assert dart_phrases(cricket_call("D20 T20"), DE) == ["Trippel 20", "zu", "40 Punkte"]
    assert dart_phrases(cricket_call("T20 20"), EN) == ["Single 20", "20 points"]


def test_a_number_closed_by_everyone_and_a_field_off_the_targets_say_nothing_more():
    assert dart_phrases(cricket_call("T20", "T20", "20"), DE) == ["Single 20"]
    assert dart_phrases(cricket_call("14"), DE) == ["Single 14"]
    assert dart_phrases(cricket_call("T20 20", scoring=CricketScoring.NO_SCORE), DE) == ["Single 20"]


def test_a_corrected_dart_is_called_in_its_place():
    assert dart_phrases(cricket_call("17 17 17", index=0), DE) == ["Single 17", "noch 2"]


def test_cut_throat_calls_the_points_one_opponent_gets():
    call = cricket_call("T20 20", scoring=CricketScoring.CUT_THROAT)

    assert call.cricket == CricketHit(left=0, closed=False, points=20)


@pytest.mark.parametrize("language", list(Language))
def test_fixed_phrases_cover_the_cricket_calls(language):
    phrases = fixed_phrases(language)

    for hit in (CricketHit(2, False, 0), CricketHit(0, True, 75), CricketHit(0, False, 60)):
        assert set(dart_phrases(call(cricket=hit), language)) <= set(phrases)
