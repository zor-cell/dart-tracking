import asyncio

import aiosmtplib
import pytest

from app.infrastructure import mailer
from app.infrastructure.config import Settings, SmtpSecurity


@pytest.fixture
def smtp(monkeypatch):
    """Configure the mailer for `security` and record what it hands to SMTP."""
    sent = []

    def configure(security: SmtpSecurity, failure: Exception | None = None):
        settings = Settings.model_construct(
            smtp_host="mail.example.org",
            smtp_port=587,
            smtp_username="user",
            smtp_password="secret",
            smtp_security=security,
            mail_from="Darts <noreply@darts.example.org>",
        )
        monkeypatch.setattr(mailer, "get_settings", lambda: settings)

        async def send(message, **options):
            if failure is not None:
                raise failure
            sent.append((message, options))

        monkeypatch.setattr(aiosmtplib, "send", send)
        return sent

    return configure


@pytest.mark.parametrize(
    ("security", "use_tls", "start_tls"),
    [(SmtpSecurity.NONE, False, False), (SmtpSecurity.STARTTLS, False, True), (SmtpSecurity.TLS, True, False)],
)
def test_encryption_follows_the_setting(smtp, security, use_tls, start_tls):
    sent = smtp(security)

    asyncio.run(mailer.send(mailer.compose("to@example.org", "Subject", "text", "<p>html</p>")))

    message, options = sent[0]
    assert (options["use_tls"], options["start_tls"]) == (use_tls, start_tls)
    assert (options["hostname"], options["port"], options["username"]) == ("mail.example.org", 587, "user")
    assert message["From"] == "Darts <noreply@darts.example.org>"
    assert "@darts.example.org>" in message["Message-ID"]


@pytest.mark.parametrize("failure", [aiosmtplib.SMTPException("refused"), OSError("unreachable")])
def test_a_failed_delivery_is_logged_not_raised(smtp, failure, monkeypatch):
    smtp(SmtpSecurity.NONE, failure)
    logged = []
    monkeypatch.setattr(mailer.logger, "exception", lambda *args: logged.append(args))

    asyncio.run(mailer.send(mailer.compose("to@example.org", "Subject", "text", "<p>html</p>")))

    assert logged and "could not send mail" in logged[0][0]
