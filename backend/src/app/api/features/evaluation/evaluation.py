"""How well the tracker scored, read off the games that were played.

Admin-only: it reports on every account's games, not on the caller's own.
"""

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.features.auth.services.current_user import AdminUser
from app.api.features.evaluation.domain.evaluation_filter import EvaluationFilter
from app.api.features.evaluation.dto.accuracy import AccuracyReportDto
from app.api.features.evaluation.services import accuracy
from app.api.features.game.domain.game_mode import GameMode
from app.infrastructure import database

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


@router.get("/accuracy", response_model=AccuracyReportDto)
async def accuracy_report(
    user: AdminUser,
    version_from: int | None = Query(None, alias="versionFrom"),
    version_to: int | None = Query(None, alias="versionTo"),
    mode: list[GameMode] = Query([]),
    test_run: bool | None = Query(None, alias="testRun"),
    since: datetime | None = None,
    until: datetime | None = None,
    tilt_from: float | None = Query(None, ge=0, le=90, alias="tiltFrom"),
    tilt_to: float | None = Query(None, ge=0, le=90, alias="tiltTo"),
) -> AccuracyReportDto:
    criteria = EvaluationFilter(
        version_from=version_from,
        version_to=version_to,
        modes=tuple(mode),
        test_run=test_run,
        since=since,
        until=until,
        tilt_from=tilt_from,
        tilt_to=tilt_to,
    )
    async with database.session_scope() as session:
        overview = await accuracy.overview(session, criteria)

    return AccuracyReportDto.from_entity(overview)


@router.get("/versions", response_model=list[int])
async def tracker_versions(user: AdminUser) -> list[int]:
    """The tracker versions the finished logged games were recorded with, newest first."""
    async with database.session_scope() as session:
        return await accuracy.versions(session)
