import string

import pytest

from app.api.core.domain.language import Language
from app.api.core.services.translations import texts, translate


def placeholders(text: str) -> set[str]:
    return {field for _, field, _, _ in string.Formatter().parse(text) if field}


def test_every_language_has_the_same_texts():
    source = texts(Language.DE)
    for language in Language:
        translated = texts(language)
        assert translated.keys() == source.keys(), language
        for key, text in source.items():
            assert placeholders(translated[key]) == placeholders(text), (language, key)


def test_a_text_is_filled_in_the_given_language():
    assert translate("mail.greeting", Language.EN, name="Anna") == "Hi Anna,"
    assert translate("mail.greeting", Language.DE, name="Anna") == "Hallo Anna,"


def test_an_unknown_key_is_an_error():
    with pytest.raises(KeyError):
        translate("no.such.text", Language.EN)
