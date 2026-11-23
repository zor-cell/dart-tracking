import importlib.util
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

_SCRIPT = Path(__file__).resolve().parents[3] / "s3" / "setup_garage.py"
_spec = importlib.util.spec_from_file_location("setup_garage", _SCRIPT)
setup_garage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(setup_garage)

KEY, SECRET = "GK0123456789abcdef01234567", "0123456789abcdef" * 4


class FakeAdmin:
    """Answers like a fresh single-node Garage, keeping what the script set up."""

    def __init__(self) -> None:
        self.role = None
        self.buckets: dict[str, str] = {}
        self.keys: dict[str, str] = {}
        self.allowed: list[dict] = []
        self.calls: list[str] = []

    def call(self, operation, body=None, **query):
        self.calls.append(operation)
        match operation:
            case "GetClusterStatus":
                return {"nodes": [{"id": "n" * 64, "role": self.role}]}
            case "UpdateClusterLayout":
                self.staged = body["roles"][0]
                return {"version": 0}
            case "ApplyClusterLayout":
                assert body == {"version": 1}
                self.role = self.staged
                return {}
            case "GetBucketInfo":
                bucket = self.buckets.get(query["globalAlias"])
                return None if bucket is None else {"id": bucket}
            case "CreateBucket":
                self.buckets[body["globalAlias"]] = "b1"
                return {"id": "b1"}
            case "GetKeyInfo":
                return {"accessKeyId": query["id"]} if query["id"] in self.keys else None
            case "ImportKey":
                self.keys[body["accessKeyId"]] = body["secretAccessKey"]
                return {}
            case "AllowBucketKey":
                self.allowed.append(body)
                return {}
        raise AssertionError(operation)


@pytest.fixture
def api(monkeypatch):
    fake = FakeAdmin()
    monkeypatch.setattr(setup_garage, "AdminApi", lambda url, token: fake)
    monkeypatch.setattr(sys, "argv", ["setup_garage.py"])
    monkeypatch.setenv("GARAGE_ADMIN_TOKEN", "token")
    monkeypatch.setenv("GARAGE_CAPACITY_GB", "5")
    return fake


def test_a_fresh_node_gets_a_layout_the_bucket_and_the_apps_key(api, monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", KEY)
    monkeypatch.setenv("S3_SECRET_KEY", SECRET)

    assert setup_garage.main() == 0

    assert (api.role["zone"], api.role["capacity"]) == ("dc1", 5 * 10**9)
    assert api.buckets == {"frames": "b1"}
    assert api.keys == {KEY: SECRET}
    assert api.allowed[-1]["permissions"] == {"read": True, "write": True, "owner": False}


def test_running_it_again_changes_nothing(api, monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", KEY)
    monkeypatch.setenv("S3_SECRET_KEY", SECRET)
    setup_garage.main()
    api.calls.clear()

    assert setup_garage.main() == 0
    assert not {"UpdateClusterLayout", "ApplyClusterLayout", "CreateBucket", "ImportKey"} & set(api.calls)


@pytest.mark.parametrize("key", ["", "my-key"])
def test_a_missing_key_or_one_not_in_garages_form_is_refused(api, monkeypatch, key):
    monkeypatch.setenv("S3_ACCESS_KEY", key)
    monkeypatch.setenv("S3_SECRET_KEY", SECRET)

    with pytest.raises(SystemExit):
        setup_garage.main()
    assert api.calls == []


@pytest.fixture
def bucket(monkeypatch):
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="frames")
        monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: client)
        yield client


def test_frames_on_disk_move_into_the_bucket(api, bucket, monkeypatch, tmp_path):
    game = tmp_path / "game_a"
    (game / "_results_debug").mkdir(parents=True)
    (game / "throw0_base.jpg").write_bytes(b"base")
    (game / "_results_debug" / "run.png").write_bytes(b"run")
    (tmp_path / "game_b").mkdir()
    (tmp_path / "game_b" / "throw0_base.jpg").write_bytes(b"other")
    monkeypatch.setenv("S3_ACCESS_KEY", KEY)
    monkeypatch.setenv("S3_SECRET_KEY", SECRET)
    monkeypatch.setenv("MOVE_FRAMES_FROM", str(tmp_path))

    assert setup_garage.main() == 0

    keys = sorted(item["Key"] for item in bucket.list_objects_v2(Bucket="frames")["Contents"])
    assert keys == ["game_a/throw0_base.jpg", "game_b/throw0_base.jpg"]
    assert bucket.get_object(Bucket="frames", Key="game_b/throw0_base.jpg")["Body"].read() == b"other"
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")) == [
        "game_a",
        "game_a/_results_debug",
        "game_a/_results_debug/run.png",
    ]


def test_without_a_folder_to_move_nothing_is_touched(api, bucket, monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", KEY)
    monkeypatch.setenv("S3_SECRET_KEY", SECRET)
    monkeypatch.setenv("MOVE_FRAMES_FROM", "")

    assert setup_garage.main() == 0
    assert "Contents" not in bucket.list_objects_v2(Bucket="frames")
