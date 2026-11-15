import asyncio
import threading
from datetime import datetime

import numpy as np

from app.api.core.socket import socket
from app.api.features.auth.services import passwords
from app.api.features.evaluation.domain.accuracy import LoggedGame
from app.api.features.evaluation.services import accuracy, frame_buffer
from app.api.features.evaluation.services.frame_buffer import FrameBuffer, FrameKind
from app.api.features.statistics.persistence import overall_repository, statistics_repository


def beside_the_loop(owner, name, start, monkeypatch, result="done"):
    """Runs `start()` with `owner.name` replaced by work that only ends once the
    event loop has moved on, so it passes only when that work leaves the loop."""
    released = threading.Event()

    def work(*_args, **_kwargs):
        assert released.wait(timeout=5), "the work blocked the event loop"
        return result

    monkeypatch.setattr(owner, name, work)

    async def main():
        task = asyncio.create_task(start())
        await asyncio.sleep(0.05)
        released.set()
        return await task

    return asyncio.run(main())


def test_the_points_tally_leaves_the_event_loop_free(monkeypatch):
    async def rows(_self, *_args):
        return statistics_repository._Rows([], {}, [], [])

    monkeypatch.setattr(statistics_repository.StatisticsRepository, "_rows", rows)

    found = beside_the_loop(
        statistics_repository,
        "_overview",
        lambda: statistics_repository.repository.overview(None, "user"),
        monkeypatch,
    )

    assert found == "done"


def test_the_overall_tally_leaves_the_event_loop_free(monkeypatch):
    async def played(*_args):
        return []

    monkeypatch.setattr(overall_repository, "played_games", played)

    found = beside_the_loop(
        overall_repository,
        "_tally",
        lambda: overall_repository.repository.overview(None, "user"),
        monkeypatch,
    )

    assert found == "done"


def test_hashing_a_password_leaves_the_event_loop_free(monkeypatch):
    class Hasher:
        def hash(self, password): ...

        def verify(self, password, password_hash): ...

    hasher = Hasher()
    monkeypatch.setattr(passwords, "_hasher", hasher)

    hashed = beside_the_loop(hasher, "hash", lambda: passwords.hash_password("secret"), monkeypatch)
    verified = beside_the_loop(
        hasher, "verify", lambda: passwords.verify_password("secret", "hash"), monkeypatch, True
    )

    assert (hashed, verified) == ("done", True)


def test_judging_the_logged_games_leaves_the_event_loop_free(monkeypatch):
    game = LoggedGame("game", 501, datetime(2026, 1, 1), evaluation_enabled=True)

    async def logged(*_args, **_kwargs):
        return [game]

    async def events(*_args):
        return []

    monkeypatch.setattr(accuracy.repository, "logged_games", logged)
    monkeypatch.setattr(accuracy.repository, "events", events)

    found = beside_the_loop(accuracy, "_judged", lambda: accuracy.judged_games(None), monkeypatch)

    assert found == "done"


def test_writing_a_throw_series_leaves_the_event_loop_free(monkeypatch):
    frames = FrameBuffer()
    frames.remember("game", b"base")
    frames.add("game", b"dart", FrameKind.BOOKED)

    found = beside_the_loop(
        frame_buffer, "_write_series", lambda: frames.flush("game", 0), monkeypatch
    )

    assert found == "done"


def test_checking_for_pulled_darts_leaves_the_event_loop_free(monkeypatch):
    board = np.zeros((4, 4, 3), dtype=np.uint8)

    pulled = beside_the_loop(
        socket.dart_detector,
        "darts_pulled",
        lambda: socket._darts_pulled("game", "camera", board, board),
        monkeypatch,
        True,
    )

    assert pulled is True
