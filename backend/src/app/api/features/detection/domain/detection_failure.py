"""Why locating a dart gave up.

Mirrors `CalibrationFailure`: the stage that failed is more useful to the
client than a bare None, because each one suggests a different fix.
"""

from enum import StrEnum


class DetectionFailure(StrEnum):
    INVALID_IMAGE = "invalid_image"
    NOT_CALIBRATED = "not_calibrated"
    ALIGNMENT_FAILED = "alignment_failed"
    NO_CHANGE = "no_change"
    IMPLAUSIBLE_SHAPE = "implausible_shape"
