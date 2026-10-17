"""Outgoing mail over SMTP, to whatever server the settings name."""

import logging
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

import aiosmtplib

from app.infrastructure.config import SmtpSecurity, get_settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15


def compose(to: str, subject: str, text: str, html: str) -> EmailMessage:
    """A message with a plain-text body and an HTML alternative."""
    sender = get_settings().mail_from
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate()
    message["Message-ID"] = make_msgid(domain=parseaddr(sender)[1].partition("@")[2] or None)
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    return message


async def send(message: EmailMessage) -> None:
    """Deliver the message. Failures are logged, not raised: callers run this as a background task."""
    settings = get_settings()
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_security is SmtpSecurity.TLS,
            start_tls=settings.smtp_security is SmtpSecurity.STARTTLS,
            timeout=_TIMEOUT_SECONDS,
        )
    except (aiosmtplib.SMTPException, OSError):
        logger.exception("could not send mail %r", message["Subject"])
