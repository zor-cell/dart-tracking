"""Random sequences of throws and corrections against the rules every state must keep."""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.features.game.domain.checkout_mode import CheckoutMode
from app.api.features.game.domain.dart import Dart
from app.api.features.game.domain.game import DARTS_PER_TURN, Game
from app.api.features.game.domain.game_variant import GameVariant
from tests.unit.darts import new_game

fields = st.sampled_from(
    [Dart(0, 0), Dart(25, 1), Dart(25, 2)]
    + [Dart(value, multiplier) for value in range(1, 21) for multiplier in (1, 2, 3)]
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
games = st.builds(
    lambda players, variant, checkout: new_game(players, variant=variant, checkout=checkout),
    st.integers(min_value=1, max_value=3),
    st.sampled_from(GameVariant),
    st.sampled_from(CheckoutMode),
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
        assert all(0 <= game.remaining(player.id) <= game.mode for player in game.players), action
        assert sum(game.remaining(player.id) == 0 for player in game.players) <= 1, action
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
