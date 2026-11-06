"""The mails an account receives: address confirmation, address change and password reset."""

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.parse import urlencode

from app.api.core.domain.language import Language
from app.api.core.services.translations import translate
from app.api.features.auth.domain.user import User
from app.api.features.auth.services import mail_layout
from app.infrastructure import mailer
from app.infrastructure.config import get_settings


@dataclass(frozen=True)
class _Text:
    title: str
    intro: str
    action: str
    outro: str


def _text(mail: str, language: Language) -> _Text:
    """The four texts of `mail` (`verification`, `change` or `reset`) in `language`."""
    parts = ("title", "intro", "action", "outro")
    return _Text(*(translate(f"mail.{mail}.{part}", language) for part in parts))


def _link(path: str, token: str) -> str:
    return f"{get_settings().app_url.rstrip('/')}/{path}?{urlencode({'token': token})}"


def _compose(
    user: User, language: Language, text: _Text, link: str, to: str | None = None
) -> EmailMessage:
    brand = parseaddr(get_settings().mail_from)[0] or "Dart-Tracking"
    greeting = translate("mail.greeting", language, name=user.display_name)
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
    return _compose(user, language, _text("verification", language), _link("verify-email", token))


def email_change(user: User, new_email: str, token: str, language: Language) -> EmailMessage:
    return _compose(
        user, language, _text("change", language), _link("confirm-email", token), to=new_email
    )


def password_reset(user: User, token: str, language: Language) -> EmailMessage:
    return _compose(user, language, _text("reset", language), _link("reset-password", token))
