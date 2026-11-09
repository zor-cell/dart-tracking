import io
import wave


def silent_wav(text: str, language: object) -> bytes:
    """A short silent clip in place of Piper's voice."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(bytes(160))
    return buffer.getvalue()
