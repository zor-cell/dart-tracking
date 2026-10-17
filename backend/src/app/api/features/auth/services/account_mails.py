"""The mails an account receives: address confirmation, address change and password reset."""

from email.message import EmailMessage
from email.utils import parseaddr
from urllib.parse import urlencode

from app.api.features.auth.domain.user import User
from app.api.features.auth.services import mail_layout
from app.infrastructure import mailer
from app.infrastructure.config import get_settings


def _link(path: str, token: str) -> str:
    return f"{get_settings().app_url.rstrip('/')}/{path}?{urlencode({'token': token})}"


def _compose(
    user: User,
    title: str,
    intro: str,
    action: str,
    link: str,
    outro: str,
    to: str | None = None,
) -> EmailMessage:
    brand = parseaddr(get_settings().mail_from)[0] or "Dart-Tracking"
    greeting = f"Hallo {user.display_name},"
    text = f"{greeting}\n\n{intro}\n\n{action}:\n{link}\n\n{outro}\n"
    html = mail_layout.render(
        brand=brand,
        title=title,
        greeting=greeting,
        intro=intro,
        action=action,
        link=link,
        outro=outro,
    )
    return mailer.compose(to or user.email, f"{brand}: {title}", text, html)


def email_verification(user: User, token: str) -> EmailMessage:
    return _compose(
        user,
        "E-Mail-Adresse bestätigen",
        "bitte bestätige noch kurz deine E-Mail-Adresse. So kommt ein Link zum "
        "Zurücksetzen auch an, falls du einmal dein Passwort vergisst.",
        "E-Mail-Adresse bestätigen",
        _link("verify-email", token),
        "Der Link ist 24 Stunden gültig. Falls du kein Konto erstellt hast, "
        "kannst du diese Mail ignorieren.",
    )


def email_change(user: User, new_email: str, token: str) -> EmailMessage:
    return _compose(
        user,
        "Neue E-Mail-Adresse bestätigen",
        "dein Konto soll künftig diese E-Mail-Adresse verwenden. Bitte bestätige das, "
        "erst dann wird die Änderung wirksam.",
        "Neue Adresse bestätigen",
        _link("confirm-email", token),
        "Der Link ist 24 Stunden gültig. Bis dahin bleibt deine bisherige Adresse aktiv. "
        "Falls du das nicht angefordert hast, kannst du diese Mail ignorieren.",
        to=new_email,
    )


def password_reset(user: User, token: str) -> EmailMessage:
    return _compose(
        user,
        "Passwort zurücksetzen",
        "für dein Konto wurde ein neues Passwort angefordert. Über den folgenden Link "
        "kannst du es festlegen.",
        "Neues Passwort festlegen",
        _link("reset-password", token),
        "Der Link ist eine Stunde gültig. Falls du das nicht angefordert hast, "
        "kannst du diese Mail ignorieren; dein Passwort bleibt unverändert.",
    )
