from enum import StrEnum


class CheckoutMode(StrEnum):
    """How a leg may be finished in x01.

    SINGLE_OUT: the leg ends the moment the remaining score hits zero, with any
    field. DOUBLE_OUT: the finishing dart must land in a double (the bullseye
    counts as the double bull). The choice only changes which checkout routes are
    valid; the serialized value is the plain string the frontend sends back.
    """

    SINGLE_OUT = "single_out"
    DOUBLE_OUT = "double_out"
