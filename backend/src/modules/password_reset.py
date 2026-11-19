"""Passenger password reset: signed single-use links sent by email.

The reset token is a short-lived signed JWT. It carries a fingerprint of the
current password hash, so it stops working as soon as the password changes
(single use) and no extra database table is needed.
"""

import hashlib
import os
import smtplib
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.core.security import create_access_token, decode_access_token

from ..logger import logger
from .notifications import send_email_via_resend

RESET_PURPOSE = "password_reset"
RESET_LIFETIME = timedelta(minutes=30)


def _fingerprint(password_hash: Optional[str]) -> str:
    return hashlib.sha256((password_hash or "").encode("utf-8")).hexdigest()[:24]


def create_reset_token(passenger_id: str, password_hash: Optional[str]) -> str:
    return create_access_token(
        data={
            "sub": passenger_id,
            "purpose": RESET_PURPOSE,
            "pv": _fingerprint(password_hash),
        },
        expires_delta=RESET_LIFETIME,
    )


def read_reset_token(token: str) -> Optional[dict]:
    """Return the token claims when it is a valid reset token, else None."""
    claims = decode_access_token(token)
    if not claims or claims.get("purpose") != RESET_PURPOSE:
        return None
    if not isinstance(claims.get("sub"), str) or not isinstance(claims.get("pv"), str):
        return None
    return claims


def token_matches_password(claims: dict, password_hash: Optional[str]) -> bool:
    return claims.get("pv") == _fingerprint(password_hash)


def frontend_base_url() -> str:
    explicit = os.getenv("FRONTEND_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    for origin in origins:
        if origin.startswith("https://"):
            return origin.rstrip("/")
    return (origins[0] if origins else "http://localhost:3000").rstrip("/")


def _send_via_smtp(to_email: str, subject: str, text: str, html: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        raise ValueError("SMTP_HOST is not configured.")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("EMAIL_FROM", user or "no-reply@kenya-airways-rag.local")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=10) as server:
            if user and password:
                server.login(user, password)
            server.sendmail(sender, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if user and password:
                server.login(user, password)
            server.sendmail(sender, [to_email], msg.as_string())


def send_reset_email(to_email: str, full_name: Optional[str], token: str) -> bool:
    """Send the reset link. Returns False when no email provider is configured."""
    link = f"{frontend_base_url()}/reset-password?token={token}"
    greeting = f"Hello {full_name}," if full_name else "Hello,"
    subject = "Reset your Pippit password"
    text = (
        f"{greeting}\n\nUse this link to choose a new password. It works for 30 minutes "
        f"and only once:\n{link}\n\nIf you did not ask for this, you can ignore this email."
    )
    html = (
        f"<p>{greeting}</p><p>Use the button below to choose a new password. "
        f"The link works for 30 minutes and only once.</p>"
        f'<p><a href="{link}" style="background:#c8102e;color:#fff;padding:10px 18px;'
        f'border-radius:8px;text-decoration:none">Reset password</a></p>'
        f"<p>If you did not ask for this, you can ignore this email.</p>"
    )
    try:
        if os.getenv("RESEND_API_KEY", "").strip():
            send_email_via_resend(to_email, subject, html)
            return True
        if os.getenv("SMTP_HOST", "").strip():
            _send_via_smtp(to_email, subject, text, html)
            return True
    except Exception:  # noqa: BLE001 - never reveal delivery details to the caller
        logger.exception("Password reset email could not be sent")
        return False
    logger.warning("Password reset requested but no email provider is configured.")
    return False
