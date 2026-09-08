"""How well the tracker scored, read off the games that were played.

Admin-only: it reports on every account's games, not on the caller's own
(docs/feature/auswertung.md §7c).
"""

from fastapi import APIRouter

from app.api.features.auth.services.current_user import AdminUser
from app.api.features.evaluation.dto.accuracy import AccuracyReportDto
from app.api.features.evaluation.services import accuracy
from app.infrastructure import database

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


@router.get("/accuracy", response_model=AccuracyReportDto)
async def accuracy_report(user: AdminUser) -> AccuracyReportDto:
    async with database.session_scope() as session:
        overview = await accuracy.overview(session)

    return AccuracyReportDto.from_entity(overview)
