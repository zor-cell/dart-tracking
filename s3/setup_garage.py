"""Set up the single Garage node for the camera frames over its admin API: layout,
bucket, the app's key from S3_ACCESS_KEY/S3_SECRET_KEY and its rights, then move
the frames left on disk into the bucket. Runs as `garage-init` on every start."""

import argparse
import base64
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# The form Garage gives its own keys: `GK` and 12 bytes, then a 32-byte secret, in hex.
ACCESS_KEY = re.compile(r"GK[0-9a-f]{24}")
SECRET_KEY = re.compile(r"[0-9a-f]{64}")


class AdminApi:
    """Garage's admin API v2: one operation per path, a bearer token for all of them."""

    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self.token = token

    def call(self, operation: str, body: dict[str, Any] | None = None, **query: str) -> Any:
        """The operation's JSON answer, or None for a 404."""
        url = f"{self.url}/v2/{operation}"
        if query:
            url += "?" + "&".join(f"{key}={value}" for key, value in query.items())
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            url,
            data=data,
            method="GET" if body is None else "POST",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise SystemExit(f"{operation} failed: {error.code} {error.read().decode()}") from error


def wait_for(api: AdminApi, seconds: int) -> dict[str, Any]:
    """The cluster status once the node answers."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            return api.call("GetClusterStatus")
        except (urllib.error.URLError, ConnectionError) as error:
            if time.monotonic() > deadline:
                raise SystemExit(f"no answer from {api.url}: {error}") from error
            time.sleep(1)


def assign_layout(api: AdminApi, status: dict[str, Any], zone: str, capacity: int) -> None:
    """Give the one node a role and apply the layout, unless it has one already."""
    [node] = status["nodes"]
    if node.get("role"):
        print(f"layout: node {node['id'][:16]} already in zone {node['role']['zone']}")
        return
    layout = api.call(
        "UpdateClusterLayout",
        {"roles": [{"id": node["id"], "zone": zone, "capacity": capacity, "tags": []}]},
    )
    version = layout["version"] + 1
    api.call("ApplyClusterLayout", {"version": version})
    print(f"layout: node {node['id'][:16]} in zone {zone}, {capacity // 10**9} GB, version {version}")


def ensure_bucket(api: AdminApi, name: str) -> str:
    bucket = api.call("GetBucketInfo", globalAlias=name)
    if bucket is None:
        bucket = api.call("CreateBucket", {"globalAlias": name})
        print(f"bucket: created {name}")
    else:
        print(f"bucket: {name} exists")
    return bucket["id"]


def ensure_key(api: AdminApi, access_key: str, secret_key: str, name: str) -> None:
    """Bring in the app's key, unless Garage knows it already."""
    if api.call("GetKeyInfo", id=access_key) is not None:
        print(f"key: {access_key} exists")
        return
    api.call("ImportKey", {"accessKeyId": access_key, "secretAccessKey": secret_key, "name": name})
    print(f"key: imported {access_key}")


def move(folder: Path, endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
    """Move every file of the `game_<id>` folders under `folder` into the bucket,
    leaving the runners' `_` folders on disk."""
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="garage",
        config=Config(s3={"addressing_style": "path"}),
    )
    for game in sorted(folder.glob("game_*")):
        moved = 0
        for path in sorted(game.rglob("*")):
            name = path.relative_to(game).as_posix()
            if not path.is_file() or any(p.startswith("_") for p in name.split("/")):
                continue
            data = path.read_bytes()
            # Garage checks the body against this hash and refuses a damaged upload.
            digest = base64.b64encode(hashlib.md5(data).digest()).decode()
            client.put_object(Bucket=bucket, Key=f"{game.name}/{name}", Body=data, ContentMD5=digest)
            path.unlink()
            moved += 1
        for directory in sorted(game.rglob("*"), reverse=True) + [game]:
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        print(f"frames: moved {moved} files of {game.name} into {bucket}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait", type=int, default=60, help="seconds to wait for the node")
    args = parser.parse_args()

    env = os.environ
    access_key, secret_key = env.get("S3_ACCESS_KEY", ""), env.get("S3_SECRET_KEY", "")
    if not ACCESS_KEY.fullmatch(access_key) or not SECRET_KEY.fullmatch(secret_key):
        raise SystemExit(
            "S3_ACCESS_KEY must be GK and 24 hex digits (GK$(openssl rand -hex 12)), "
            "S3_SECRET_KEY 64 (openssl rand -hex 32)"
        )
    token = env.get("GARAGE_ADMIN_TOKEN")
    if not token:
        raise SystemExit("set GARAGE_ADMIN_TOKEN")

    api = AdminApi(env.get("GARAGE_ADMIN_URL", "http://garage:3903"), token)
    bucket = env.get("S3_BUCKET", "frames")
    capacity = int(env.get("GARAGE_CAPACITY_GB", "100")) * 10**9

    status = wait_for(api, args.wait)
    assign_layout(api, status, env.get("GARAGE_ZONE", "dc1"), capacity)
    bucket_id = ensure_bucket(api, bucket)
    ensure_key(api, access_key, secret_key, "dart-tracking")
    api.call(
        "AllowBucketKey",
        {
            "bucketId": bucket_id,
            "accessKeyId": access_key,
            "permissions": {"read": True, "write": True, "owner": False},
        },
    )
    print(f"rights: {access_key} may read and write {bucket}")

    frames = env.get("MOVE_FRAMES_FROM")
    if frames and Path(frames).is_dir():
        s3_url = env.get("S3_ENDPOINT") or "http://garage:3900"
        move(Path(frames), s3_url, access_key, secret_key, bucket)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
