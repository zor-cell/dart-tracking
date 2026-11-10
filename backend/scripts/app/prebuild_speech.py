"""Download the announcer's Piper voices and voice every phrase that names no player.
Run by the Dockerfile; locally it fills `backend/voices` and `backend/speech`."""

import argparse
import sys
import time
from pathlib import Path

# Import app.* from src/, as `--app-dir src` does at runtime.
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND / "src"))

from piper.download_voices import download_voice  # noqa: E402

from app.api.features.announcement.services.phrases import fixed_phrases  # noqa: E402
from app.api.features.announcement.services.speech import (  # noqa: E402
    VOICES,
    PiperSynthesizer,
    SpeechStore,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voices", type=Path, default=_BACKEND / "voices")
    parser.add_argument("--out", type=Path, default=_BACKEND / "speech")
    args = parser.parse_args()

    args.voices.mkdir(parents=True, exist_ok=True)
    for voice in VOICES.values():
        if not (args.voices / f"{voice}.onnx").is_file():
            print(f"downloading {voice}")
            download_voice(voice, args.voices)

    store = SpeechStore(PiperSynthesizer(args.voices), args.out, None)
    for speaker, voice in VOICES.items():
        started = time.perf_counter()
        phrases = fixed_phrases(speaker.language)
        for phrase in phrases:
            store.make(phrase, speaker)
        print(f"{voice}: {len(phrases)} clips in {time.perf_counter() - started:.1f} s")


if __name__ == "__main__":
    main()
