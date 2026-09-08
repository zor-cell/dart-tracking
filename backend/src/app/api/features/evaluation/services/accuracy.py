"""Turns the stored event logs into the numbers the evaluation page shows."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.features.evaluation.domain.accuracy import (
    AccuracyOverview,
    GameAccuracy,
    Judgement,
    judge,
    summarise,
)
from app.api.features.evaluation.domain.visit_replay import Visit, replay
from app.api.features.evaluation.persistence.evaluation_repository import repository


async def overview(session: AsyncSession) -> AccuracyOverview:
    """Every logged game, newest first, and the totals over all of them. A game
    nobody filmed is left out: it would read as darts the camera never saw."""
    visits: list[Visit] = []
    judgements: list[Judgement] = []
    per_game: list[GameAccuracy] = []

    for game in await repository.logged_games(session, evaluation_only=False):
        events = await repository.events(session, game.id)
        filmed = [visit for visit in replay(events) if visit.tracked]
        if not filmed:
            continue

        judged = [j for visit in filmed for j in judge(game.id, visit)]
        per_game.append(GameAccuracy(game=game, accuracy=summarise(1, filmed, judged)))
        visits += filmed
        judgements += judged

    per_game.reverse()
    return AccuracyOverview(
        total=summarise(len(per_game), visits, judgements), games=per_game
    )
