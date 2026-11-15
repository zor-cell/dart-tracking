import asyncio
import threading

from app.api.features.statistics.persistence import overall_repository, statistics_repository


def tally_beside_the_loop(module, tally_name, start_overview, monkeypatch):
    """Runs an overview whose tally only ends once the event loop has moved on."""
    released = threading.Event()

    def tally(_rows):
        assert released.wait(timeout=5), "the tally blocked the event loop"
        return "tally"

    monkeypatch.setattr(module, tally_name, tally)

    async def main():
        task = asyncio.create_task(start_overview())
        await asyncio.sleep(0.05)
        released.set()
        return await task

    return asyncio.run(main())


def test_the_points_tally_leaves_the_event_loop_free(monkeypatch):
    async def rows(_self, *_args):
        return statistics_repository._Rows([], {}, [], [])

    monkeypatch.setattr(statistics_repository.StatisticsRepository, "_rows", rows)

    found = tally_beside_the_loop(
        statistics_repository,
        "_overview",
        lambda: statistics_repository.repository.overview(None, "user"),
        monkeypatch,
    )

    assert found == "tally"


def test_the_overall_tally_leaves_the_event_loop_free(monkeypatch):
    async def played(*_args):
        return []

    monkeypatch.setattr(overall_repository, "played_games", played)

    found = tally_beside_the_loop(
        overall_repository,
        "_tally",
        lambda: overall_repository.repository.overview(None, "user"),
        monkeypatch,
    )

    assert found == "tally"
