"""Provider-independent SMTP delivery and hashed, single-use email challenges."""

import os
import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import unquote

from fastapi import HTTPException, Request
from sqlmodel import Session, select

from app import auth
from app.models import EmailVerification, User, as_utc, utc_now
from app.telemetry import event


def return_path(value: str) -> str:
    decoded = unquote(value)
    if (len(value) > 500 or not decoded.startswith("/") or decoded.startswith("//")
            or "\\" in decoded or any(ord(c) < 32 for c in decoded)
            or decoded.startswith(("/login", "/verify-email"))):
        raise ValueError("Invalid return path")
    return value


def enabled() -> bool:
    return auth.env_bool("AUTH_REQUIRE_EMAIL_VERIFICATION", False)


def validate_configuration() -> None:
    if not enabled():
        return
    for name in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL"):
        if not os.getenv(name) or any(c in os.environ[name] for c in "\r\n"):
            raise auth.AuthConfigurationError(f"{name} is required for email verification")
    if int(os.getenv("SMTP_PORT", "587")) not in {465, 587}:
        raise auth.AuthConfigurationError("SMTP_PORT must be 587 (STARTTLS) or 465 (TLS)")
    if "@" not in os.environ["SMTP_FROM_EMAIL"] or any(c in os.getenv("SMTP_FROM_NAME", "PNBallie") for c in "\r\n"):
        raise auth.AuthConfigurationError("Invalid SMTP sender")


def send_verification(recipient: str, token: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Bevestig je e-mailadres voor PNBallie"
    message["From"] = formataddr((os.getenv("SMTP_FROM_NAME", "PNBallie"), os.environ["SMTP_FROM_EMAIL"]))
    message["To"] = recipient
    # A fragment never reaches HTTP access logs or Referer headers. The browser
    # clears it before displaying the explicit confirmation form.
    link = f"{auth.app_origin()}/verify-email#token={token}"
    message.set_content(
        "Bevestig je e-mailadres voor PNBallie:\n\n" + link
        + "\n\nLog in met je eigen account en kies ‘E-mailadres bevestigen’."
        " De link is 24 uur geldig en kan één keer worden gebruikt."
        "\n\nHeb je dit niet aangevraagd? Dan hoef je niets te doen.\n"
    )
    host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
    context = ssl.create_default_context()
    connection = smtplib.SMTP_SSL(host, port, timeout=15, context=context) if port == 465 else smtplib.SMTP(host, port, timeout=15)
    with connection as smtp:
        smtp.ehlo()
        if port != 465:
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)


def request_verification(user: User, request: Request, session: Session, next_path: str = "/") -> bool:
    if user.email_verified_at is not None:
        return True
    if not enabled():
        raise HTTPException(503, "E-mailverificatie is niet ingesteld.")
    auth.rate_limit(session, f"verify-send-minute:{user.id}", 1, 60)
    auth.rate_limit(session, f"verify-send-day:{user.id}", 5, 86400)
    auth.rate_limit(session, f"verify-send-ip:{auth.client_key(request)}", 10, 3600)
    auth.rate_limit(session, "verify-send-global", 200, 86400)
    token = secrets.token_urlsafe(32)
    # Rate limiting prevents concurrent sends for one account; one row per user
    # additionally ensures a newer challenge supersedes any previous link.
    challenge = session.get(EmailVerification, user.id)
    if challenge is None:
        challenge = EmailVerification(user_id=user.id, email=user.email, token_hash=auth.token_hash(token), expires_at=utc_now())
    challenge.next_path = return_path(next_path)
    challenge.email = user.email
    challenge.token_hash = auth.token_hash(token)
    challenge.expires_at = utc_now() + timedelta(hours=24)
    session.add(challenge)
    for expired in session.exec(select(EmailVerification).where(EmailVerification.expires_at < utc_now())).all():
        if expired.user_id != user.id:
            session.delete(expired)
    session.commit()
    try:
        send_verification(user.email, token)
    except (OSError, smtplib.SMTPException, ValueError):
        # Never export SMTP responses, addresses, credentials or link tokens.
        event("auth.email.delivery", outcome="failure")
        return False
    event("auth.email.delivery", outcome="success")
    return True


def confirm(user: User, token: str, session: Session) -> str:
    user_id, email = user.id, user.email
    session.rollback()
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    challenge = session.get(EmailVerification, user_id, populate_existing=True)
    current = session.get(User, user_id, populate_existing=True)
    if (not challenge or not current or current.email != email or challenge.email != email
            or as_utc(challenge.expires_at) <= utc_now()
            or not secrets.compare_digest(challenge.token_hash, auth.token_hash(token))):
        session.rollback()
        raise HTTPException(400, "Deze link is ongeldig, verlopen of hoort bij een ander account. Vraag zo nodig een nieuwe aan.")
    current.email_verified_at = utc_now()
    session.add(current)
    next_path = challenge.next_path
    session.delete(challenge)
    session.commit()
    return next_path
