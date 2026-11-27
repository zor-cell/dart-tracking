import base64
import re
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.core.socket import socket
from app.api.features.calibration.domain.calibration import Calibration
from app.api.features.detection.debug.trace import DetectionTrace
from app.api.features.calibration.domain.board_geometry import Segment
from app.api.features.detection.domain.board_check import BoardCheck
from app.api.features.detection.domain.detection import Dart
from app.api.features.detection.domain.detection_failure import DetectionFailure
from app.api.features.evaluation.domain.alignment import DartOutcome
from app.api.features.evaluation.services import accuracy, frame_sweeper
from app.infrastructure import database
from tests.api.support import X01
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
        other.send("remove_dart", index=1)

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


def test_removing_a_dart_reopens_the_visit_just_handed_over(room, game_id, session):
    with room(game_id) as device:
        for _ in range(3):
            device.throw(0)
        device.send("next_player")
        device.send("remove_dart", index=2, turn=0)

        for _ in range(5):
            state = device.next("game_state")

    assert (len(state["turns"]), state["currentPlayerIndex"], darts(state)) == (1, 0, ["0", "0"])
    kinds = session.sql(
        "SELECT kind FROM game_events WHERE game_id = :id AND kind IN ('visit_reopened', 'dart_removed') ORDER BY id",
        id=game_id,
    )
    assert [row[0] for row in kinds] == ["visit_reopened", "dart_removed"]


def test_a_command_that_changes_nothing_is_not_broadcast(room, game_id):
    with room(game_id) as device:
        device.send("remove_dart", index=0)
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


def test_darts_and_handovers_are_dated(room, game_id, session):
    with room(game_id) as device:
        device.throw(20)
        device.next("game_state")
        device.send("next_player")
        device.next("game_state")

    darts_dated = session.sql(
        "SELECT count(thrown_at) FROM game_darts WHERE game_id = :id", id=game_id
    )
    visits_ended = session.sql(
        "SELECT turn_index FROM game_turns WHERE game_id = :id AND ended_at IS NOT NULL",
        id=game_id,
    )
    assert darts_dated[0][0] == 3
    assert [row[0] for row in visits_ended] == [0]


@pytest.mark.parametrize("raw", ["not json", '{"type": "no_such_thing"}', '{"type": "register_dart", "value": 26}'])
def test_malformed_messages_are_dropped_and_the_connection_stays(room, game_id, raw):
    with room(game_id) as device:
        device.websocket.send_text(raw)
        device.throw(5)

        assert darts(device.next("game_state")) == ["5"]


def test_evaluation_switch_of_an_anonymous_game_needs_an_admin(room, game_id, register, session):
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


def test_the_owner_stops_keeping_frames_and_they_are_deleted(room, register, session, frames):
    alice, bob = register("alice"), register("bob")
    game_id = alice.new_game(alice.own_entry()["id"], evaluationEnabled=True)["id"]
    frames.write(game_id, "throw0_base.jpg", b"jpeg")

    with room(game_id) as device:
        device.send("authenticate", accessToken=bob.token)
        device.send("set_evaluation", enabled=False)
        device.throw(5)
        assert device.next("game_state")["evaluationEnabled"] is True

        device.send("authenticate", accessToken=alice.token)
        device.send("set_evaluation", enabled=False)
        assert device.next("game_state")["evaluationEnabled"] is False

    session.run(frame_sweeper.sweep)
    assert frames.names(game_id) == []


def test_frames_from_a_scoreboard_are_ignored(room, game_id):
    with room(game_id) as device:
        device.send("calibration_frame", image=jpeg(64, 48))
        device.send("detection_frame", image=jpeg(64, 48))
        device.send("board_check_frame", image=jpeg(64, 48))
        device.send("set_role", role="scoreboard")

        device.next("client_state", never=("calibration_result", "detection_result", "calibration_requested"))


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


def test_a_calibrated_camera_gets_its_outline_back_on_rejoining(room, camera, game_id, monkeypatch):
    monkeypatch.setattr(socket.board_detector, "detect_board", lambda image: Calibration(np.eye(3), 64, 48))
    with camera() as phone:
        phone.send("calibration_frame", image=jpeg(64, 48))
        outline = phone.next("calibration_result")["overlay"]

    with room(game_id, phone.id) as rejoined:
        result = rejoined.next("calibration_result", never=("calibration_requested",))
        assert result["success"] is True
        assert result["overlay"] == outline


def test_pulling_the_winning_darts_confirms_the_win_in_the_room(room, camera, game_id, monkeypatch):
    monkeypatch.setattr(socket.board_detector, "detect_board", lambda image: Calibration(np.eye(3), 64, 48))
    monkeypatch.setattr(socket.dart_detector, "detect_dart", lambda *args: DetectionFailure.DARTS_REMOVED)

    async def pulled(*_args):
        return True

    monkeypatch.setattr(socket, "_darts_pulled", pulled)
    with camera() as phone, room(game_id) as scoreboard:
        phone.send("calibration_frame", image=jpeg(64, 48))
        phone.next("calibration_result")
        win(scoreboard)

        phone.send("detection_frame", image=jpeg(64, 48), advanceOnPull=True)
        state = scoreboard.next("game_state", never=("calibration_requested", "turn_announcement"))
        assert state["winConfirmed"] is True


def test_the_win_is_confirmed_and_reopened_for_the_whole_room(room, game_id):
    with room(game_id) as one, room(game_id) as other:
        win(one)
        while other.next("game_state")["winnerId"] is None:
            pass
        assert other.state["winConfirmed"] is False

        one.send("set_win_confirmed", confirmed=True)
        assert other.next("game_state")["winConfirmed"] is True

        one.send("set_win_confirmed", confirmed=False)
        assert other.next("game_state")["winConfirmed"] is False

        one.send("set_win_confirmed", confirmed=True)
        other.next("game_state")
        one.send("replace_dart", index=2, value=2, multiplier=1)
        state = other.next("game_state")
        assert state["winnerId"] is None
        assert state["winConfirmed"] is False


def test_a_correction_with_a_consequence_asks_its_sender_before_booking(room, game_id):
    with room(game_id) as one, room(game_id) as other:
        for dart in [(20, 3), (20, 3), (20, 3), None, (20, 1), None, (20, 3), (19, 3), (1, 2), None]:
            if dart is None:
                one.send("next_player")
            else:
                one.throw(*dart)
        one.throw(5)
        correction = {"index": 2, "value": 2, "multiplier": 2, "turn": 2}
        one.send("replace_dart", **correction)

        pending = one.next("correction_pending")
        assert (pending["wonAt"], pending["dropped"]) == (2, 1)
        assert pending["winnerId"] == one.state["players"][0]["id"]
        assert pending["command"]["turn"] == 2

        one.send("replace_dart", **correction, confirmed=True)
        while other.next("game_state", never=("correction_pending",))["winnerId"] is None:
            pass
        assert len(other.state["turns"]) == 3
        assert other.state["winConfirmed"] is True
        assert [d["label"] for d in other.state["turns"][2]["darts"]] == ["T20", "T19", "D2"]


def win(device: Device) -> dict[str, Any]:
    """Play the first player out of 301: 180, then 121 over T20, T19, D2."""
    for dart in [(20, 3), (20, 3), (20, 3), None, (20, 1), None, (20, 3), (19, 3), (2, 2)]:
        if dart is None:
            device.send("next_player")
        else:
            device.throw(*dart)
        state = device.next("game_state")
    assert state["winnerId"] is not None
    return state


TRIGGER = {
    "peakBlocks": 3, "peakExcess": 2, "spanCols": 2, "spanRows": 2, "frames": 6,
    "timedOut": False, "gridCols": 16, "gridRows": 9,
}


@pytest.mark.parametrize(
    ("failure", "moves"),
    [
        (DetectionFailure.NO_CHANGE, True),
        (DetectionFailure.DARTS_REMOVED, True),
        (DetectionFailure.IMPLAUSIBLE_SHAPE, False),
    ],
)
def test_a_frame_without_a_dart_becomes_the_next_reference(camera, game_id, monkeypatch, failure, moves):
    monkeypatch.setattr(socket.board_detector, "detect_board", lambda image: Calibration(np.eye(3), 64, 48))
    seen = np.full((48, 64, 3), 7, np.uint8)

    def detect(*_args):
        socket.dart_detector.trace = DetectionTrace(aligned=seen)
        return failure

    monkeypatch.setattr(socket.dart_detector, "detect_dart", detect)
    with camera() as phone:
        phone.send("calibration_frame", image=jpeg(64, 48))
        phone.next("calibration_result")
        before = socket.detection_store.get(game_id, phone.id)

        phone.send("detection_frame", image=jpeg(64, 48))
        assert phone.next("detection_result")["failure"] == failure.value

        after = socket.detection_store.get(game_id, phone.id)
        assert (after is seen) is moves
        assert (after is before) is not moves


def test_handover_asks_the_cameras_to_calibrate_again(room, camera, game_id):
    with camera() as phone, room(game_id) as scoreboard:
        scoreboard.throw(20)
        scoreboard.send("next_player")
        scoreboard.next("game_state")
        scoreboard.next("game_state")

        phone.next("calibration_requested")


def test_pausing_reaches_the_room_and_resuming_recalibrates(room, camera, game_id):
    with camera() as phone, room(game_id) as scoreboard:
        scoreboard.send("set_tracking_paused", paused=True)
        assert phone.next("game_state")["trackingPaused"] is True

        scoreboard.send("set_tracking_paused", paused=False)
        assert phone.next("game_state")["trackingPaused"] is False
        phone.next("calibration_requested")


def test_handover_without_a_camera_calls_the_next_player_at_once(room, game_id):
    with room(game_id) as announcer:
        announcer.throw(20)
        announcer.send("next_player")

        call = announcer.next("turn_announcement")

    assert (call["player"], call["score"]) == ("Ben", 301)


def test_the_call_names_the_score_on_every_handover(room, game_id):
    with room(game_id) as announcer:
        for visit in ([(20, 3)] * 3, [(1, 1)], [(20, 3), (20, 3), (5, 1)]):
            for value, multiplier in visit:
                announcer.throw(value, multiplier)
            announcer.send("next_player")

        calls = [announcer.next("turn_announcement") for _ in range(3)]

    assert [(call["player"], call["score"]) for call in calls] == [("Ben", 301), ("Ann", 121), ("Ben", 300)]


def test_the_elimination_call_names_the_score_counted_up(room, anon):
    game_id = anon.new_game({"name": "Ann"}, {"name": "Ben"}, settings={"variant": "elimination"})["id"]
    with room(game_id) as announcer:
        for visit in ([(20, 3)], [(5, 1)]):
            for value, multiplier in visit:
                announcer.throw(value, multiplier)
            announcer.send("next_player")

        calls = [announcer.next("turn_announcement") for _ in range(2)]

    assert [(call["player"], call["score"]) for call in calls] == [("Ben", 0), ("Ann", 60)]


def test_handover_with_a_camera_waits_for_the_recalibration(room, camera, game_id):
    with camera(), room(game_id) as scoreboard:
        scoreboard.throw(20)
        scoreboard.send("next_player")
        scoreboard.throw(5)

        state = scoreboard.next("game_state", never=("turn_announcement",))
        while darts(state) != ["5"]:
            state = scoreboard.next("game_state", never=("turn_announcement",))


def test_a_failed_recalibration_is_said_once_and_still_calls_the_turn(room, camera, game_id):
    with camera() as phone, room(game_id) as scoreboard:
        heard = []
        for _ in range(2):
            scoreboard.throw(20)
            scoreboard.send("next_player")
            phone.next("calibration_requested")
            phone.send("calibration_frame", image=jpeg(640, 480))
            while (message := scoreboard.websocket.receive_json())["type"] != "turn_announcement":
                if message["type"] == "calibration_announcement":
                    heard.append(message["calibrated"])

    assert heard == [False]


def calibrated(phone: Device, monkeypatch) -> None:
    monkeypatch.setattr(socket.board_detector, "detect_board", lambda image: Calibration(np.eye(3), 64, 48))
    phone.send("calibration_frame", image=jpeg(64, 48))
    phone.next("calibration_result")


def hand_over(phone: Device) -> None:
    phone.throw(20)
    phone.next("game_state")
    phone.send("next_player")


def settled(phone: Device) -> None:
    """Wait until the server has handled everything the phone sent before."""
    phone.send("set_role", role="camera")
    phone.next("client_state")


def test_a_handover_calls_the_next_player_at_once_and_checks_the_board(camera, game_id, monkeypatch, session):
    seen = np.full((48, 64, 3), 7, np.uint8)
    monkeypatch.setattr(
        socket.dart_detector,
        "check_board",
        lambda *_args: BoardCheck(inliers=900, shift_mm=1.0, coverage=1.0, aligned=seen),
    )
    with camera() as phone:
        calibrated(phone, monkeypatch)
        anchor = socket.detection_store.anchor(game_id, phone.id)
        hand_over(phone)

        phone.next("board_check_requested", never=("calibration_requested",))
        assert phone.next("turn_announcement", never=("calibration_requested",))["player"] == "Ben"
        phone.send("board_check_frame", image=jpeg(64, 48))
        settled(phone)

        assert socket.detection_store.get(game_id, phone.id) is seen
        assert socket.detection_store.empty_board(game_id, phone.id) is seen
        assert socket.detection_store.anchor(game_id, phone.id) is anchor

    checks = session.sql(
        "SELECT accepted FROM game_events WHERE game_id = :id AND kind = 'board_checked'", id=game_id
    )
    assert [row[0] for row in checks] == [True]


def test_a_board_check_that_does_not_hold_recalibrates(camera, game_id, monkeypatch):
    monkeypatch.setattr(socket.dart_detector, "check_board", lambda *_args: BoardCheck(inliers=12))
    with camera() as phone:
        calibrated(phone, monkeypatch)
        before = socket.detection_store.get(game_id, phone.id)
        hand_over(phone)
        phone.next("board_check_requested")

        phone.send("board_check_frame", image=jpeg(64, 48))

        phone.next("calibration_requested")
        assert socket.detection_store.get(game_id, phone.id) is before


def test_a_board_check_from_an_uncalibrated_camera_recalibrates(camera):
    with camera() as phone:
        phone.send("board_check_frame", image=jpeg(64, 48))
        phone.next("calibration_requested")


def test_a_lost_alignment_recalibrates_before_the_next_player_is_called(camera, monkeypatch):
    monkeypatch.setattr(socket.dart_detector, "detect_dart", lambda *_args: DetectionFailure.ALIGNMENT_FAILED)
    with camera() as phone:
        calibrated(phone, monkeypatch)
        phone.send("detection_frame", image=jpeg(64, 48))
        phone.next("detection_result")
        hand_over(phone)

        phone.next("calibration_requested", never=("board_check_requested", "turn_announcement"))
        phone.send("calibration_frame", image=jpeg(64, 48))
        assert phone.next("turn_announcement")["player"] == "Ben"

        hand_over(phone)
        phone.next("board_check_requested", never=("calibration_requested",))


def locates_a_dart(monkeypatch, blob: np.ndarray) -> None:
    def detect(*_args):
        socket.dart_detector.trace = DetectionTrace(aligned=np.zeros((48, 64, 3), np.uint8), blob=blob)
        return Dart(tip_image=(30, 20), axis_image=((30, 20), (40, 20)), tip_board=(30, 20), segment=Segment(20, 1))

    monkeypatch.setattr(socket.dart_detector, "detect_dart", detect)


@pytest.mark.parametrize("pulled", [True, False])
def test_darts_still_in_at_the_handover_keep_the_empty_board(camera, game_id, monkeypatch, pulled):
    seen = np.full((48, 64, 3), 7, np.uint8)
    blob = np.array([[30, 20]], np.float32)
    locates_a_dart(monkeypatch, blob)
    monkeypatch.setattr(
        socket.dart_detector,
        "check_board",
        lambda *_args: BoardCheck(inliers=900, shift_mm=1.0, coverage=1.0, aligned=seen),
    )
    left = []
    monkeypatch.setattr(socket.dart_detector, "darts_pulled", lambda blobs, *_args: left.extend(blobs) or pulled)
    with camera() as phone:
        calibrated(phone, monkeypatch)
        empty_board = socket.detection_store.empty_board(game_id, phone.id)
        phone.send("detection_frame", image=jpeg(64, 48))
        assert darts(phone.next("game_state")) == ["20"]
        phone.send("next_player")
        phone.next("board_check_requested")

        phone.send("board_check_frame", image=jpeg(64, 48))
        settled(phone)

        assert left == [blob]
        assert socket.detection_store.get(game_id, phone.id) is seen
        assert socket.detection_store.empty_board(game_id, phone.id) is (seen if pulled else empty_board)


def test_a_dart_the_visit_has_no_room_for_is_not_remembered(camera, game_id, monkeypatch):
    locates_a_dart(monkeypatch, np.array([[30, 20]], np.float32))
    with camera() as phone:
        calibrated(phone, monkeypatch)
        for _ in range(3):
            phone.throw(1)
            phone.next("game_state")

        phone.send("detection_frame", image=jpeg(64, 48))
        assert darts(phone.next("game_state")) == ["1", "1", "1"]

        assert socket.detection_store.darts(game_id, phone.id) == []


def test_an_elimination_is_named_in_the_dart_call(room, anon):
    game_id = anon.new_game({"name": "Ann"}, {"name": "Ben"}, settings={"variant": "elimination"})["id"]
    with room(game_id) as announcer:
        announcer.throw(20)
        announcer.send("next_player")
        announcer.throw(20)

        calls = [announcer.next("dart_announcement") for _ in range(2)]

    assert [call["eliminated"] for call in calls] == [[], ["Ann"]]


def test_rematch_calls_the_old_room_over(room, game_id, anon):
    with room(game_id) as device:
        rematch = anon.post(
            "/games",
            json={
                "settings": X01,
                "players": [{"playerId": p["identityId"]} for p in device.state["players"]],
                "rematchOf": game_id,
            },
        ).json()

        assert device.next("rematch_started")["gameId"] == rematch["id"]


@pytest.mark.dataset
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


@pytest.mark.dataset
@pytest.mark.skipif(dataset_root() is None, reason="TESTDATA_DIR is not set")
def test_the_first_calibration_calls_the_opening_player_once(camera):
    entry = ("games/game_01a13481-1426-766f-b71d-524e8038c6ba", {"throw16"})
    base = next(iter(series_of(dataset_root(), entry).values()))[0][1]

    with camera() as device:
        device.send("calibration_frame", image=encoded(base))
        assert device.next("turn_announcement")["player"] == "Ann"
        device.send("calibration_frame", image=encoded(base))
        device.next("calibration_result", never=("turn_announcement",))
        device.send("register_dart", value=20, multiplier=1)
        device.next("dart_announcement", never=("turn_announcement",))


@pytest.mark.dataset
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
            device.next("board_check_requested", never=("calibration_requested",))
            assert device.next("turn_announcement")["player"] == "Ben"
            device.send("board_check_frame", image=encoded(base))
            device.send("set_role", role="camera")
            device.next("client_state", never=("calibration_requested",))
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


@pytest.mark.parametrize("kept", [False, True])
def test_a_game_keeping_frames_keeps_the_shot_of_a_failed_calibration(room, register, frames, kept):
    alice = register("alice")
    game_id = alice.new_game(alice.own_entry()["id"], evaluationEnabled=kept)["id"]

    with room(game_id) as device:
        device.send("set_role", role="camera")
        device.send("calibration_frame", image=jpeg(640, 480))
        assert device.next("calibration_result")["success"] is False

    assert any(name.startswith("calibration_") for name in frames.names(game_id)) is kept


@pytest.mark.dataset
@pytest.mark.skipif(dataset_root() is None, reason="TESTDATA_DIR is not set")
def test_an_evaluation_run_records_frames_and_events(room, register, session, frames):
    alice = register("alice")
    session.make_admin(alice)
    game_id = alice.new_game(alice.own_entry()["id"], evaluationEnabled=True)["id"]
    shots = next(
        shots
        for entry in manifest("gate")
        if entry[0].startswith("games/")
        for shots in series_of(dataset_root(), entry).values()
        if replay_series(shots)[0]["failure"] is None
    )

    with room(game_id) as device:
        device.send("set_role", role="camera")
        device.send("authenticate", accessToken=alice.token)
        device.send("calibration_frame", image=base64.b64encode(shots[0][1].read_bytes()).decode())
        assert device.next("calibration_result")["success"] is True
        booked = 0
        for _, path in shots[1:]:
            device.send("detection_frame", image=base64.b64encode(path.read_bytes()).decode())
            booked += device.next("detection_result")["success"]
        device.send("next_player")
        while device.next("game_state")["currentPlayerIndex"] != 0 or len(device.state["turns"]) < 2:
            pass

    kept = frames.read(game_id, "throw0_frames.txt").decode().splitlines()
    assert frames.read(game_id, "throw0_base.jpg") is not None
    darts = [name for name in frames.names(game_id) if re.fullmatch(r"throw0_dart\d+\.jpg", name)]
    assert sorted(darts) == [f"throw0_dart{i}.jpg" for i in range(1, len(kept) + 1)]

    async def judged():
        async with database.session_scope() as db:
            return await accuracy.judged_games(db, game_ids=[game_id], include_unfinished=True)

    (game,) = session.run(judged)
    assert len(game.judgements) == min(booked, 3)
    assert all(judgement.outcome is DartOutcome.CORRECT for judgement in game.judgements)


def test_a_located_dart_without_effect_is_marked_in_the_log(room, anon, session, monkeypatch):
    game_id = anon.new_game({"name": "Ann"}, {"name": "Ben"}, settings={"variant": "cricket"})["id"]
    fields = iter([Segment(9, 1), Segment(20, 3)])

    def detect(*_args):
        socket.dart_detector.trace = DetectionTrace(aligned=np.zeros((48, 64, 3), np.uint8))
        return Dart(tip_image=(30, 20), axis_image=((30, 20), (40, 20)), tip_board=(30, 20), segment=next(fields))

    monkeypatch.setattr(socket.dart_detector, "detect_dart", detect)
    with room(game_id) as phone:
        phone.send("set_role", role="camera")
        calibrated(phone, monkeypatch)
        for _ in range(2):
            phone.send("detection_frame", image=jpeg(64, 48))
            assert phone.next("detection_result")["success"] is True
            phone.next("game_state")

    rows = session.sql(
        "SELECT value, metrics ->> 'no_effect' FROM game_events WHERE game_id = :id AND kind = 'detected' ORDER BY id",
        id=game_id,
    )
    assert [tuple(row) for row in rows] == [(9, "1.0"), (20, None)]
