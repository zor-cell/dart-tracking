import boto3
import pytest
from moto import mock_aws

from app.api.features.evaluation.services.frame_store import S3FrameStore


@pytest.fixture
def files():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="frames")
        yield S3FrameStore(client, "frames")


def test_files_are_kept_per_game(files):
    files.write("a", "throw0_base.jpg", b"base")
    files.write("a", "throw0_dart1.jpg", b"dart")
    files.write("b", "throw0_base.jpg", b"other")

    assert files.names("a") == ["throw0_base.jpg", "throw0_dart1.jpg"]
    assert files.read("a", "throw0_dart1.jpg") == b"dart"
    assert files.read("a", "missing.jpg") is None


def test_removing_and_deleting(files):
    for name in ("throw0_base.jpg", "throw0_dart1.jpg", "throw0_dart2.jpg"):
        files.write("a", name, b"x")
    files.write("b", "throw0_base.jpg", b"x")

    files.remove("a", ["throw0_dart1.jpg", "throw0_dart2.jpg"])
    assert files.names("a") == ["throw0_base.jpg"]

    files.delete("a")
    assert files.names("a") == []
    assert files.names("b") == ["throw0_base.jpg"]


def test_more_than_a_thousand_files_are_deleted_in_batches(files):
    for index in range(1001):
        files.write("a", f"f{index}.jpg", b"")

    files.delete("a")

    assert files.names("a") == []


def test_the_games_in_the_bucket(files):
    files.write("a", "throw0_base.jpg", b"x")
    files.write("b", "sub/ground_truth.txt", b"x")
    files.client.put_object(Bucket="frames", Key="stray.txt", Body=b"x")

    assert files.games() == ["a", "b"]
