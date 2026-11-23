"""Packs an account's data export into a zip file on disk."""

import asyncio
import os
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from app.api.features.auth.domain.user import User
from app.api.features.evaluation.services.frame_store import recorded, store
from app.api.features.export.dto.account_export import AccountFileDto, GamesFileDto
from app.api.features.export.persistence.export_repository import ExportRows, assemble, repository
from app.infrastructure import database


async def write_export(user: User, *, frames: bool) -> Path:
    """The zip with `account.json`, `games.json` and, with `frames`, the recorded camera
    frames; the caller deletes it."""
    async with database.session_scope() as session:
        rows = await repository.load(session, user)
    return await asyncio.to_thread(_write, rows, frames, datetime.now(UTC))


def _write(rows: ExportRows, frames: bool, exported_at: datetime) -> Path:
    export = assemble(rows)
    handle, name = tempfile.mkstemp(prefix="export-", suffix=".zip")
    os.close(handle)
    path = Path(name)
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            account = AccountFileDto.from_entity(export, exported_at)
            archive.writestr("account.json", account.model_dump_json(by_alias=True, indent=2))
            games = GamesFileDto.from_entity(export)
            archive.writestr("games.json", games.model_dump_json(by_alias=True, indent=2))
            if frames:
                files = store()
                for game_id in export.recorded_game_ids:
                    for name, arcname in recorded(game_id):
                        data = files.read(game_id, name) or b""
                        archive.writestr(arcname, data, compress_type=zipfile.ZIP_STORED)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path
