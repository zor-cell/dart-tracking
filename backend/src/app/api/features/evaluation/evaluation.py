"""How well the tracker scored, read off the games that were played.

Admin-only: it reports on every account's games, not on the caller's own.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.api.features.auth.services.current_user import AdminUser
from app.api.features.evaluation.domain.breakdown import breakdowns_of
from app.api.features.evaluation.domain.evaluation_filter import EvaluationFilter
from app.api.features.evaluation.dto.accuracy import AccuracyReportDto, GameReportDto
from app.api.features.evaluation.services import accuracy
from app.api.features.evaluation.services.report_markdown import build_report
from app.api.features.game.domain.game_mode import GameMode
from app.infrastructure import database

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


def evaluation_filter(
    version_from: int | None = Query(None, alias="versionFrom"),
    version_to: int | None = Query(None, alias="versionTo"),
    mode: list[GameMode] = Query([]),
    test_run: bool | None = Query(None, alias="testRun"),
    since: datetime | None = None,
    until: datetime | None = None,
    tilt_from: float | None = Query(None, ge=0, le=90, alias="tiltFrom"),
    tilt_to: float | None = Query(None, ge=0, le=90, alias="tiltTo"),
) -> EvaluationFilter:
    return EvaluationFilter(
        version_from=version_from,
        version_to=version_to,
        modes=tuple(mode),
        test_run=test_run,
        since=since,
        until=until,
        tilt_from=tilt_from,
        tilt_to=tilt_to,
    )


Criteria = Annotated[EvaluationFilter, Depends(evaluation_filter)]


@router.get("/accuracy", response_model=AccuracyReportDto)
async def accuracy_report(user: AdminUser, criteria: Criteria) -> AccuracyReportDto:
    async with database.session_scope() as session:
        games = await accuracy.judged_games(session, criteria=criteria)

    return AccuracyReportDto.from_entity(accuracy.overview_of(games), breakdowns_of(games))


@router.get("/report", response_class=PlainTextResponse)
async def markdown_report(user: AdminUser, criteria: Criteria) -> PlainTextResponse:
    """The same selection as `/accuracy`, as a Markdown file to download."""
    async with database.session_scope() as session:
        games = await accuracy.judged_games(session, criteria=criteria)

    now = datetime.now()
    return PlainTextResponse(
        "\n".join(build_report(games, criteria, created_at=now)) + "\n",
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="accuracy_{now:%Y%m%d-%H%M%S}.md"'
        },
    )


@router.get("/games/{game_id}", response_model=GameReportDto)
async def game_report(user: AdminUser, game_id: str) -> GameReportDto:
    """One game's figures, finished or not, whatever the page's filters."""
    async with database.session_scope() as session:
        games = await accuracy.judged_games(session, game_ids=[game_id])
    if not games:
        raise HTTPException(status_code=404, detail="game has no judged darts")

    return GameReportDto.from_entity(accuracy.overview_of(games).games[0], breakdowns_of(games))


@router.get("/versions", response_model=list[int])
async def tracker_versions(user: AdminUser) -> list[int]:
    """The tracker versions the finished logged games were recorded with, newest first."""
    async with database.session_scope() as session:
        return await accuracy.versions(session)
