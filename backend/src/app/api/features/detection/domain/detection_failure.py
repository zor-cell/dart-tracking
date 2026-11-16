"""Why locating a dart gave up: the stage that failed, like `CalibrationFailure`."""

from enum import StrEnum


class DetectionFailure(StrEnum):
    INVALID_IMAGE = "invalid_image"
    NOT_CALIBRATED = "not_calibrated"
    ALIGNMENT_FAILED = "alignment_failed"
    NO_CHANGE = "no_change"
    IMPLAUSIBLE_SHAPE = "implausible_shape"
    DARTS_REMOVED = "darts_removed"

    @property
    def moves_reference(self) -> bool:
        """Whether the frame still becomes the next throw's reference: it shows no dart-sized
        change that a later throw must be told apart from."""
        return self in (DetectionFailure.NO_CHANGE, DetectionFailure.DARTS_REMOVED)
