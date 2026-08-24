"""SMTP email sender. Honors SMTP_DRY_RUN to log instead of send in dev/test."""
import asyncio
import smtplib
import socket
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


def _create_ipv4_connection(address, timeout=15, source_address=None):
    """Force IPv4 address resolution to prevent [Errno 101] Network is unreachable on containers without IPv6 routes."""
    host, port = address
    err = None
    for res in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = socket.socket(af, socktype, proto)
            if timeout is not None:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sa)
            return sock
        except socket.error as exc:
            err = exc
            if sock is not None:
                sock.close()
    if err is not None:
        raise err
    raise socket.error(f"getaddrinfo failed for {host}:{port}")


def _send_smtp_sync(msg: EmailMessage) -> None:
    """Send a single message via SMTP. Called inside asyncio.to_thread."""
    smtp_cls = smtplib.SMTP_SSL if SMTP_PORT == 465 else smtplib.SMTP
    s = smtp_cls(timeout=15)
    s._get_socket = lambda host, port, timeout: _create_ipv4_connection((host, port), timeout, s.source_address)
    with s:
        s.connect(SMTP_HOST, SMTP_PORT)
        if SMTP_PORT != 465:
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
