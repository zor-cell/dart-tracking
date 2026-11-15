"""Turns the stored event logs into the numbers the evaluation page shows."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.evaluation.domain.accuracy import (
    AccuracyOverview,
    GameAccuracy,
    JudgedGame,
    LoggedGame,
    judge,
    summarise,
)
from app.api.features.evaluation.domain.evaluation_filter import EvaluationFilter
from app.api.features.evaluation.domain.game_event import GameEvent
from app.api.features.evaluation.domain.visit_replay import replay
from app.api.features.evaluation.persistence.evaluation_repository import repository


async def judged_games(
    session: AsyncSession,
    *,
    game_ids: list[str] | None = None,
    test_runs_only: bool = False,
    include_unfinished: bool = False,
    min_version: int | None = None,
    version: int | None = None,
    criteria: EvaluationFilter = EvaluationFilter(),
) -> list[JudgedGame]:
    """The games the page, the report and the export read, oldest first: finished ones
    by default, explicit ids unfiltered, none without a judged dart.
    """
    games = await repository.logged_games(
        session,
        evaluation_only=test_runs_only and not game_ids,
        finished_only=not include_unfinished and not game_ids,
        game_ids=game_ids or None,
    )
    if min_version is not None:
        games = [
            game
            for game in games
            if game.tracker_versions and game.tracker_versions[0] >= min_version
        ]
    if version is not None:
        games = [game for game in games if game.tracker_versions == (version,)]
    games = [game for game in games if criteria.selects(game)]

    events = await repository.events(session, [game.id for game in games])
    logs = [(game, events.get(game.id, [])) for game in games]
    return await asyncio.to_thread(_judged, logs, criteria)


def _judged(
    logs: list[tuple[LoggedGame, list[GameEvent]]], criteria: EvaluationFilter
) -> list[JudgedGame]:
    """The logged games with at least one judged dart the filter's camera selects."""
    judged: list[JudgedGame] = []
    for game, events in logs:
        visits = [visit for visit in replay(events) if visit.tracked]
        judgements = [j for visit in visits for j in judge(game.id, visit)]
        if judgements:
            entry = JudgedGame(game, events, visits, judgements)
            if criteria.selects_camera(entry.camera):
                judged.append(entry)
    return judged


async def versions(session: AsyncSession) -> list[int]:
    """The tracker versions the finished logged games were recorded with, newest first."""
    games = await repository.logged_games(session, evaluation_only=False, finished_only=True)
    return sorted({version for game in games for version in game.tracker_versions}, reverse=True)


def overview_of(games: list[JudgedGame]) -> AccuracyOverview:
    """Every game on its own, newest first, and the totals over all of them."""
    per_game = [
        GameAccuracy(
            game=g.game, accuracy=summarise(1, g.visits, g.judgements), camera=g.camera
        )
        for g in reversed(games)
    ]
    return AccuracyOverview(
        total=summarise(
            len(games),
            [visit for g in games for visit in g.visits],
            [j for g in games for j in g.judgements],
        ),
        games=per_game,
    )
