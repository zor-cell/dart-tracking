"""Reads a JPEG's pixel size from its header, without decoding the image."""

# Start-of-frame markers; C4, C8 and CC share the range but are not frames.
_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
# Markers that stand alone, without a length field.
_STANDALONE_MARKERS = {0x01, 0xD8, *range(0xD0, 0xD8)}


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) of a JPEG, or None if the data is not one."""
    if not data.startswith(b"\xff\xd8"):
        return None

    position = 2
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            return None
        marker = data[position + 1]
        if marker == 0xFF:
            position += 1
            continue
        if marker in _STANDALONE_MARKERS:
            position += 2
            continue
        if marker in _SOF_MARKERS:
            if position + 9 > len(data):
                return None
            height = int.from_bytes(data[position + 5 : position + 7], "big")
            width = int.from_bytes(data[position + 7 : position + 9], "big")
            return width, height
        length = int.from_bytes(data[position + 2 : position + 4], "big")
        if length < 2:
            return None
        position += 2 + length
    return None
