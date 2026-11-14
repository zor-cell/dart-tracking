"""The announcer's calls worded in a language, one phrase per clip."""

from app.api.core.domain.language import Language
from app.api.core.services.translations import translate
from app.api.features.announcement.domain.calls import DartCall, TurnCall
from app.api.features.game.domain.cricket import CRICKET_TARGETS, MARKS_TO_CLOSE, CricketHit

_MULTIPLIER_KEYS = {1: "announcer.single", 2: "announcer.double", 3: "announcer.triple"}
# Most points a visit of three darts can score.
_MAX_VISIT = 180


def field_phrase(value: int, multiplier: int, language: Language) -> str:
    """The field a dart landed in: the outer bull as 25, the bullseye as Bull."""
    if multiplier == 0:
        return translate("announcer.miss", language)
    if value == 25:
        return translate("announcer.bull" if multiplier == 2 else "announcer.outerBull", language)
    return translate(_MULTIPLIER_KEYS[multiplier], language, value=value)


def cricket_phrases(hit: CricketHit, language: Language) -> list[str]:
    """How far the number is from closed, then the points the dart scored."""
    phrases = []
    if hit.left > 0:
        phrases.append(translate("announcer.cricketLeft", language, left=hit.left))
    elif hit.closed:
        phrases.append(translate("announcer.cricketClosed", language))
    if hit.points > 0:
        phrases.append(translate("announcer.points", language, points=hit.points))
    return phrases


def dart_phrases(call: DartCall, language: Language) -> list[str]:
    """The field, what it did in Cricket, whoever it eliminated, then how the visit ended."""
    phrases = [field_phrase(call.value, call.multiplier, language)]
    if call.cricket is not None:
        phrases.extend(cricket_phrases(call.cricket, language))
    if call.eliminated:
        players = f" {translate('announcer.and', language)} ".join(call.eliminated)
        phrases.append(translate("announcer.eliminated", language, players=players))
    if call.won:
        phrases.append(translate("announcer.gameShot", language))
    elif call.busted:
        phrases.append(translate("announcer.bust", language))
    elif call.visit_points is not None:
        phrases.append(str(call.visit_points))
    return phrases


def turn_phrase(call: TurnCall, language: Language) -> str:
    """The player, then their score or the field to hit; a single field is its number alone."""
    score: int | str | None = call.score
    if call.target is not None:
        value, multiplier = call.target
        score = value if multiplier == 1 else field_phrase(value, multiplier, language)
    if score is None:
        return call.player
    return translate("announcer.turn", language, player=call.player, score=score)


def calibration_phrase(calibrated: bool, language: Language) -> str:
    key = "announcer.calibrated" if calibrated else "announcer.calibrationFailed"
    return translate(key, language)


def self_test_phrase(language: Language) -> str:
    return translate("announcer.test", language)


def fixed_phrases(language: Language) -> list[str]:
    """Every phrase that names no player, so it can be voiced ahead of any game."""
    fields = [
        field_phrase(value, multiplier, language)
        for value in [*range(1, 21), 25]
        for multiplier in (1, 2, 3)
        if not (value == 25 and multiplier == 3)
    ]
    phrases = [
        *fields,
        field_phrase(0, 0, language),
        *(str(points) for points in range(_MAX_VISIT + 1)),
        *(
            translate("announcer.cricketLeft", language, left=left)
            for left in range(1, MARKS_TO_CLOSE)
        ),
        translate("announcer.cricketClosed", language),
        *(
            translate("announcer.points", language, points=target * marks)
            for target in CRICKET_TARGETS
            for marks in range(1, MARKS_TO_CLOSE + 1)
        ),
        translate("announcer.gameShot", language),
        translate("announcer.bust", language),
        calibration_phrase(True, language),
        calibration_phrase(False, language),
        self_test_phrase(language),
    ]
    return list(dict.fromkeys(phrases))
