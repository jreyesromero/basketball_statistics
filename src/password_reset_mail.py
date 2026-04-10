"""Deliver password reset links (SMTP if configured, else stderr for local dev)."""

from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    """
    If BASKET_SMTP_HOST is set, send mail via STARTTLS (port 587 by default).
    Otherwise print the link to stderr (local development; configure SMTP for production).
    """
    host = os.environ.get("BASKET_SMTP_HOST", "").strip()
    if not host:
        print(
            f"\n[BASKET] Password reset (SMTP not configured). Link for {to_email}:\n"
            f"{reset_url}\n",
            file=sys.stderr,
        )
        return

    port = int(os.environ.get("BASKET_SMTP_PORT", "587"))
    user = os.environ.get("BASKET_SMTP_USER", "").strip()
    password = os.environ.get("BASKET_SMTP_PASSWORD", "")
    from_addr = os.environ.get("BASKET_SMTP_FROM", "").strip() or user
    if not from_addr:
        print(
            "[BASKET] BASKET_SMTP_FROM (or BASKET_SMTP_USER) must be set when using SMTP.",
            file=sys.stderr,
        )
        print(
            f"\n[BASKET] Password reset fallback for {to_email}:\n{reset_url}\n",
            file=sys.stderr,
        )
        return

    msg = EmailMessage()
    msg["Subject"] = "Reset your basketball statistics password"
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(
        f"You requested a password reset.\n\n"
        f"Open this link (valid for one hour):\n{reset_url}\n\n"
        f"If you did not request this, you can ignore this message.\n"
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls(context=context)
        if user:
            server.login(user, password)
        server.send_message(msg)
