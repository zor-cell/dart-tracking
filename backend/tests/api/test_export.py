import io
import json
import zipfile

import pytest

from app.api.features.evaluation.domain.game_event import GameEvent, GameEventKind
from app.api.features.evaluation.persistence.evaluation_repository import repository as events
from app.api.features.evaluation.services import frame_buffer
from app.infrastructure import database

T20, D5 = (20, 3), (5, 2)


@pytest.fixture
def alice(register):
    return register("alice")


def export(api, **params):
    response = api.get("/export", params=params)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    files = {name: archive.read(name) for name in archive.namelist()}
    return json.loads(files.pop("account.json")), json.loads(files.pop("games.json"))["games"], files


def own_game(api, *guests):
    return api.new_game(api.own_entry()["id"], *guests)["id"]


def log_event(session, game_id, event):
    async def write():
        async with database.session_scope() as db:
            events.append(db, game_id, event)

    session.run(write)


def test_export_needs_an_account(anon):
    assert anon.get("/export").status_code == 401


def test_account_settings_and_address_book(alice):
    alice.put("/settings/filter-usage", json={"uses": [
        {"view": "games", "key": "status", "value": '"finished"', "score": 1, "lastUsedAt": "2026-11-01T10:00:00Z"}
    ]})
    alice.add_player("Bob")

    account, games, files = export(alice)

    assert account["user"]["username"] == "alice"
    assert account["settings"]["advanceOnPull"] is True
    assert [use["key"] for use in account["filterUsage"]] == ["status"]
    assert sorted((p["name"], p["isSelf"]) for p in account["players"]) == [("Alice", True), ("Bob", False)]
    assert (games, files) == ([], {})


def test_games_with_turns_darts_and_positions(alice, session):
    game_id = own_game(alice, alice.add_player("Bob"))
    session.play(game_id, [T20, T20, T20], [D5], hand_over=False)
    session.sql("UPDATE game_darts SET pos_x = 1.5, pos_y = -2 WHERE turn_index = 0 AND dart_index = 0")

    _, games, _ = export(alice)

    [game] = games
    assert (game["id"], game["owned"], game["status"], game["hidden"]) == (game_id, True, "active", False)
    assert game["settings"]["variant"] == "x01"
    assert [(p["name"], p["isMe"]) for p in game["players"]] == [("Alice", True), ("Bob", False)]
    first, second = game["turns"]
    assert first["playerIndex"] == 0 and second["playerIndex"] == 1
    assert [(d["value"], d["multiplier"]) for d in first["darts"]] == [T20] * 3
    assert first["darts"][0]["position"] == [1.5, -2.0]
    assert first["darts"][1]["position"] is None
    assert {"thrownAt", "targetValue", "targetMultiplier"} <= first["darts"][0].keys()


def test_only_games_the_account_is_part_of(alice, register, session):
    bob = register("bob")
    own_game(bob)
    alice_id = own_game(alice)
    alice.patch(f"/games/{alice_id}", json={"status": "discarded"})

    _, games, _ = export(alice)

    assert [(game["id"], game["hidden"]) for game in games] == [(alice_id, True)]


def test_the_password_hash_stays_out(alice):
    response = alice.get("/export")
    archive = zipfile.ZipFile(io.BytesIO(response.content))

    for name in archive.namelist():
        assert b"argon2" not in archive.read(name)
        assert b"passwordHash" not in archive.read(name)


def test_events_and_frames_of_own_test_runs(alice, register, session, tmp_path, monkeypatch):
    monkeypatch.setattr(frame_buffer, "_EVALUATION_ROOT", tmp_path)
    bob = register("bob")
    mine, theirs = own_game(alice), bob.new_game(bob.own_entry()["id"], {"name": "Alice"})["id"]
    session.sql("UPDATE games SET evaluation_enabled = true")
    for game_id in (mine, theirs):
        log_event(session, game_id, GameEvent(
            kind=GameEventKind.DETECTED, turn_index=0, player_index=0, accepted=True,
            value=20, multiplier=3, position=(3.0, 4.0), tracker_version=7,
        ))
        folder = frame_buffer.folder_of(game_id)
        (folder / "_results").mkdir(parents=True)
        (folder / "throw0_base.jpg").write_bytes(b"jpeg")
        (folder / "_results" / "annotated.jpg").write_bytes(b"jpeg")

    _, games, files = export(alice)
    [game] = games
    [event] = game["events"]
    assert (event["kind"], event["position"], event["trackerVersion"]) == ("detected", [3.0, 4.0], 7)
    assert "clientId" not in event
    assert files == {}

    _, _, files = export(alice, frames=True)
    assert files == {f"testdata/evaluation/game_{mine}/throw0_base.jpg": b"jpeg"}


def test_a_moved_tip_is_marked(alice, session):
    game_id = own_game(alice)
    session.play(game_id, [T20], hand_over=False)
    session.sql(
        "UPDATE game_darts SET pos_x = 0, pos_y = 100, pos_snapped = true WHERE game_id = :id",
        id=game_id,
    )

    _, [game], _ = export(alice)

    assert game["turns"][0]["darts"][0]["snapped"] is True
