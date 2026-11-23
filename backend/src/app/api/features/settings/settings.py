"""The account's app settings: anyone reads (anonymous gets the defaults), only
accounts write.
"""

from fastapi import APIRouter

from app.api.features.auth.services.current_user import AuthenticatedUser, CurrentUser
from app.api.features.evaluation.persistence.frame_deletion_repository import (
    repository as frame_deletions,
)
from app.api.features.evaluation.services import frame_sweeper
from app.api.features.settings.domain.app_settings import DEFAULTS
from app.api.features.settings.dto.app_settings import AppSettingsDto
from app.api.features.settings.dto.filter_usage import FilterUsageDto
from app.api.features.settings.persistence.settings_repository import repository
from app.infrastructure import database

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=AppSettingsDto)
async def read_settings(user: CurrentUser) -> AppSettingsDto:
    if user is None:
        return AppSettingsDto.from_entity(DEFAULTS)

    async with database.session_scope() as session:
        settings = await repository.get(session, user.id)

    return AppSettingsDto.from_entity(settings)


@router.put("", response_model=AppSettingsDto)
async def write_settings(body: AppSettingsDto, user: AuthenticatedUser) -> AppSettingsDto:
    """Answers with what was stored, so the client adopts the server's reading
    rather than its own optimistic one. Turning frames off deletes the kept ones."""
    async with database.session_scope() as session:
        before = await repository.get(session, user.id)
        await repository.save(session, user.id, body.to_entity())
        settings = await repository.get(session, user.id)
        stopped = before.evaluation_enabled and not settings.evaluation_enabled
        if stopped:
            await frame_deletions.stop_keeping_owned(session, user.id)

    if stopped:
        frame_sweeper.wake()
    return AppSettingsDto.from_entity(settings)


@router.get("/filter-usage", response_model=FilterUsageDto)
async def read_filter_usage(user: AuthenticatedUser) -> FilterUsageDto:
    async with database.session_scope() as session:
        uses = await repository.filter_usage(session, user.id)

    return FilterUsageDto.from_entities(uses)


@router.put("/filter-usage", status_code=204)
async def write_filter_usage(body: FilterUsageDto, user: AuthenticatedUser) -> None:
    async with database.session_scope() as session:
        await repository.save_filter_usage(session, user.id, body.to_entities())

