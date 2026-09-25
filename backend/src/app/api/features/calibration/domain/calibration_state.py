"""How far the game's board calibration is, as every device in the room shows it.

See docs/feature/done/multi-device.md §5c.
"""

from enum import StrEnum


class CalibrationState(StrEnum):
    #: No camera in the room; darts are entered by hand.
    NO_CAMERA = "no_camera"

    #: A camera is there, but none that scores has a calibration.
    UNCALIBRATED = "uncalibrated"

    #: An attempt that decides the scoring calibration is running.
    CALIBRATING = "calibrating"

    #: The scoring camera is connected and holds a calibration.
    CALIBRATED = "calibrated"

    #: The scoring camera's latest attempt failed.
    FAILED = "failed"


def calibration_state(
    *, camera_connected: bool, scoring_connected: bool, calibrating: bool, failed: bool
) -> CalibrationState:
    """Collapse the room's calibration facts into the one state a device shows."""
    if not camera_connected:
        return CalibrationState.NO_CAMERA
    if calibrating:
        return CalibrationState.CALIBRATING
    if failed:
        return CalibrationState.FAILED
    if scoring_connected:
        return CalibrationState.CALIBRATED
    return CalibrationState.UNCALIBRATED
