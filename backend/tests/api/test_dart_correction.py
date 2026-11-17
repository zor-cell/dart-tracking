from app.api.features.game.domain.dart import Dart
from app.api.features.game.persistence.game_repository import repository as games
from app.infrastructure import database


def test_a_moved_tip_is_saved_and_loaded_with_its_mark(register, session):
    alice = register("alice")
    game_id = alice.new_game(alice.own_entry()["id"])["id"]

    async def correct() -> None:
        async with database.session_scope() as db:
            game = await games.lock(db, game_id)
            game.register_dart(Dart(value=20, multiplier=1, position=(0.0, 158.5)))
            game.replace_dart(0, Dart(value=20, multiplier=2))
            await games.save(db, game)

    async def load() -> Dart:
        async with database.session_scope() as db:
            game = await games.get(db, game_id)
            return game.turns[0].darts[0]

    session.run(correct)
    loaded = session.run(load)

    assert (loaded.label, loaded.snapped) == ("D20", True)
    assert loaded.position is not None
