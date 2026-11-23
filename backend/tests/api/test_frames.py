import pytest

from app.api.features.evaluation.services import frame_store, frame_sweeper
from tests.api.support import PASSWORD


@pytest.fixture
def alice(register):
    return register("alice")


def kept_game(api) -> str:
    game_id = api.new_game(api.own_entry()["id"], evaluationEnabled=True)["id"]
    frame_store.store().write(game_id, "throw0_base.jpg", b"jpeg")
    return game_id


def has_frames(game_id: str) -> bool:
    return bool(frame_store.store().names(game_id))


def keeps(session, game_id: str) -> bool:
    [row] = session.sql("SELECT evaluation_enabled FROM games WHERE id = :id", id=game_id)
    return row[0]


def test_turning_frames_off_deletes_the_ones_kept_of_own_games(alice, register, session):
    bob = register("bob")
    mine, theirs = kept_game(alice), kept_game(bob)

    settings = alice.get("/settings").json()
    alice.put("/settings", json=settings | {"evaluationEnabled": True})
    alice.put("/settings", json=settings | {"evaluationEnabled": False})
    session.run(frame_sweeper.sweep)

    assert (has_frames(mine), has_frames(theirs)) == (False, True)
    assert (keeps(session, mine), keeps(session, theirs)) == (False, True)


def test_settings_saved_with_frames_on_delete_nothing(alice, session):
    game_id = kept_game(alice)

    settings = alice.get("/settings").json() | {"evaluationEnabled": True}
    alice.put("/settings", json=settings)
    alice.put("/settings", json=settings | {"advanceOnPull": False})
    session.run(frame_sweeper.sweep)

    assert has_frames(game_id)


def test_deleting_the_account_deletes_its_frames_also_of_shared_games(alice, register, session):
    bob = register("bob")
    alone = kept_game(alice)
    entry = alice.add_player("Bob")
    bob.accept(alice.invite(entry))
    shared = alice.new_game(alice.own_entry()["id"], entry, evaluationEnabled=True)["id"]
    frame_store.store().write(shared, "throw0_base.jpg", b"jpeg")
    theirs = kept_game(bob)

    assert alice.delete("/auth/me", json={"currentPassword": PASSWORD}).status_code == 204
    session.run(frame_sweeper.sweep)

    assert (has_frames(alone), has_frames(shared), has_frames(theirs)) == (False, False, True)
    assert keeps(session, shared) is False


def test_frames_past_the_retention_are_deleted(alice, session):
    old, new = kept_game(alice), kept_game(alice)
    session.sql("UPDATE games SET created_at = now() - interval '400 days' WHERE id = :id", id=old)

    session.run(frame_sweeper.sweep)

    assert (has_frames(old), has_frames(new)) == (False, True)
    assert (keeps(session, old), keeps(session, new)) == (False, True)


def test_frames_of_no_known_game_are_left_alone(frames, session):
    stray = "01a07b67-e24d-7ed3-a72b-83e0d606fb97"
    frames.write(stray, "throw0_base.jpg", b"jpeg")

    assert session.run(frame_sweeper.sweep) == 0
    assert has_frames(stray)
