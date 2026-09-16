"""Single-use mailbox recovery for local-password accounts."""

import secrets
import smtplib
from datetime import timedelta

from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy import delete
from sqlmodel import Session, select

from app import auth, email_verification
from app.models import (
    EmailVerification,
    LoginSession,
    PasswordReset,
    User,
    as_utc,
    utc_now,
)
from app.telemetry import event


def request_reset(email: str, request: Request, session: Session, delivery: BackgroundTasks) -> None:
    auth.check_origin(request)
    if not email_verification.enabled():
        raise HTTPException(503, "Wachtwoordherstel is niet ingesteld.")
    auth.rate_limit(session, f"reset-ip:{auth.client_key(request)}", 10, 3600)
    # Apply recipient limits even to unknown/OIDC-only addresses. Account state
    # never changes the response body/status, including delivery failures.
    try:
        auth.rate_limit(session, f"reset-minute:{email}", 1, 60)
        auth.rate_limit(session, f"reset-day:{email}", 5, 86400)
    except HTTPException as exc:
        if exc.status_code != 429:
            raise
        return
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not user.password_hash:
        return
    try:
        auth.rate_limit(session, "verify-send-global", 200, 86400)
    except HTTPException as exc:
        if exc.status_code != 429:
            raise
        return
    token = secrets.token_urlsafe(32)
    row = session.get(PasswordReset, user.id)
    if row is None:
        row = PasswordReset(
            user_id=user.id,
            email=user.email,
            token_hash="",
            password_fingerprint="",
            expires_at=utc_now(),
        )
    row.email = user.email
    row.token_hash = auth.token_hash(token)
    row.password_fingerprint = auth.token_hash(user.password_hash)
    row.expires_at = utc_now() + timedelta(minutes=30)
    session.add(row)
    for expired in session.exec(
        select(PasswordReset).where(PasswordReset.expires_at < utc_now())
    ).all():
        if expired.user_id != user.id:
            session.delete(expired)
    session.commit()
    # SMTP runs after the neutral response, so provider latency does not reveal
    # whether an address exists. A failed delivery can be requested again later.
    delivery.add_task(_deliver_reset, user.email, token)


def _deliver_reset(email: str, token: str) -> None:
    try:
        email_verification.send_mail(
            email,
            "Nieuw wachtwoord voor PNBallie",
            "Kies een nieuw wachtwoord voor PNBallie:\n\n"
            + f"{auth.app_origin()}/reset-password#token={token}"
            + "\n\nDe link is 30 minuten geldig en kan één keer worden gebruikt."
            " Na het opslaan moet je opnieuw inloggen op al je apparaten."
            "\n\nHeb je dit niet aangevraagd? Dan hoef je niets te doen; je wachtwoord blijft ongewijzigd.\n",
        )
    except (OSError, smtplib.SMTPException, ValueError):
        event("auth.password_reset.delivery", outcome="failure")
        return
    event("auth.password_reset.delivery", outcome="success")


def reset_password(
    token: str, new_password: str, request: Request, session: Session
) -> None:
    auth.check_origin(request)
    auth.rate_limit(session, f"reset-confirm:{auth.client_key(request)}", 20, 900)
    digest = auth.token_hash(token)
    row = session.exec(
        select(PasswordReset).where(PasswordReset.token_hash == digest)
    ).first()
    if not row or as_utc(row.expires_at) <= utc_now():
        raise HTTPException(
            400, "Deze herstellink is ongeldig of verlopen. Vraag een nieuwe aan."
        )
    # Do expensive Argon2 work outside the SQLite write transaction. Recheck the
    # challenge and password version under the lock before consuming the proof.
    encoded = auth.password_hash(new_password)
    session.rollback()
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    row = session.exec(
        select(PasswordReset)
        .where(PasswordReset.token_hash == digest)
        .execution_options(populate_existing=True)
    ).first()
    user = session.get(User, row.user_id, populate_existing=True) if row else None
    if (
        not row
        or not user
        or not user.password_hash
        or user.email != row.email
        or as_utc(row.expires_at) <= utc_now()
        or not secrets.compare_digest(
            row.password_fingerprint, auth.token_hash(user.password_hash)
        )
    ):
        session.rollback()
        raise HTTPException(
            400, "Deze herstellink is ongeldig of verlopen. Vraag een nieuwe aan."
        )
    user.password_hash = encoded
    # The reset proves mailbox control and replaces every password/session from
    # before that proof, so pending local accounts can recover safely too.
    user.email_verified_at = user.email_verified_at or utc_now()
    session.add(user)
    session.exec(delete(LoginSession).where(LoginSession.user_id == user.id))
    session.exec(delete(EmailVerification).where(EmailVerification.user_id == user.id))
    session.delete(row)
    session.commit()
    event("auth.password_reset.finished", outcome="success")
