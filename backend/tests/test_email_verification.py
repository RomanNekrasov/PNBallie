import smtplib
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app import auth, email_verification
from app.models import AuthThrottle, EmailVerification, User, utc_now


@pytest.fixture
def mail(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "true")
    sent = []
    monkeypatch.setattr(email_verification, "send_verification", lambda recipient, token: sent.append((recipient, token)))
    return sent


def signup(client, address="verify@example.org"):
    response = client.post("/api/auth/register", json={"email": address, "password": "long-password-for-tests", "display_name": "Test"})
    assert response.status_code == 201
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response


def test_required_and_one_use(client, db_engine, mail):
    response = signup(client)
    assert response.json()["verification_sent"] is True
    assert response.json()["user"]["verification_required"] is True
    token = mail[0][1]
    with Session(db_engine) as session:
        challenge = session.exec(select(EmailVerification)).one()
        assert challenge.token_hash == auth.token_hash(token) and token != challenge.token_hash
        assert session.get(User, challenge.user_id).email_verified_at is None
    for path in ("/api/groups", "/api/players", "/api/avatars/players/1.png", "/api/stats"):
        assert client.get(path).status_code == 403
    assert client.post("/api/groups", json={"name": "No access"}).status_code == 403
    assert client.post("/api/groups/join", json={"code": "unknown"}).status_code == 403
    # Neither opening a link nor anonymous POST confirms ownership.
    assert client.get("/api/auth/email/confirm").status_code == 405
    assert client.post("/api/auth/email/confirm", json={"token": token}).status_code == 200
    assert client.get("/api/auth/me").json()["user"]["email_verified"] is True
    assert client.get("/api/groups").status_code == 200
    assert client.post("/api/auth/email/confirm", json={"token": token}).status_code == 400
    with Session(db_engine) as session:
        assert session.exec(select(EmailVerification)).first() is None


def test_wrong_account_csrf_expiry_and_resend(client_factory, db_engine, mail):
    a, b = client_factory(), client_factory()
    signup(a)
    signup(b, "second@example.org")
    token = mail[0][1]
    assert b.post("/api/auth/email/confirm", json={"token": token}).status_code == 400
    assert a.post("/api/auth/email/confirm", json={"token": token}, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert a.post("/api/auth/email/confirm", json={"token": token}, headers={"Origin": "https://foreign.example"}).status_code == 403
    anonymous = client_factory()
    assert anonymous.post("/api/auth/email/confirm", json={"token": token}).status_code == 401
    assert a.post("/api/auth/email/request").status_code == 429
    with Session(db_engine) as session:
        challenge = session.exec(select(EmailVerification).where(EmailVerification.email == "verify@example.org")).one()
        challenge.expires_at = utc_now() - timedelta(seconds=1)
        session.add(challenge)
        for row in session.exec(select(AuthThrottle)).all():
            session.delete(row)
        session.commit()
    assert a.post("/api/auth/email/confirm", json={"token": token}).status_code == 400
    assert a.post("/api/auth/email/request").status_code == 200
    fresh = mail[-1][1]
    assert fresh != token
    assert a.post("/api/auth/email/confirm", json={"token": token}).status_code == 400
    assert a.post("/api/auth/email/confirm", json={"token": fresh}).status_code == 200


def test_existing_local_account_requires_proof(registered, monkeypatch):
    client, _ = registered()
    monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "true")
    assert client.get("/api/auth/me").json()["user"]["verification_required"] is True
    assert client.get("/api/groups").status_code == 403
    assert client.post("/api/auth/logout").status_code == 204


def test_delivery_failure_preserves_recoverable_account(client, monkeypatch, mail):
    def fail(*_):
        raise smtplib.SMTPAuthenticationError(535, b"private response")
    monkeypatch.setattr(email_verification, "send_verification", fail)
    response = signup(client)
    assert response.json()["verification_sent"] is False
    assert "private" not in response.text
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/groups").status_code == 403


def test_smtp_tls_and_message(monkeypatch):
    for key, value in {"SMTP_HOST":"smtp.example.org", "SMTP_USERNAME":"login", "SMTP_PASSWORD":"secret", "SMTP_FROM_EMAIL":"noreply@example.org", "SMTP_FROM_NAME":"PNBallie", "AUTH_APP_ORIGIN":"https://acceptatie.example.org"}.items():
        monkeypatch.setenv(key, value)
    calls = []
    class SMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.example.org", 587, 15)
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def ehlo(self): calls.append("ehlo")
        def starttls(self, context):
            assert context.check_hostname
            calls.append("tls")
        def login(self, user, password):
            assert (user, password) == ("login", "secret")
            calls.append("login")
        def send_message(self, message):
            assert message["To"] == "recipient@example.org"
            assert "https://acceptatie.example.org/verify-email#token=" in message.get_content()
            assert "secret" not in message.get_content()
            calls.append("send")
    monkeypatch.setattr(smtplib, "SMTP", SMTP)
    email_verification.send_verification("recipient@example.org", "x" * 43)
    assert calls == ["ehlo", "tls", "ehlo", "login", "send"]


def test_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "true")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with pytest.raises(auth.AuthConfigurationError):
        email_verification.validate_configuration()


@pytest.mark.parametrize("path", ["https://evil.example", "//evil.example", "/%2fevil.example", "/%5cevil.example", "/%0aevil", "/login", "/verify-email"])
def test_rejects_unsafe_return_paths(client, mail, path):
    response = client.post("/api/auth/register", json={"email": "invalid@example.org", "password": "long-password-for-tests", "display_name": "Test", "next_path": path})
    assert response.status_code == 422
    assert not mail


def test_invitation_survives_email_confirmation(client, mail):
    response = client.post("/api/auth/register", json={"email": "invite@example.org", "password": "long-password-for-tests", "display_name": "Test", "next_path": "/join/test-invite"})
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    response = client.post("/api/auth/email/confirm", json={"token": mail[0][1]})
    assert response.json() == {"verified": True, "next_path": "/join/test-invite"}
