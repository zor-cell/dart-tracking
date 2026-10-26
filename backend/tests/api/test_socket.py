import base64
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.features.evaluation.domain.alignment import DartOutcome
from app.api.features.evaluation.services import accuracy, frame_buffer
from app.infrastructure import database
from tests.cv.replay import dataset_root, manifest, replay_series, series_of

SOME_ID = "00000000-0000-0000-0000-000000000000"


class Device:
    """One phone in a game's room."""

    def __init__(self, websocket: Any) -> None:
        self.websocket = websocket
        handshake = self.next("client_state")
        self.id, self.role = handshake["clientId"], handshake["role"]
        self.state = self.next("game_state")

    def send(self, type: str, **fields: Any) -> None:
        self.websocket.send_json({"type": type, **fields})

    def next(self, type: str, *, never: tuple[str, ...] = ()) -> dict[str, Any]:
        """The next message of `type`, skipping others but failing on any in `never`."""
        while True:
            message = self.websocket.receive_json()
            assert message["type"] not in never, message
            if message["type"] == type:
                if type == "game_state":
                    self.state = message
                return message

    def throw(self, value: int, multiplier: int = 1, **fields: Any) -> None:
        self.send("register_dart", value=value, multiplier=multiplier, **fields)


@pytest.fixture
def room(client):
    @contextmanager
    def join(game_id: str, client_id: str | None = None):
        query = f"?clientId={client_id}" if client_id else ""
        with client.websocket_connect(f"/api/ws/games/{game_id}{query}") as websocket:
            yield Device(websocket)

    return join


@pytest.fixture
def game_id(anon):
    return anon.new_game({"name": "Ann"}, {"name": "Ben"})["id"]


def darts(state: dict[str, Any]) -> list[str]:
    return [dart["label"] for dart in state["turns"][-1]["darts"]]


def encoded(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def jpeg(width: int, height: int) -> str:
    _, buffer = cv2.imencode(".jpg", np.zeros((height, width, 3), np.uint8))
    return base64.b64encode(buffer.tobytes()).decode()


@pytest.mark.parametrize("target", [SOME_ID, "not-a-uuid"])
def test_unknown_game_is_refused(client, target):
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect(f"/api/ws/games/{target}"):
            pass
    assert refused.value.code == 1008


@pytest.mark.parametrize(("origin", "allowed"), [("https://evil.example", False), ("http://testserver", True)])
def test_browsers_from_other_sites_are_refused(client, game_id, origin, allowed):
    def connect():
        with client.websocket_connect(f"/api/ws/games/{game_id}", headers={"origin": origin}) as ws:
            Device(ws)

    if allowed:
        connect()
    else:
        with pytest.raises(WebSocketDisconnect):
            connect()


def test_a_room_holds_eight_devices(room, client, game_id):
    with ExitStack() as stack:
        for _ in range(8):
            stack.enter_context(room(game_id))
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/api/ws/games/{game_id}"):
                pass


def test_role_survives_a_reconnect(room, game_id):
    with room(game_id, "phone") as phone:
        assert phone.role == "scoreboard"
        phone.send("set_role", role="camera")
        assert phone.next("client_state")["role"] == "camera"

    with room(game_id, "phone") as phone:
        assert (phone.id, phone.role) == ("phone", "camera")
        phone.next("calibration_requested")


def test_every_device_in_the_room_gets_each_change(room, game_id):
    with room(game_id) as scoreboard, room(game_id) as other:
        other.throw(20, 3)
        other.throw(5)
        other.throw(1)
        other.send("replace_dart", index=1, value=20, multiplier=1)
        other.send("move_dart", index=2, toIndex=0)
        other.send("remove_dart", index=1)
        other.send("undo")

        for device in (scoreboard, other):
            for _ in range(7):
                device.next("game_state")
            assert darts(device.state) == ["1"]
            assert device.state["revision"] == 7


def test_the_announcer_hears_each_booked_dart(room, game_id):
    with room(game_id) as announcer, room(game_id) as other:
        for value in (20, 20, 20):
            other.throw(value, 3)

        first = announcer.next("dart_announcement")
        announcer.next("dart_announcement")
        last = announcer.next("dart_announcement")

    assert (first["value"], first["multiplier"], first["visitPoints"]) == (20, 3, None)
    assert last["visitPoints"] == 180


def test_a_command_that_changes_nothing_is_not_broadcast(room, game_id):
    with room(game_id) as device:
        device.send("undo")
        device.send("next_player")
        device.throw(5)

        state = device.next("game_state")

    assert (state["revision"], darts(state)) == (1, ["5"])


def test_a_command_against_an_outdated_visit_is_refused(room, game_id):
    with room(game_id) as device:
        device.throw(20, turnIndex=0, dartIndex=0)
        device.next("game_state")
        device.throw(1, turnIndex=0, dartIndex=0)
        device.throw(2, turnIndex=0, dartIndex=1)

        state = device.next("game_state")

    assert darts(state) == ["20", "2"]


def test_two_devices_ending_the_same_visit_hand_over_once(room, game_id):
    with room(game_id) as first, room(game_id) as second:
        first.throw(20)
        first.next("game_state")
        first.send("next_player")
        first.next("game_state")

        second.send("next_player")
        second.throw(1)
        state = second.next("game_state")
        while darts(state) != ["1"]:
            state = second.next("game_state")

    assert (state["currentPlayerIndex"], state["revision"]) == (1, 5)


@pytest.mark.parametrize("raw", ["not json", '{"type": "no_such_thing"}', '{"type": "register_dart", "value": 26}'])
def test_malformed_messages_are_dropped_and_the_connection_stays(room, game_id, raw):
    with room(game_id) as device:
        device.websocket.send_text(raw)
        device.throw(5)

        assert darts(device.next("game_state")) == ["5"]


def test_evaluation_switch_needs_an_admin_on_the_connection(room, game_id, register, session):
    alice = register("alice")
    with room(game_id) as device:
        device.send("set_evaluation", enabled=True)
        device.send("authenticate", accessToken="garbage")
        device.send("set_evaluation", enabled=True)
        device.send("authenticate", accessToken=alice.token)
        device.send("set_evaluation", enabled=True)
        device.throw(5)
        assert device.next("game_state")["evaluationEnabled"] is False

        session.make_admin(alice)
        device.send("authenticate", accessToken=alice.token)
        device.send("set_evaluation", enabled=True)

        assert device.next("game_state")["evaluationEnabled"] is True


def test_frames_from_a_scoreboard_are_ignored(room, game_id):
    with room(game_id) as device:
        device.send("calibration_frame", image=jpeg(64, 48))
        device.send("detection_frame", image=jpeg(64, 48))
        device.send("set_role", role="scoreboard")

        device.next("client_state", never=("calibration_result", "detection_result"))


@pytest.fixture
def camera(room, game_id):
    @contextmanager
    def join():
        with room(game_id) as device:
            device.send("set_role", role="camera")
            device.next("client_state")
            yield device

    return join


@pytest.mark.parametrize("image", ["%%% not base64", base64.b64encode(b"GIF89a").decode(), jpeg(4097, 8)])
def test_unreadable_frames_are_reported_not_decoded(camera, image):
    with camera() as device:
        device.send("calibration_frame", image=image)
        assert device.next("calibration_result") == {
            "type": "calibration_result",
            "success": False,
            "overlay": None,
            "failure": "invalid_image",
        }


def test_throw_before_calibration(camera):
    with camera() as device:
        device.send("detection_frame", image=jpeg(64, 48))
        assert device.next("detection_result")["failure"] == "not_calibrated"


def test_handover_asks_the_cameras_to_calibrate_again(room, camera, game_id):
    with camera() as phone, room(game_id) as scoreboard:
        scoreboard.throw(20)
        scoreboard.send("next_player")
        scoreboard.next("game_state")
        scoreboard.next("game_state")

        phone.next("calibration_requested")


def test_rematch_calls_the_old_room_over(room, game_id, anon):
    with room(game_id) as device:
        rematch = anon.post(
            "/games",
            json={
                "mode": 301,
                "players": [{"playerId": p["identityId"]} for p in device.state["players"]],
                "rematchOf": game_id,
            },
        ).json()

        assert device.next("rematch_started")["gameId"] == rematch["id"]


@pytest.mark.skipif(dataset_root() is None, reason="TESTDATA_DIR is not set")
def test_socket_scores_a_throw_series_like_the_pipeline_does(camera):
    entry = next(entry for entry in manifest("gate") if entry[0].startswith("games/"))
    frames = next(
        frames for frames in series_of(dataset_root(), entry).values() if replay_series(frames)[0]["failure"] is None
    )
    expected = list(replay_series(frames)[1].values())

    with camera() as device:
        device.send("calibration_frame", image=encoded(frames[0][1]))
        assert device.next("calibration_result")["success"] is True

        reported, booked = [], 0
        for _, path in frames[1:]:
            device.send("detection_frame", image=encoded(path))
            result = device.next("detection_result")
            reported.append(result["segment"] or result["failure"])
            if result["success"]:
                booked += 1
                assert len(darts(device.next("game_state"))) == min(booked, 3)

    assert reported == expected


@pytest.mark.skipif(dataset_root() is None, reason="TESTDATA_DIR is not set")
@pytest.mark.parametrize("advance_on_pull", [True, False])
def test_pulled_darts_hand_over_with_the_rest_as_misses(camera, advance_on_pull):
    entry = ("games/game_01a13481-1426-766f-b71d-524e8038c6ba", {"throw16"})
    base, located, pulled = (path for _, path in next(iter(series_of(dataset_root(), entry).values())))

    with camera() as device:
        device.send("calibration_frame", image=encoded(base))
        assert device.next("calibration_result")["success"] is True
        device.send("detection_frame", image=encoded(located), advanceOnPull=advance_on_pull)
        assert darts(device.next("game_state")) == ["15"]

        device.send("detection_frame", image=encoded(pulled), advanceOnPull=advance_on_pull)
        assert device.next("detection_result")["failure"] == "darts_removed"
        if advance_on_pull:
            state = device.next("game_state")
            assert [dart["label"] for dart in state["turns"][0]["darts"]] == ["15", "0", "0"]
            assert len(state["turns"]) == 2
            device.next("calibration_requested")
        else:
            device.send("set_role", role="camera")
            device.next("client_state", never=("game_state",))


def test_camera_frames_are_throttled(camera):
    with camera() as device:
        for _ in range(8):
            device.send("detection_frame", image=jpeg(64, 48))
        device.send("set_role", role="camera")

        answered = 0
        while (message := device.websocket.receive_json())["type"] != "client_state":
            answered += message["type"] == "detection_result"

    assert answered in (6, 7)


@pytest.mark.parametrize("test_run", [False, True])
def test_a_test_run_keeps_the_shot_of_a_failed_calibration(room, register, session, tmp_path, monkeypatch, test_run):
    monkeypatch.setattr(frame_buffer, "_EVALUATION_ROOT", tmp_path)
    alice = register("alice")
    session.make_admin(alice)
    game_id = alice.new_game(alice.own_entry()["id"], evaluationEnabled=test_run)["id"]

    with room(game_id) as device:
        device.send("set_role", role="camera")
        device.send("calibration_frame", image=jpeg(640, 480))
        assert device.next("calibration_result")["success"] is False

    assert any(tmp_path.rglob("calibration_*.jpg")) is test_run


@pytest.mark.skipif(dataset_root() is None, reason="TESTDATA_DIR is not set")
def test_an_evaluation_run_records_frames_and_events(room, register, session, tmp_path, monkeypatch):
    monkeypatch.setattr(frame_buffer, "_EVALUATION_ROOT", tmp_path / "evaluation")
    alice = register("alice")
    session.make_admin(alice)
    game_id = alice.new_game(alice.own_entry()["id"], evaluationEnabled=True)["id"]
    frames = next(
        frames
        for entry in manifest("gate")
        if entry[0].startswith("games/")
        for frames in series_of(dataset_root(), entry).values()
        if replay_series(frames)[0]["failure"] is None
    )

    with room(game_id) as device:
        device.send("set_role", role="camera")
        device.send("authenticate", accessToken=alice.token)
        device.send("calibration_frame", image=base64.b64encode(frames[0][1].read_bytes()).decode())
        assert device.next("calibration_result")["success"] is True
        booked = 0
        for _, path in frames[1:]:
            device.send("detection_frame", image=base64.b64encode(path.read_bytes()).decode())
            booked += device.next("detection_result")["success"]
        device.send("next_player")
        while device.next("game_state")["currentPlayerIndex"] != 0 or len(device.state["turns"]) < 2:
            pass

    folder = tmp_path / "evaluation" / f"game_{game_id}"
    kept = (folder / "throw0_frames.txt").read_text().splitlines()
    assert (folder / "throw0_base.jpg").is_file()
    assert sorted(path.name for path in folder.glob("throw0_dart*.jpg")) == [f"throw0_dart{i}.jpg" for i in range(1, len(kept) + 1)]

    async def judged():
        async with database.session_scope() as db:
            return await accuracy.judged_games(db, game_ids=[game_id], include_unfinished=True)

    (game,) = session.run(judged)
    assert len(game.judgements) == min(booked, 3)
    assert all(judgement.outcome is DartOutcome.CORRECT for judgement in game.judgements)
