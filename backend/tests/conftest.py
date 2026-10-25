def pytest_addoption(parser):
    parser.addoption(
        "--update-baseline",
        action="store_true",
        help="write the current CV results into the regression baseline instead of comparing",
    )
    parser.addoption(
        "--cv-set",
        choices=("gate", "corpus"),
        default="gate",
        help="replay the small gate set from tests/cv/gate.txt or the whole corpus",
    )
