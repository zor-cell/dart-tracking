from enum import StrEnum


class DeviceRole(StrEnum):
    """What a device does in a game (see docs/feature/multi-device.md).

    Says nothing about what the device may change — a scoreboard is explicitly
    the way to correct a misread — only whether it films the board.
    """

    CAMERA = "camera"
    SCOREBOARD = "scoreboard"
