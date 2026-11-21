"""Spoken clips of the announcer's phrases: voiced once by Piper, then served as files."""

import asyncio
import hashlib
import io
import logging
import re
import threading
import uuid
import wave
from collections.abc import Callable
from functools import cache
from pathlib import Path

from piper import PiperVoice, SynthesisConfig

from app.api.core.domain.language import Language
from app.api.features.announcement.domain.speaker import Speaker, Voice
from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)

# The Piper model behind each speaker.
VOICES = {
    Speaker(Language.DE, Voice.FIRST): "de_DE-thorsten-medium",
    Speaker(Language.DE, Voice.SECOND): "de_DE-pavoque-low",
    Speaker(Language.EN, Voice.FIRST): "en_GB-alan-medium",
    Speaker(Language.EN, Voice.SECOND): "en_GB-jenny_dioco-medium",
}

# How much slower than its own pace a model speaks, as a factor.
PACES = {"de_DE-thorsten-medium": 1.1}

# Endings a model drops or blurs before a pause, with the phonemes that say them clearly.
FINALS = {"de_DE-thorsten-medium": {"f": "fff", "bˈʊl": "bˈʊll"}}

# Words a model stresses oddly, as their phonemes and the ones that say them right.
SOUNDS = {"en_GB-alan-medium": {"sˈɛvəntˌiːn": "sˈɛvəntiːn"}}

# What sets a clause apart from the next, in Piper's phonemes.
_PAUSE = re.compile(r"([,.!?]+ *)")

# Voices a phrase as one speaker, as WAV bytes.
Synthesizer = Callable[[str, Speaker], bytes]

CLIP_ID = re.compile(r"[0-9a-f]{32}")


def clip_id(text: str, speaker: Speaker) -> str:
    """Named by voice, its tuning and text, so a change to any gets a clip of its own."""
    model = VOICES[speaker]
    tuning = [table.get(model) for table in (PACES, FINALS, SOUNDS) if model in table] or ""
    return hashlib.sha256(f"{model}{tuning}\n{text}".encode()).hexdigest()[:32]


def respelled(
    text: str, phonemes: list[list[str]], finals: dict[str, str], sounds: dict[str, str]
) -> str:
    """`text` as Piper's raw phonemes when it holds a sound of `sounds` or a clause
    ends in one of `finals`, else as it is."""
    if len(phonemes) != 1:
        return text
    spoken = "".join(phonemes[0]).rstrip(" .!?,")
    tuned = spoken
    for sound, kept in sounds.items():
        tuned = tuned.replace(sound, kept)
    parts = _PAUSE.split(tuned)
    for index in range(0, len(parts), 2):
        ending = next((e for e in finals if parts[index].endswith(e)), None)
        if ending is not None:
            parts[index] = parts[index].removesuffix(ending) + finals[ending]
    tuned = "".join(parts)
    return text if tuned == spoken else f"[[ {tuned} ]]"


def clip_url(clip: str) -> str:
    return f"/api/announcer/clips/{clip}.wav"


class PiperSynthesizer:
    """Loads each speaker's voice from `voices_dir` on first use."""

    def __init__(self, voices_dir: Path) -> None:
        self.voices_dir = voices_dir
        self._voices: dict[Speaker, PiperVoice] = {}
        self._lock = threading.Lock()

    def __call__(self, text: str, speaker: Speaker) -> bytes:
        buffer = io.BytesIO()
        model = VOICES[speaker]
        with self._lock:
            voice = self._voice(speaker)
            if model in FINALS or model in SOUNDS:
                phonemes = voice.phonemize(text)
                text = respelled(text, phonemes, FINALS.get(model, {}), SOUNDS.get(model, {}))
            with wave.open(buffer, "wb") as wav:
                config = SynthesisConfig(length_scale=PACES.get(model))
                voice.synthesize_wav(text, wav, syn_config=config)
        return buffer.getvalue()

    def load(self, speakers: list[Speaker]) -> None:
        with self._lock:
            for speaker in speakers:
                self._voice(speaker)

    def _voice(self, speaker: Speaker) -> PiperVoice:
        voice = self._voices.get(speaker)
        if voice is None:
            voice = PiperVoice.load(self.voices_dir / f"{VOICES[speaker]}.onnx")
            self._voices[speaker] = voice
        return voice


class SpeechStore:
    """Clips by id: looked up in the prebuilt directory, else voiced into `cache_dir`."""

    def __init__(self, synthesize: Synthesizer, cache_dir: Path, prebuilt_dir: Path | None) -> None:
        self.synthesize = synthesize
        self.cache_dir = cache_dir
        self.prebuilt_dir = prebuilt_dir

    def path(self, clip: str) -> Path | None:
        if not CLIP_ID.fullmatch(clip):
            return None
        for directory in (self.prebuilt_dir, self.cache_dir):
            if directory is not None and (candidate := directory / f"{clip}.wav").is_file():
                return candidate
        return None

    def make(self, text: str, speaker: Speaker) -> str:
        """The clip of `text`, voiced now unless it already exists."""
        clip = clip_id(text, speaker)
        if self.path(clip) is None:
            audio = self.synthesize(text, speaker)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            partial = self.cache_dir / f"{clip}.{uuid.uuid4().hex}.part"
            partial.write_bytes(audio)
            partial.replace(self.cache_dir / f"{clip}.wav")
        return clip

    async def urls(self, texts: list[str], speaker: Speaker) -> list[str]:
        """Where to fetch each phrase's clip; none when they cannot be voiced."""
        try:
            clips = await asyncio.to_thread(lambda: [self.make(t, speaker) for t in texts])
        except Exception:
            logger.exception("[speech] could not voice %r as %s", texts, speaker)
            return []
        return [clip_url(clip) for clip in clips]


async def warm_up() -> None:
    """Load every voice ahead of the first call that names a player."""
    synthesize = speech_store().synthesize
    if isinstance(synthesize, PiperSynthesizer):
        try:
            await asyncio.to_thread(synthesize.load, list(VOICES))
        except Exception:
            logger.warning("[speech] no voices in %s, the announcer stays silent", synthesize.voices_dir)


@cache
def speech_store() -> SpeechStore:
    """The app's store, built on first use so the build-time script needs no settings."""
    settings = get_settings()
    return SpeechStore(
        PiperSynthesizer(settings.voices_dir), settings.speech_dir, settings.speech_prebuilt_dir
    )
