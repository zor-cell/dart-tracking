from typing import Literal

from app.api.core.dto.base import CamelModel


class ThrowReceivedMessage(CamelModel):
    """Server -> client: acknowledgement of a throw frame.

    Stub for now — dart localization/scoring from the frame is future work
    (see roadmap.md §4, `dart_detected`); this just confirms receipt.
    """

    type: Literal["throw_received"] = "throw_received"
    bytes_received: int
