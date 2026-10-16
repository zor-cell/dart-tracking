"""The game selection flags shared by `report.py` and `export.py`, so both read
the same games as the evaluation page (`services.accuracy.judged_games`)."""

import argparse


def add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--test-runs-only",
        action="store_true",
        help="only games marked as a test run",
    )
    parser.add_argument(
        "--include-unfinished",
        action="store_true",
        help="also games without a winner",
    )
    parser.add_argument(
        "--min-version",
        type=int,
        help="only games played entirely with this tracker version or a later one",
    )
    parser.add_argument(
        "--version",
        type=int,
        help="only games played entirely with exactly this tracker version",
    )
