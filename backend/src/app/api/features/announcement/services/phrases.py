"""The announcer's calls worded in a language, one phrase per clip."""

from app.api.core.domain.language import Language
from app.api.core.services.translations import translate
from app.api.features.announcement.domain.calls import DartCall, TurnCall
from app.api.features.game.domain.cricket import CricketHit

_MULTIPLIER_KEYS = {1: "announcer.single", 2: "announcer.double", 3: "announcer.triple"}


def field_phrase(value: int, multiplier: int, language: Language) -> str:
    """The field a dart landed in: the outer bull as 25, the bullseye as Bull."""
    if multiplier == 0:
        return translate("announcer.miss", language)
    if value == 25:
        return translate("announcer.bull" if multiplier == 2 else "announcer.outerBull", language)
    return translate(_MULTIPLIER_KEYS[multiplier], language, value=value)


def _target_phrase(target: tuple[int, int], language: Language) -> int | str:
    """A field to hit: a single as its number alone."""
    value, multiplier = target
    return value if multiplier == 1 else field_phrase(value, multiplier, language)


def next_target_phrase(target: tuple[int, int], language: Language) -> str:
    return translate("announcer.nextTarget", language, target=_target_phrase(target, language))


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


def dart_phrase(call: DartCall, language: Language) -> str:
    """The field, what it did in Cricket, whoever it eliminated, how the visit ended,
    then the training field to throw at next, as one clip."""
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
    if call.target is not None:
        phrases.append(next_target_phrase(call.target, language))
    return ", ".join(phrases)


def turn_phrase(call: TurnCall, language: Language) -> str:
    """The player, then their score or the field to hit; a single field is its number alone."""
    score: int | str | None = call.score
    if call.target is not None:
        score = _target_phrase(call.target, language)
    if score is None:
        return call.player
    return translate("announcer.turn", language, player=call.player, score=score)


def calibration_phrase(calibrated: bool, language: Language) -> str:
    key = "announcer.calibrated" if calibrated else "announcer.calibrationFailed"
    return translate(key, language)


def self_test_phrase(language: Language) -> str:
    return translate("announcer.test", language)


def fixed_phrases(language: Language) -> list[str]:
    """Every phrase that is a clip of its own and names no player, so it can be
    voiced ahead of any game."""
    board = [
        (value, multiplier)
        for value in [*range(1, 21), 25]
        for multiplier in (1, 2, 3)
        if not (value == 25 and multiplier == 3)
    ]
    return [
        *(field_phrase(value, multiplier, language) for value, multiplier in board),
        field_phrase(0, 0, language),
        calibration_phrase(True, language),
        calibration_phrase(False, language),
        self_test_phrase(language),
    ]
