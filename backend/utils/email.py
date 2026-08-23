"""SMTP email sender. Honors SMTP_DRY_RUN to log instead of send in dev/test."""
import asyncio
import smtplib
from email.message import EmailMessage

from config.settings import (
    SMTP_DRY_RUN,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
    logger,
)


def _send_smtp_sync(msg: EmailMessage) -> None:
    """Send a single message via SMTP. Called inside asyncio.to_thread."""
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
        s.starttls()
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)


async def send_email(to: str, subject: str, html: str, text: str) -> bool:
    """Send an email with both plain-text and HTML parts.

    Returns True if the message was dispatched (or logged in dry-run mode).
    Failures are logged and return False; callers should not let send failures
    break user-facing flows (the user can resend).
    """
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    if SMTP_DRY_RUN:
        logger.info(f"[EMAIL DRY-RUN] to={to} subject={subject}\n{text}\n--- HTML ---\n{html}")
        return True

    try:
        await asyncio.to_thread(_send_smtp_sync, msg)
        return True
    except Exception:
        logger.exception(f"SMTP send failed to={to} subject={subject}")
        return False
