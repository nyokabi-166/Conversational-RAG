"""Notification dispatch service supporting Resend HTTP API and standard SMTP."""

import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..logger import logger

KQ_RED = "#BD0026"
KQ_DARK = "#1A1A1A"
KQ_GRAY = "#F4F5F7"
KQ_STATUS_URL = "https://www.kenya-airways.com/en/book-manage/flight-status/"
KQ_CHECKIN_URL = "https://www.kenya-airways.com/en/book-manage/web-check-in/"


def render_flight_email_html(
    passenger_name: str,
    flight_number: str,
    origin: str,
    destination: str,
    departure_date: str,
    reminder_title: str = "",
    flight_status: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a responsive HTML email branded for Kenya Airways."""
    status_label = "Scheduled"
    terminal_info = "Terminal 1A (JKIA)" if origin.upper() == "NBO" else "Check flight status"
    departure_time_str = departure_date

    if flight_status and flight_status.get("flight"):
        flight_info = flight_status["flight"]
        status_label = (flight_info.get("status") or "Scheduled").capitalize()
        if flight_info.get("terminal"):
            terminal_info = f"Terminal {flight_info.get('terminal')}"
        if flight_info.get("departure_at"):
            try:
                departure_time_str = str(flight_info.get("departure_at"))
            except Exception:
                pass

    custom_reminder_block = ""
    if reminder_title:
        custom_reminder_block = f"""
        <div style="background-color: #FFF3CD; border-left: 4px solid #FFA000; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
            <strong style="color: #856404; font-size: 14px;">Trip Note / Reminder:</strong>
            <p style="margin: 4px 0 0 0; color: #856404; font-size: 14px;">{reminder_title}</p>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Kenya Airways Flight Alert</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: {KQ_GRAY}; color: {KQ_DARK};">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: {KQ_GRAY}; padding: 24px 0;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); max-width: 600px; width: 100%;">
                        <!-- Header Banner -->
                        <tr>
                            <td style="background-color: {KQ_RED}; padding: 24px 32px; text-align: left;">
                                <h1 style="color: #FFFFFF; margin: 0; font-size: 22px; font-weight: 700; letter-spacing: 0.5px;">Kenya Airways</h1>
                                <p style="color: rgba(255,255,255,0.85); margin: 4px 0 0 0; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;">Customer Support &amp; Flight Assistant</p>
                            </td>
                        </tr>

                        <!-- Body Content -->
                        <tr>
                            <td style="padding: 32px;">
                                <h2 style="margin: 0 0 12px 0; font-size: 18px; color: {KQ_DARK};">
                                    Flight Advisory: {flight_number.upper()} ({origin.upper()} &rarr; {destination.upper()})
                                </h2>
                                <p style="margin: 0 0 20px 0; font-size: 14px; line-height: 1.5; color: #555555;">
                                    Hello {passenger_name or 'Valued Passenger'},<br>
                                    Here is the latest advisory for your upcoming Kenya Airways trip.
                                </p>

                                {custom_reminder_block}

                                <!-- Flight Card -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #F8F9FA; border: 1px solid #E9ECEF; border-radius: 6px; margin: 16px 0 24px 0;">
                                    <tr>
                                        <td style="padding: 16px;">
                                            <table width="100%" cellpadding="4" cellspacing="0" style="font-size: 14px;">
                                                <tr>
                                                    <td width="35%" style="color: #777777;">Flight:</td>
                                                    <td style="font-weight: 600; color: {KQ_DARK};">{flight_number.upper()}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color: #777777;">Route:</td>
                                                    <td style="font-weight: 600; color: {KQ_DARK};">{origin.upper()} to {destination.upper()}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color: #777777;">Departure Date:</td>
                                                    <td style="font-weight: 600; color: {KQ_DARK};">{departure_time_str}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color: #777777;">Live Status:</td>
                                                    <td style="font-weight: 600; color: {KQ_RED};">{status_label}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color: #777777;">Terminal:</td>
                                                    <td style="font-weight: 600; color: {KQ_DARK};">{terminal_info}</td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>

                                <!-- Policy Advisory Box -->
                                <h3 style="margin: 20px 0 8px 0; font-size: 15px; color: {KQ_DARK};">Travel Preparation Checklist</h3>
                                <ul style="margin: 0 0 24px 0; padding-left: 20px; font-size: 13px; line-height: 1.6; color: #444444;">
                                    <li><strong>Web Check-In:</strong> Online check-in opens 24 hours before scheduled departure.</li>
                                    <li><strong>Baggage Allowance:</strong> Standard international economy permits 2 x 23 kg checked bags plus 1 carry-on bag (up to 12 kg).</li>
                                    <li><strong>Passport &amp; Visas:</strong> Ensure your passport is valid for at least 6 months beyond travel dates, and confirm transit/destination visa requirements.</li>
                                    <li><strong>Airport Arrival:</strong> Arrive at the airport at least 3 hours before international flights and 2 hours for domestic services.</li>
                                </ul>

                                <!-- Call to Action Buttons -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 16px;">
                                    <tr>
                                        <td align="center">
                                            <a href="{KQ_CHECKIN_URL}" target="_blank" style="display: inline-block; background-color: {KQ_RED}; color: #FFFFFF; text-decoration: none; font-size: 14px; font-weight: 600; padding: 12px 24px; border-radius: 4px; margin-right: 8px;">
                                                Web Check-In &rarr;
                                            </a>
                                            <a href="{KQ_STATUS_URL}" target="_blank" style="display: inline-block; background-color: #FFFFFF; color: {KQ_DARK}; border: 1px solid #CCCCCC; text-decoration: none; font-size: 14px; font-weight: 600; padding: 12px 20px; border-radius: 4px;">
                                                Check Live Status
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #F1F3F5; padding: 20px 32px; font-size: 12px; color: #777777; border-top: 1px solid #E9ECEF; text-align: center;">
                                <p style="margin: 0 0 4px 0;">This automated reminder was sent by the Strathmore University Capstone Conversational AI Platform.</p>
                                <p style="margin: 0;">Optimizing Customer Support Operations through a Retrieval-Augmented Generation (RAG) Framework.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


def send_email_via_resend(to_email: str, subject: str, html_content: str) -> dict:
    """Send an email using Resend REST API (https://resend.com)."""
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        raise ValueError("RESEND_API_KEY is not configured.")

    from_address = os.getenv("EMAIL_FROM", "Kenya Airways Assistant <onboarding@resend.dev>")
    payload = json.dumps(
        {
            "from": from_address,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
    ).encode("utf-8")

    req = Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(req, timeout=12) as response:
        data = json.loads(response.read().decode("utf-8"))
        logger.info("Resend email dispatched successfully: %s", data.get("id"))
        return {"sent": True, "provider": "resend", "id": data.get("id")}


def send_email_via_smtp(to_email: str, subject: str, html_content: str) -> dict:
    """Send an email using standard SMTP server configuration."""
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_address = os.getenv("EMAIL_FROM", user or "no-reply@kenya-airways-rag.local")

    if not host:
        raise ValueError("SMTP_HOST is not configured.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = to_email

    # Plain text fallback
    plain_text = f"{subject}\n\nCheck official flight status on Kenya Airways: {KQ_STATUS_URL}"
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=10) as server:
            if user and password:
                server.login(user, password)
            server.sendmail(from_address, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if user and password:
                server.login(user, password)
            server.sendmail(from_address, [to_email], msg.as_string())

    logger.info("SMTP email dispatched successfully to %s", to_email)
    return {"sent": True, "provider": "smtp"}


def send_flight_alert(
    to_email: str,
    passenger_name: str,
    flight_number: str,
    origin: str,
    destination: str,
    departure_date: str,
    reminder_title: str = "",
    flight_status: Optional[Dict[str, Any]] = None,
) -> dict:
    """Attempt dispatch via Resend or SMTP, with graceful fallback logging."""
    if not to_email:
        return {"sent": False, "reason": "No recipient email provided"}

    subject = f"✈️ Kenya Airways Flight Alert: {flight_number.upper()} ({origin.upper()} → {destination.upper()})"
    if reminder_title:
        subject = f"🔔 Reminder: {reminder_title} - {flight_number.upper()}"

    html_content = render_flight_email_html(
        passenger_name=passenger_name,
        flight_number=flight_number,
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        reminder_title=reminder_title,
        flight_status=flight_status,
    )

    # 1. Try Resend if configured
    if os.getenv("RESEND_API_KEY"):
        try:
            return send_email_via_resend(to_email, subject, html_content)
        except Exception as exc:
            logger.warning("Resend dispatch failed: %s; falling back to SMTP or logging", exc)

    # 2. Try SMTP if configured
    if os.getenv("SMTP_HOST"):
        try:
            return send_email_via_smtp(to_email, subject, html_content)
        except Exception as exc:
            logger.warning("SMTP dispatch failed: %s; falling back to logging", exc)

    # 3. Simulated delivery fallback
    logger.info(
        "SIMULATED EMAIL DISPATCH -> To: %s | Subject: %s | Flight: %s",
        to_email,
        subject,
        flight_number,
    )
    return {
        "sent": True,
        "provider": "simulated",
        "message": f"Flight alert successfully simulated for {to_email}. Set RESEND_API_KEY or SMTP credentials in .env for live inbox delivery.",
        "subject": subject,
        "recipient": to_email,
    }
