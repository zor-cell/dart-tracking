import sys

from scripts.evaluation import pull


def test_pulling_copies_every_game_the_bucket_holds(frames, monkeypatch, tmp_path):
    frames.write("a", "throw0_base.jpg", b"base")
    frames.write("a", "sub/ground_truth.txt", b"truth")
    frames.write("b", "throw0_base.jpg", b"other")
    monkeypatch.setattr(sys, "argv", ["pull.py", "--out", str(tmp_path)])

    assert pull.main() == 0

    assert (tmp_path / "game_a" / "sub" / "ground_truth.txt").read_bytes() == b"truth"
    assert (tmp_path / "game_b" / "throw0_base.jpg").read_bytes() == b"other"


def test_pulling_named_games_only(frames, monkeypatch, tmp_path):
    frames.write("a", "throw0_base.jpg", b"base")
    frames.write("b", "throw0_base.jpg", b"other")
    monkeypatch.setattr(sys, "argv", ["pull.py", "b", "--out", str(tmp_path)])

    pull.main()

    assert sorted(path.name for path in tmp_path.iterdir()) == ["game_b"]
