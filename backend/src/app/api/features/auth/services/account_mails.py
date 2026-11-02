"""The mails an account receives: address confirmation, address change and password reset."""

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.parse import urlencode

from app.api.features.auth.domain.user import User
from app.api.features.auth.services import mail_layout
from app.api.features.settings.domain.language import Language
from app.infrastructure import mailer
from app.infrastructure.config import get_settings


@dataclass(frozen=True)
class _Text:
    title: str
    intro: str
    action: str
    outro: str


_GREETING = {Language.DE: "Hallo {name},", Language.EN: "Hi {name},"}

_VERIFICATION = {
    Language.DE: _Text(
        "E-Mail-Adresse bestätigen",
        "bitte bestätige noch kurz deine E-Mail-Adresse. So kommt ein Link zum "
        "Zurücksetzen auch an, falls du einmal dein Passwort vergisst.",
        "E-Mail-Adresse bestätigen",
        "Der Link ist 24 Stunden gültig. Falls du kein Konto erstellt hast, "
        "kannst du diese Mail ignorieren.",
    ),
    Language.EN: _Text(
        "Confirm your email address",
        "please take a moment to confirm your email address. That way a reset link "
        "reaches you too, should you ever forget your password.",
        "Confirm email address",
        "The link is valid for 24 hours. If you did not create an account, "
        "you can ignore this email.",
    ),
}

_CHANGE = {
    Language.DE: _Text(
        "Neue E-Mail-Adresse bestätigen",
        "dein Konto soll künftig diese E-Mail-Adresse verwenden. Bitte bestätige das, "
        "erst dann wird die Änderung wirksam.",
        "Neue Adresse bestätigen",
        "Der Link ist 24 Stunden gültig. Bis dahin bleibt deine bisherige Adresse aktiv. "
        "Falls du das nicht angefordert hast, kannst du diese Mail ignorieren.",
    ),
    Language.EN: _Text(
        "Confirm your new email address",
        "your account is to use this email address from now on. Please confirm it; "
        "only then does the change take effect.",
        "Confirm new address",
        "The link is valid for 24 hours. Until then your current address stays active. "
        "If you did not request this, you can ignore this email.",
    ),
}

_RESET = {
    Language.DE: _Text(
        "Passwort zurücksetzen",
        "für dein Konto wurde ein neues Passwort angefordert. Über den folgenden Link "
        "kannst du es festlegen.",
        "Neues Passwort festlegen",
        "Der Link ist eine Stunde gültig. Falls du das nicht angefordert hast, "
        "kannst du diese Mail ignorieren; dein Passwort bleibt unverändert.",
    ),
    Language.EN: _Text(
        "Reset your password",
        "a new password was requested for your account. You can set it with the "
        "following link.",
        "Set new password",
        "The link is valid for one hour. If you did not request this, you can ignore "
        "this email; your password stays unchanged.",
    ),
}


def _link(path: str, token: str) -> str:
    return f"{get_settings().app_url.rstrip('/')}/{path}?{urlencode({'token': token})}"


def _compose(
    user: User, language: Language, text: _Text, link: str, to: str | None = None
) -> EmailMessage:
    brand = parseaddr(get_settings().mail_from)[0] or "Dart-Tracking"
    greeting = _GREETING[language].format(name=user.display_name)
    plain = f"{greeting}\n\n{text.intro}\n\n{text.action}:\n{link}\n\n{text.outro}\n"
    html = mail_layout.render(
        language=language,
        brand=brand,
        title=text.title,
        greeting=greeting,
        intro=text.intro,
        action=text.action,
        link=link,
        outro=text.outro,
    )
    return mailer.compose(to or user.email, f"{brand}: {text.title}", plain, html)


def email_verification(user: User, token: str, language: Language) -> EmailMessage:
    return _compose(user, language, _VERIFICATION[language], _link("verify-email", token))


def email_change(user: User, new_email: str, token: str, language: Language) -> EmailMessage:
    return _compose(
        user, language, _CHANGE[language], _link("confirm-email", token), to=new_email
    )


def password_reset(user: User, token: str, language: Language) -> EmailMessage:
    return _compose(user, language, _RESET[language], _link("reset-password", token))
