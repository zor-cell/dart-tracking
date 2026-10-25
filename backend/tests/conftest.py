def pytest_addoption(parser):
    parser.addoption(
        "--update-baseline",
        action="store_true",
        help="write the current CV results as the new regression baseline instead of comparing",
    )
