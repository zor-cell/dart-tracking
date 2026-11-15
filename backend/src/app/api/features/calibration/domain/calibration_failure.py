"""Why a calibration attempt failed: the stage that gave up, which the client turns
into advice.
"""

from enum import StrEnum


class CalibrationFailure(StrEnum):
    #: Image cannot be read
    INVALID_IMAGE = "invalid_image"

    #: Colour was found but no ellipse could be fitted to it, so whatever was
    #: found is not board-shaped.
    ELLIPSE_FIT_FAILED = "ellipse_fit_failed"

    #: The ring did not yield exactly 20 colour transitions, so the sector wires
    #: cannot be matched up.
    SECTOR_WIRES_UNCLEAR = "sector_wires_unclear"

    #: Wires were matched but the homography solve did not converge.
    HOMOGRAPHY_FAILED = "homography_failed"
