"""The single-use tokens behind the links sent by account mails, one live token
per account and purpose."""

from datetime import timedelta

from app.api.core.services.one_time_tokens import OneTimeTokens

email_verification = OneTimeTokens("auth:verify-email", timedelta(hours=24))
password_reset = OneTimeTokens("auth:password-reset", timedelta(hours=1))
email_change = OneTimeTokens("auth:email-change", timedelta(hours=24))
