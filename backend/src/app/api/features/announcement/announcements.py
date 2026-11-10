"""The announcer's voiced clips, and the phrase the settings page tests the sound with."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.core.services.request_language import current_language
from app.api.features.announcement.dto.speech_test import SpeechTestDto
from app.api.features.announcement.services.phrases import self_test_phrase
from app.api.features.announcement.services.speakers import speaker_for
from app.api.features.announcement.services.speech import speech_store
from app.api.features.auth.services.current_user import CurrentUser

router = APIRouter(prefix="/announcer", tags=["Announcer"])


@router.get("/clips/{clip}.wav", response_class=FileResponse)
async def clip(clip: str) -> FileResponse:
    """A clip never changes under its id, so it may be cached for good."""
    path = speech_store().path(clip)
    if path is None:
        raise HTTPException(status_code=404, detail="clip_not_found")
    return FileResponse(
        path,
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/test", response_model=SpeechTestDto)
async def speech_test(user: CurrentUser) -> SpeechTestDto:
    """The test phrase as the account's announcer speaks it, else in the request's language."""
    speaker = await speaker_for(None if user is None else user.id, current_language.get())
    clips = await speech_store().urls([self_test_phrase(speaker.language)], speaker)
    return SpeechTestDto(clips=clips)
