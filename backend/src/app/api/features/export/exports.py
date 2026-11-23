"""The account's data export as one zip download."""

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api.core.services import rate_limit
from app.api.features.auth.services.current_user import AuthenticatedUser
from app.api.features.export.services.archive import write_export

router = APIRouter(prefix="/export", tags=["Export"])

# Exports per account per hour.
_EXPORT_LIMIT, _EXPORT_WINDOW = 10, 60 * 60


@router.get("", response_class=FileResponse)
async def export_account(user: AuthenticatedUser, frames: bool = False) -> FileResponse:
    """`frames` adds the camera frames kept of the games this account set up."""
    await rate_limit.enforce("export", user.id, _EXPORT_LIMIT, _EXPORT_WINDOW)
    path = await write_export(user, frames=frames)
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"dart-tracking-{datetime.now(UTC):%Y-%m-%d}.zip",
        # Already compressed: keeps the gzip middleware from packing it again.
        headers={"Content-Encoding": "identity"},
        background=BackgroundTask(path.unlink, missing_ok=True),
    )
