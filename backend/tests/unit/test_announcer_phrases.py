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

EN, DE = Language.EN, Language.DE


def call(value=20, multiplier=1, *, points=None, busted=False, won=False, eliminated=()):
    return DartCall(value, multiplier, points, busted, won, tuple(eliminated))


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
