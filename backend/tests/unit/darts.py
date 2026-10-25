"""Builds darts and games from the labels a scoreboard calls out."""

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import Game
from app.api.features.game.domain.game_mode import GameMode
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.player import Player
from app.api.features.game.domain.turn import Turn


def dart(label: str) -> Dart:
    """`T20`, `D16`, `5`, `25` (outer bull), `50` (bullseye), `0` (miss)."""
    if label == "0":
        return Dart(value=0, multiplier=0)
    if label == "50":
        return Dart(value=25, multiplier=2)
    if label[0] in "DT":
        return Dart(value=int(label[1:]), multiplier="_SDT".index(label[0]))
    return Dart(value=int(label), multiplier=1)


def darts(*labels: str) -> list[Dart]:
    return [dart(label) for label in labels]


def new_game(
    players: int = 2,
    *,
    mode: int = 301,
    variant: GameVariant = GameVariant.X01,
    checkout: CheckoutMode = CheckoutMode.DOUBLE_OUT,
) -> Game:
    return Game(
        id="game",
        mode=GameMode(mode),
        players=[Player(id=seat, name=f"P{seat}", identity_id=f"id{seat}") for seat in range(players)],
        variant=variant,
        checkout_mode=checkout,
    )


def leg_at(remaining: int, checkout: CheckoutMode = CheckoutMode.DOUBLE_OUT) -> Game:
    """Player 0 to throw against an opponent who has not scored, needing `remaining`."""
    game = new_game(checkout=checkout)
    game.turns = [
        Turn(player_id=0, darts=[Dart(value=301 - remaining, multiplier=1)]),
        Turn(player_id=1, darts=[dart("0")]),
        Turn(player_id=0),
    ]
    return game
