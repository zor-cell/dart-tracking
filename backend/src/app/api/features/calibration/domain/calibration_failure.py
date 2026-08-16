"""Why a calibration attempt failed.

Each value names the stage that gave up, which is what makes it actionable:
the client turns it into advice ("get closer", "avoid shadows") instead of a
bare "not recognised", and the evaluation in zeitplan.md Phase 4 can count how
often each cause occurs rather than just the failure rate.
"""

from enum import StrEnum


class CalibrationFailure(StrEnum):
    #: Image cannot be read
    INVALID_IMAGE = "invalid_image"

    #: Colour was found but no ellipse could be fitted to it, so whatever was
    #: found is not board-shaped.
    ELLIPSE_FIT_FAILED = "ellipse_fit_failed"

    #: The ring was traced but did not yield exactly 20 colour transitions, so
    #: the sector wires cannot be matched up. Usually part of the board is
    #: occluded, cropped, or lost in shadow.
    SECTOR_WIRES_UNCLEAR = "sector_wires_unclear"

    #: Wires were matched but the homography solve did not converge.
    HOMOGRAPHY_FAILED = "homography_failed"
