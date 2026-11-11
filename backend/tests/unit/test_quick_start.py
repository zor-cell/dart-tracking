from datetime import UTC, datetime, timedelta

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.cricket import CricketOptions
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.killer import KillerOptions, KillerZone
from app.api.features.game.domain.quick_start import GameSetup, PlayedSetup, favourite

NOW = datetime(2026, 11, 11, tzinfo=UTC)
X01 = GameSetup.of(GameVariant.X01, GameMode.X01_501, CheckoutMode.DOUBLE_OUT, None)
CRICKET = GameSetup.of(GameVariant.CRICKET, None, None, CricketOptions())


def played(setup, days_ago, game_id=None):
    return PlayedSetup(game_id or f"{setup.variant}-{days_ago}", NOW - timedelta(days=days_ago), setup)


def test_nothing_played_offers_nothing():
    assert favourite([], NOW) is None


def test_the_setup_played_most_wins():
    games = [played(CRICKET, 1), played(X01, 2), played(X01, 3)]

    assert favourite(games, NOW).setup == X01


def test_old_games_weigh_less():
    games = [played(CRICKET, 1), played(X01, 90), played(X01, 120)]

    assert favourite(games, NOW).setup == CRICKET


def test_a_tie_goes_to_the_setup_played_last():
    games = [played(X01, 5), played(CRICKET, 5)]
    games[1] = PlayedSetup("cricket", games[0].played_at + timedelta(minutes=1), CRICKET)

    assert favourite(games, NOW).setup == CRICKET


def test_the_latest_game_of_the_setup_is_offered():
    games = [played(X01, 9, "old"), played(X01, 2, "new"), played(CRICKET, 1)]

    assert favourite(games, NOW).game_id == "new"


def test_killer_games_with_other_numbers_are_the_same_setup():
    first = GameSetup.of(GameVariant.KILLER, None, None, KillerOptions(numbers=(3, 7)))
    second = GameSetup.of(GameVariant.KILLER, None, None, KillerOptions(numbers=(12, 1)))
    other = GameSetup.of(
        GameVariant.KILLER, None, None, KillerOptions(numbers=(3, 7), zone=KillerZone.TRIPLE)
    )

    assert first == second
    assert first != other
