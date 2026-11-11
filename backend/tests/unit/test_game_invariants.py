"""Random sequences of throws and corrections against the rules every state must keep."""

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.features.game.domain.around_the_clock import ClockOptions, ClockZone
from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.cricket import CricketOptions, CricketScoring
from app.api.features.game.domain.killer import KillerOptions, KillerZone
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import DARTS_PER_TURN, Game
from app.api.features.game.domain.game_variant import GameVariant
from app.api.features.game.domain.turn import Turn
from tests.unit.darts import new_game

fields = st.one_of(
    st.sampled_from(
        [Dart(0, 0), Dart(25, 1), Dart(25, 2)]
        + [Dart(value, multiplier) for value in range(1, 21) for multiplier in (1, 2, 3)]
    ),
    # The fields the variants' targets and the Killer numbers below sit on.
    st.sampled_from([Dart(value, multiplier) for value in (1, 2, 3, 20) for multiplier in (1, 2, 3)]),
    st.sampled_from([Dart(value, 3) for value in range(15, 21)] + [Dart(25, 2)]),
)
positions = st.integers(min_value=0, max_value=3)
actions = st.one_of(
    st.tuples(st.just("register"), fields),
    st.tuples(st.just("add"), fields),
    st.tuples(st.just("replace"), positions, fields),
    st.tuples(st.just("remove"), positions),
    st.tuples(st.just("move"), positions, positions),
    st.tuples(st.just("undo")),
    st.tuples(st.just("next")),
)
# Killer numbers among the low ones, so random darts hit them often.
options = st.one_of(
    st.none(),
    st.builds(CricketOptions, st.sampled_from(CricketScoring)),
    st.builds(ClockOptions, st.sampled_from(ClockZone), st.booleans()),
    st.builds(
        lambda zone, lives: KillerOptions(numbers=(1, 2, 3), lives=lives, zone=zone),
        st.sampled_from(KillerZone),
        st.integers(min_value=1, max_value=3),
    ),
)
_VARIANT_OF = {
    CricketOptions: GameVariant.CRICKET,
    ClockOptions: GameVariant.AROUND_THE_CLOCK,
    KillerOptions: GameVariant.KILLER,
}


def _game(players, variant, checkout, settings, warm_up):
    if settings is None:
        return new_game(players, variant=variant, checkout=checkout)
    if isinstance(settings, KillerOptions):
        players = max(players, 2)
        settings = replace(settings, numbers=settings.numbers[:players])
    game = new_game(players, variant=_VARIANT_OF[type(settings)], options=settings)
    for _ in range(warm_up * players):
        while game.winner is None and game.darts_remaining > 0:
            game.register_dart(_aim(game))
        game.next_player()
    return game


_RING = {ClockZone.ANY: 1, ClockZone.DOUBLE: 2, ClockZone.TRIPLE: 3}
_KILLER_RING = {KillerZone.ANY: 1, KillerZone.DOUBLE: 2, KillerZone.TRIPLE: 3}


def _aim(game: Game) -> Dart:
    """A dart that moves the current player on, so the random part starts mid-game."""
    progress = game.progress
    player = progress.players[game.current_player.id]
    match game.options:
        case CricketOptions():
            target = next(t for t, marks in player.marks.items() if marks < 3)
            return Dart(25, 2) if target == 25 else Dart(target, 3)
        case ClockOptions(zone=zone):
            return Dart(25, 2) if player.target == 25 else Dart(player.target, _RING[zone])
        case KillerOptions(zone=zone) if not player.killer:
            return Dart(player.number, _KILLER_RING[zone])
    return Dart(0, 0)


games = st.builds(
    _game,
    st.integers(min_value=1, max_value=3),
    st.sampled_from([GameVariant.X01, GameVariant.ELIMINATION]),
    st.sampled_from(CheckoutMode),
    options,
    st.integers(min_value=0, max_value=6),
)


def apply(game: Game, action: tuple) -> None:
    match action:
        case ("register", dart):
            game.register_dart(dart)
        case ("add", dart):
            game.add_dart(dart)
        case ("replace", index, dart):
            game.replace_dart(index, dart)
        case ("remove", index):
            game.remove_dart(index)
        case ("move", index, to_index):
            game.move_dart(index, to_index)
        case ("undo",):
            game.undo()
        case ("next",):
            game.next_player()


def snapshot(game: Game) -> tuple:
    return (
        game.current_player_index,
        tuple((turn.player_id, tuple(turn.darts), turn.busted) for turn in game.turns),
        tuple(game.shadow_darts),
    )


@settings(max_examples=300, deadline=None)
@given(games, st.lists(actions, max_size=60))
def test_every_reachable_state_keeps_the_rules(game, sequence):
    for action in sequence:
        before, revision = snapshot(game), game.revision
        apply(game, action)

        assert game.turns, action
        assert game.current_turn.player_id == game.current_player.id, action
        assert all(len(turn.darts) <= DARTS_PER_TURN for turn in game.turns), action
        assert len(game.current_turn.darts) + len(game.shadow_darts) <= DARTS_PER_TURN, action
        if game.variant.counts_points:
            assert all(0 <= game.remaining(player.id) <= game.mode for player in game.players)
            assert sum(game.remaining(player.id) == 0 for player in game.players) <= 1, action
        else:
            assert not any(turn.busted for turn in game.turns), action
            assert game.checkout is None and game.setup is None, action
        if isinstance(game.options, KillerOptions):
            progress = game.progress
            assert all(0 <= p.lives <= game.options.lives for p in progress.players.values())
            alive = [pid for pid, p in progress.players.items() if not p.out]
            assert alive, action
            assert (game.winner is not None) is (len(alive) == 1), action
            # Only a player who knocked themselves out in the open visit is still up.
            if game.is_out(game.current_player.id):
                assert game.current_turn.darts and game.darts_remaining == 0, action
            assert not any(
                replace(game, turns=game.turns[:index]).is_out(turn.player_id)
                for index, turn in enumerate(game.turns)
                if index
            ), action
        if game.winner is not None and not game.variant.counts_points:
            # The win fell on the last dart booked: nothing scored after it.
            open_turn = game.current_turn
            before_win = [*game.turns[:-1], Turn(open_turn.player_id, open_turn.darts[:-1])]
            assert replace(game, turns=before_win).winner is None, action
        if snapshot(game) != before:
            assert game.revision > revision, f"{action} changed the game without a new revision"


@settings(max_examples=300, deadline=None)
@given(games, st.lists(actions, max_size=60), fields)
def test_undo_takes_back_a_booked_dart_exactly(game, sequence, dart):
    for action in sequence:
        apply(game, action)
    before = snapshot(game)

    if game.register_dart(dart):
        game.undo()
        assert snapshot(game) == before
