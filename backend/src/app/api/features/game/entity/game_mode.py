from enum import IntEnum


class GameMode(IntEnum):
    """Standard x01 modes. The value *is* the starting score, so the enum can be
    used directly in score arithmetic and serializes to a plain JSON number.
    """

    X01_301 = 301
    X01_501 = 501
    X01_701 = 701
