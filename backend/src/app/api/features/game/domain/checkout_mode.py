from enum import StrEnum


class CheckoutMode(StrEnum):
    """How a leg may be finished in x01: with any field (SINGLE_OUT) or with a double,
    Bull included (DOUBLE_OUT).
    """

    SINGLE_OUT = "single_out"
    DOUBLE_OUT = "double_out"
