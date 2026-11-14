import asyncio

from app.api.core.domain.language import Language
from app.api.features.announcement.domain.speaker import Speaker, Voice
from app.api.features.announcement.services import speech
from app.api.features.announcement.services.speech import (
    VOICES,
    PiperSynthesizer,
    SpeechStore,
    clip_id,
    clip_url,
    respelled,
)
from tests.audio import silent_wav


EN, DE = Speaker(Language.EN), Speaker(Language.DE)


def recording_store(tmp_path, prebuilt=None):
    voiced: list[str] = []

    def synthesize(text: str, speaker: Speaker) -> bytes:
        voiced.append(text)
        return silent_wav(text, speaker)

    return SpeechStore(synthesize, tmp_path / "cache", prebuilt), voiced


def test_a_phrase_is_voiced_once_and_then_read_from_disk(tmp_path):
    store, voiced = recording_store(tmp_path)

    first = store.make("Double 20", EN)
    second = store.make("Double 20", EN)

    assert first == second
    assert voiced == ["Double 20"]
    assert store.path(first) == tmp_path / "cache" / f"{first}.wav"


def test_the_same_text_gets_a_clip_per_language_and_voice():
    assert clip_id("Bull", EN) != clip_id("Bull", DE)
    assert clip_id("Bull", EN) != clip_id("Bull", Speaker(Language.EN, Voice.SECOND))


def test_a_prebuilt_clip_is_not_voiced_again(tmp_path):
    prebuilt = tmp_path / "prebuilt"
    prebuilt.mkdir()
    clip = clip_id("Bull", EN)
    (prebuilt / f"{clip}.wav").write_bytes(b"RIFF")
    store, voiced = recording_store(tmp_path, prebuilt)

    assert store.make("Bull", EN) == clip
    assert voiced == []
    assert store.path(clip) == prebuilt / f"{clip}.wav"


def test_only_clip_ids_are_looked_up(tmp_path):
    store, _ = recording_store(tmp_path)
    (tmp_path / "cache").mkdir()
    (tmp_path / "secret.wav").write_bytes(b"RIFF")

    assert store.path("../secret") is None
    assert store.path("0" * 32) is None


def test_urls_name_each_clip_in_order(tmp_path):
    store, _ = recording_store(tmp_path)

    urls = asyncio.run(store.urls(["Single 20", "60"], DE))

    assert urls == [clip_url(clip_id(text, DE)) for text in ("Single 20", "60")]


def test_a_voice_that_fails_leaves_the_announcement_silent(tmp_path):
    def broken(text: str, speaker: Speaker) -> bytes:
        raise FileNotFoundError("no voice model")

    store = SpeechStore(broken, tmp_path / "cache", None)

    assert asyncio.run(store.urls(["Bull"], EN)) == []


def test_every_voice_is_loaded_at_startup(tmp_path, monkeypatch):
    loaded: list[Speaker] = []

    class Recording(PiperSynthesizer):
        def load(self, speakers: list[Speaker]) -> None:
            loaded.extend(speakers)

    store = SpeechStore(Recording(tmp_path), tmp_path / "cache", None)
    monkeypatch.setattr(speech, "speech_store", lambda: store)

    asyncio.run(speech.warm_up())

    assert loaded == list(VOICES)


def test_a_dropped_final_sound_is_respelled_in_phonemes():
    finals = {"f": "fff"}

    assert respelled("5", [["f", "ˈ", "ʏ", "n", "f"]], finals) == "[[ fˈʏnfff ]]"
    assert respelled("Anna, 5.", [["ˈ", "a", "n", "a", ",", " ", "f", "ʏ", "n", "f", "."]], finals) == "[[ ˈana, fʏnfff ]]"


def test_the_german_bull_is_respelled():
    finals = speech.FINALS[VOICES[DE]]

    assert respelled("Bull", [["b", "ˈ", "ʊ", "l"]], finals) == "[[ bˈʊll ]]"
    assert respelled("Null", [["n", "ˈ", "ʊ", "l"]], finals) == "Null"


def test_other_endings_and_several_sentences_stay_as_written():
    finals = {"f": "fff"}

    assert respelled("40", [["f", "ɪ", "ɾ", "t", "s", "ɪ", "ç"]], finals) == "40"
    assert respelled("Elf. Fünf", [["ɛ", "l", "f"], ["f", "ʏ", "n", "f"]], finals) == "Elf. Fünf"


def test_a_tuned_voice_names_its_clips_apart(monkeypatch):
    before = clip_id("5", DE)
    monkeypatch.setitem(speech.PACES, VOICES[DE], 1.3)

    assert clip_id("5", DE) != before
