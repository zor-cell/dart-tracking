"""The announcer's voiced clips, and the phrase the settings page tests the sound with."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.core.services.request_language import current_language
from app.api.features.announcement.dto.speech_test import SpeechTestDto
from app.api.features.announcement.services.phrases import self_test_phrase
from app.api.features.announcement.services.speech import speech_store

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
async def speech_test() -> SpeechTestDto:
    """The test phrase in the request's language."""
    language = current_language.get()
    return SpeechTestDto(clips=await speech_store().urls([self_test_phrase(language)], language))
