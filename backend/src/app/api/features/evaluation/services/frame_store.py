"""Where kept camera frames live: one key prefix per game in the S3 bucket of the
Garage node (see `s3/`)."""

import logging
from typing import Any, Protocol

from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)

_PREFIX = "game_"


class FrameStore(Protocol):
    """Files by game and name; a name is relative to the game's folder."""

    def write(self, game_id: str, name: str, data: bytes) -> None: ...
    def read(self, game_id: str, name: str) -> bytes | None: ...
    def names(self, game_id: str) -> list[str]: ...
    def remove(self, game_id: str, names: list[str]) -> None: ...
    def delete(self, game_id: str) -> None: ...
    def games(self) -> list[str]: ...


def folder_name(game_id: str) -> str:
    """A game's key prefix, and its folder in exports and pulled copies."""
    return f"{_PREFIX}{game_id}"


class S3FrameStore:
    """Keys `game_<id>/<name>` in one bucket."""

    def __init__(self, client: Any, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def _key(self, game_id: str, name: str) -> str:
        return f"{folder_name(game_id)}/{name}"

    def write(self, game_id: str, name: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self._key(game_id, name), Body=data)

    def read(self, game_id: str, name: str) -> bytes | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(game_id, name))
        except self.client.exceptions.NoSuchKey:
            return None
        return response["Body"].read()

    def names(self, game_id: str) -> list[str]:
        prefix = f"{folder_name(game_id)}/"
        pages = self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix
        )
        keys = (item["Key"] for page in pages for item in page.get("Contents", []))
        return sorted(key[len(prefix) :] for key in keys)

    def remove(self, game_id: str, names: list[str]) -> None:
        # One request deletes at most 1000 objects.
        for start in range(0, len(names), 1000):
            batch = names[start : start + 1000]
            objects = [{"Key": self._key(game_id, name)} for name in batch]
            self.client.delete_objects(
                Bucket=self.bucket, Delete={"Objects": objects, "Quiet": True}
            )

    def delete(self, game_id: str) -> None:
        self.remove(game_id, self.names(game_id))

    def games(self) -> list[str]:
        """The ids of the games the bucket holds files of."""
        pages = self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Delimiter="/"
        )
        prefixes = (item["Prefix"] for page in pages for item in page.get("CommonPrefixes", []))
        return sorted(prefix[len(_PREFIX) : -1] for prefix in prefixes if prefix.startswith(_PREFIX))


_store: FrameStore | None = None


def store() -> FrameStore:
    """The bucket, with the client built on first use."""
    global _store
    if _store is None:
        import boto3
        from botocore.config import Config

        settings = get_settings()
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(s3={"addressing_style": "path"}),
        )
        _store = S3FrameStore(client, settings.s3_bucket)
    return _store


def recorded(game_id: str) -> list[tuple[str, str]]:
    """A game's files with their archive path, `testdata/evaluation/game_<id>/…`."""
    return [
        (name, f"testdata/evaluation/{folder_name(game_id)}/{name}")
        for name in store().names(game_id)
    ]


def delete(game_id: str) -> None:
    """Remove every file kept for a game."""
    store().delete(game_id)
    logger.info("[evaluation] deleted the frames of %s", game_id)
