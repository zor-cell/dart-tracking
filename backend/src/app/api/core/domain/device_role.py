from enum import StrEnum


class DeviceRole(StrEnum):
    """What a device does in a game: whether it films the board."""

    CAMERA = "camera"
    SCOREBOARD = "scoreboard"
