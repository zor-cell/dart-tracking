"""The account's app settings: anyone reads (anonymous gets the defaults), only
accounts write; the debug and recording switches are admin only.
"""

from fastapi import APIRouter

from app.api.features.auth.domain.user import User
from app.api.features.auth.services.current_user import AuthenticatedUser, CurrentUser
from app.api.features.settings.domain.app_settings import DEFAULTS, AppSettings
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

    return AppSettingsDto.from_entity(_visible_to(settings, user))


@router.put("", response_model=AppSettingsDto)
async def write_settings(body: AppSettingsDto, user: AuthenticatedUser) -> AppSettingsDto:
    """Answers with what was stored, so the client adopts the server's reading
    rather than its own optimistic one."""
    async with database.session_scope() as session:
        await repository.save(session, user.id, _visible_to(body.to_entity(), user))
        settings = await repository.get(session, user.id)

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


def _visible_to(settings: AppSettings, user: User) -> AppSettings:
    """What this account may see and set of `settings`."""
    return settings if user.is_admin else settings.without_diagnostics()
