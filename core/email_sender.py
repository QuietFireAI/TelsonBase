# TelsonBase/core/email_sender.py
# REM: =======================================================================================
# REM: SMTP EMAIL SENDER MODULE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 24, 2026
#
# REM: v8.1.0CC: Outbound email delivery for verification links and security alerts.
#
# REM: Mission Statement: Send transactional emails (email verification, security alerts)
# REM: via configurable SMTP. Falls back to console logging when SMTP is not configured,
# REM: so the system degrades gracefully in dev environments.
#
# REM: Configuration (env vars):
# REM:   SMTP_HOST     — SMTP server hostname (e.g. mailhog for dev, smtp.gmail.com for prod)
# REM:   SMTP_PORT     — SMTP port (1025 for MailHog, 587 for TLS, 465 for SSL)
# REM:   SMTP_USER     — SMTP username (empty for MailHog)
# REM:   SMTP_PASSWORD — SMTP password (empty for MailHog)
# REM:   SMTP_FROM     — From address shown to recipients
# REM:   APP_BASE_URL  — Base URL for link generation (e.g. http://localhost:8000)
#
# REM: Dev setup: MailHog catches all mail at http://localhost:8025
# REM:   SMTP_HOST=mailhog, SMTP_PORT=1025 (no credentials needed)
# REM: =======================================================================================

import asyncio
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# REM: Read SMTP configuration from environment
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@telsonbase.local")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")


def _send_sync(to_email: str, subject: str, html_body: str) -> bool:
    """
    REM: Blocking SMTP send — called via asyncio.to_thread to avoid blocking the event loop.
    REM: Returns True on success, False on failure or when SMTP is not configured.
    """
    if not SMTP_HOST:
        logger.warning(
            f"REM: SMTP not configured — email NOT sent to {to_email}. "
            f"Set SMTP_HOST in .env (or use MailHog for dev)_Thank_You_But_No"
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        if SMTP_PORT == 465:
            # REM: SSL (port 465)
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM, to_email, msg.as_string())
        else:
            # REM: Plain or STARTTLS (port 587 / 1025)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                try:
                    server.starttls()
                    server.ehlo()
                except smtplib.SMTPException:
                    # REM: MailHog and some local servers don't support STARTTLS — continue plain
                    pass
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM, to_email, msg.as_string())

        logger.info(f"REM: Email sent to ::{to_email}:: subject ::{subject}::_Thank_You")
        return True

    except Exception as e:
        logger.error(
            f"REM: SMTP send failed to ::{to_email}::: {e}_Thank_You_But_No"
        )
        return False


async def send_verification_email(
    to_email: str,
    username: str,
    token: str,
    user_id: str,
) -> bool:
    """
    REM: Send an email verification link to a newly registered user.
    REM: Non-blocking — runs SMTP I/O in a thread pool.

    Args:
        to_email: Recipient email address
        username: Display name / username for the greeting
        token:    Raw verification token (included in the link URL)
        user_id:  User's unique ID (included in the link URL)

    Returns:
        True if the email was sent successfully, False otherwise
    """
    verify_url = (
        f"{APP_BASE_URL}/v1/auth/verify-email"
        f"?user_id={user_id}&token={token}"
    )

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:40px 20px;">
  <div style="max-width:480px;margin:0 auto;background:#1e293b;border:1px solid #334155;
              border-radius:12px;padding:32px;">
    <h2 style="color:#22d3ee;margin-top:0;">Verify your email</h2>
    <p>Hi <strong>{username}</strong>,</p>
    <p>You've been registered on <strong>TelsonBase</strong>.
       Please verify your email address to activate your account:</p>
    <p style="text-align:center;margin:32px 0;">
      <a href="{verify_url}"
         style="background:#0891b2;color:#fff;text-decoration:none;
                padding:12px 28px;border-radius:8px;font-weight:600;
                display:inline-block;">
        Verify Email Address
      </a>
    </p>
    <p style="font-size:12px;color:#64748b;">
      This link expires in 24 hours. If you did not register for TelsonBase,
      you can safely ignore this email.
    </p>
    <hr style="border:none;border-top:1px solid #334155;margin:24px 0;"/>
    <p style="font-size:11px;color:#475569;margin:0;">
      TelsonBase by Quietfire AI &mdash; Sovereign AI Management Platform
    </p>
  </div>
</body>
</html>
"""

    return await asyncio.to_thread(
        _send_sync, to_email, "Verify your TelsonBase email address", html_body
    )
