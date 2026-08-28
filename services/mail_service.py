"""Email dispatch service built on Flask-Mail."""

from flask import current_app
from flask_mail import Message

from extensions import mail


def send_email(
    subject: str,
    recipients: str | list[str],
    text_body: str | None = None,
    html_body: str | None = None,
) -> bool:
    """Send an email. Returns True when dispatched, False on failure."""
    if isinstance(recipients, str):
        recipients = [recipients]

    try:
        message = Message(
            subject=subject,
            recipients=recipients,
            sender=current_app.config["MAIL_DEFAULT_SENDER"],
            body=text_body or "",
            html=html_body,
        )
        mail.send(message)
        return True
    except Exception as exc:  # noqa: BLE001 - never leak SMTP errors to users
        current_app.logger.error("Email dispatch failed: %s", exc)
        return False
