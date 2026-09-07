"""How this account wants the app to behave.

Reading is open to anyone — an anonymous session is told the defaults, which is
what it runs on. Writing needs an account: there is nowhere to put the answer
otherwise (docs/feature/done/einstellungen.md).
"""

from fastapi import APIRouter

from app.api.features.auth.services.current_user import AuthenticatedUser, CurrentUser
from app.api.features.settings.domain.app_settings import DEFAULTS
from app.api.features.settings.dto.app_settings import AppSettingsDto
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
    rather than its own optimistic one."""
    async with database.session_scope() as session:
        await repository.save(session, user.id, body.to_entity())
        settings = await repository.get(session, user.id)

    return AppSettingsDto.from_entity(settings)
