"""Who an announcing device speaks as."""

from app.api.core.domain.language import Language
from app.api.features.announcement.domain.speaker import Speaker
from app.api.features.settings.domain.app_settings import DEFAULTS
from app.api.features.settings.persistence.settings_repository import repository as settings_repository
from app.infrastructure import database


async def speaker_for(user_id: str | None, device_language: Language) -> Speaker:
    """The account's voice and language; without a pick, the language the device shows the app in."""
    settings = DEFAULTS
    if user_id is not None:
        async with database.session_scope() as session:
            settings = await settings_repository.get(session, user_id)
    return Speaker(settings.announcer_language or device_language, settings.announcer_voice)
