import pytest

from app.api.features.evaluation.services import frame_store
from tests.frames import MemoryFrameStore


def pytest_addoption(parser):
    parser.addoption(
        "--update-baseline",
        action="store_true",
        help="write the current CV results into the regression baseline instead of comparing",
    )
    parser.addoption(
        "--cv-set",
        choices=("gate", "dataset"),
        default="gate",
        help="replay the small gate set from tests/cv/gate.txt or the whole dataset",
    )


@pytest.fixture(autouse=True)
def frames(monkeypatch):
    """The frame store every test writes to, in memory."""
    files = MemoryFrameStore()
    monkeypatch.setattr(frame_store, "_store", files)
    return files
