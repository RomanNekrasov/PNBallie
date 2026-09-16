import smtplib
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app import auth, email_verification
from app.models import (
    AuthThrottle,
    EmailVerification,
    LoginSession,
    PasswordReset,
    User,
    utc_now,
)


@pytest.fixture
def reset_mail(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "true")
    monkeypatch.setattr(email_verification, "send_verification", lambda *_: None)
    sent = []
    monkeypatch.setattr(
        email_verification, "send_mail", lambda *args: sent.append(args)
    )
    return sent


def token(mail):
    return mail[-1][2].split("#token=")[1].split()[0]


def request(client, email="admin@example.org"):
    return client.post("/api/auth/password/forgot", json={"email": email})


def reset(client, value, password="a-new-long-password"):
    return client.post(
        "/api/auth/password/reset", json={"token": value, "new_password": password}
    )


def clear_limits(engine):
    with Session(engine) as session:
        for row in session.exec(select(AuthThrottle)).all():
            session.delete(row)
        session.commit()


def test_reset_proves_mailbox_revokes_sessions_and_is_one_use(
    registered, client_factory, db_engine, reset_mail
):
    original, user = registered()
    second = client_factory()
    assert (
        second.post(
            "/api/auth/login",
            json={"email": user["email"], "password": "a-long-test-password"},
        ).status_code
        == 200
    )
    anonymous = client_factory()
    assert request(anonymous, " ADMIN@example.org ").status_code == 202
    value = token(reset_mail)
    assert reset_mail[0][0] == user["email"]
    assert "http://testserver/reset-password#token=" in reset_mail[0][2]
    with Session(db_engine) as session:
        row = session.get(PasswordReset, user["id"])
        assert row.token_hash == auth.token_hash(value) and row.token_hash != value
        assert session.get(User, user["id"]).email_verified_at is None
        assert len(session.exec(select(LoginSession)).all()) == 2
    assert anonymous.get("/api/auth/password/reset").status_code == 405
    result = reset(anonymous, value)
    assert result.status_code == 204
    assert result.headers["cache-control"] == "no-store"
    for client in (original, second, anonymous):
        assert client.get("/api/auth/me").status_code == 401
    assert reset(anonymous, value).status_code == 400
    assert (
        anonymous.post(
            "/api/auth/login",
            json={"email": user["email"], "password": "a-long-test-password"},
        ).status_code
        == 401
    )
    result = anonymous.post(
        "/api/auth/login",
        json={"email": user["email"], "password": "a-new-long-password"},
    )
    assert result.status_code == 200 and result.json()["user"]["email_verified"]
    with Session(db_engine) as session:
        assert session.get(PasswordReset, user["id"]) is None
        assert session.get(EmailVerification, user["id"]) is None


def test_neutral_response_unknown_oidc_throttled_and_failed_delivery(
    registered, client_factory, db_engine, reset_mail, monkeypatch
):
    registered()
    with Session(db_engine) as session:
        session.add(
            User(
                email="oidc@example.org",
                display_name="OIDC",
                oidc_issuer="https://issuer.example",
                oidc_subject="subject",
            )
        )
        session.commit()
    anonymous = client_factory()
    results = [
        request(anonymous, address)
        for address in (
            "missing@example.org",
            "oidc@example.org",
            "admin@example.org",
            "admin@example.org",
        )
    ]
    assert len(reset_mail) == 1
    clear_limits(db_engine)

    def fail(*_):
        raise smtplib.SMTPException("private provider failure")

    monkeypatch.setattr(email_verification, "send_mail", fail)
    results.append(request(anonymous))
    assert all(
        response.status_code == 202 and response.json() == results[0].json()
        for response in results
    )
    assert all("private" not in response.text for response in results)


@pytest.mark.parametrize(
    "invalidate", ["expired", "email", "password", "oidc", "resend", "change"]
)
def test_invalidated_proof_cannot_replace_password(
    registered, client_factory, db_engine, reset_mail, invalidate
):
    client, user = registered()
    anonymous = client_factory()
    request(anonymous)
    value = token(reset_mail)
    if invalidate == "resend":
        clear_limits(db_engine)
        request(anonymous)
        assert token(reset_mail) != value
    elif invalidate == "change":
        assert (
            client.post(
                "/api/auth/password",
                json={
                    "current_password": "a-long-test-password",
                    "new_password": "another-long-password",
                },
            ).status_code
            == 200
        )
    else:
        with Session(db_engine) as session:
            row = session.get(PasswordReset, user["id"])
            account = session.get(User, user["id"])
            if invalidate == "expired":
                row.expires_at = utc_now() - timedelta(seconds=1)
            if invalidate == "email":
                account.email = "changed@example.org"
            if invalidate == "password":
                account.password_hash = auth.password_hash("changed-password")
            if invalidate == "oidc":
                account.password_hash = None
            session.add(row)
            session.add(account)
            session.commit()
    assert reset(anonymous, value).status_code == 400
    assert client.get("/api/auth/me").status_code == 200


def test_origin_validation_and_limits(client, reset_mail):
    assert request(client, "bad").status_code == 422
    assert (
        client.post(
            "/api/auth/password/forgot",
            json={"email": "x@example.org"},
            headers={"Origin": "https://foreign.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/password/reset",
            json={"token": "x" * 43, "new_password": "long-new-password"},
            headers={"Origin": "https://foreign.example"},
        ).status_code
        == 403
    )
    assert reset(client, "x" * 43, "short").status_code == 422
    for i in range(10):
        assert request(client, f"unknown{i}@example.org").status_code == 202
    assert request(client).status_code == 429
    assert not reset_mail


def test_email_verification_token_cannot_reset_password(
    registered, client_factory, db_engine, reset_mail
):
    _, user = registered()
    with Session(db_engine) as session:
        proof = session.get(EmailVerification, user["id"])
        proof.token_hash = auth.token_hash("x" * 43)
        session.add(proof)
        session.commit()
    assert reset(client_factory(), "x" * 43).status_code == 400


def test_concurrent_consumption_has_exactly_one_winner(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi import HTTPException
    from sqlmodel import SQLModel, create_engine
    from starlette.requests import Request

    from app import password_reset

    engine = create_engine(f"sqlite:///{tmp_path / 'race.sqlite'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    encoded = auth.password_hash("original-password")
    with Session(engine) as session:
        user = User(email="race@example.org", display_name="Race", password_hash=encoded)
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(PasswordReset(user_id=user.id, email=user.email, token_hash=auth.token_hash("x" * 43), password_fingerprint=auth.token_hash(encoded), expires_at=utc_now() + timedelta(minutes=30)))
        session.commit()
    barrier = Barrier(2)
    real_hash = auth.password_hash
    def synchronized_hash(value):
        result = real_hash(value)
        barrier.wait(timeout=5)
        return result
    monkeypatch.setattr(auth, "password_hash", synchronized_hash)
    monkeypatch.setenv("AUTH_APP_ORIGIN", "http://testserver")
    def consume(index):
        request = Request({"type": "http", "method": "POST", "headers": [], "client": (f"127.0.0.{index}", 1234)})
        with Session(engine) as session:
            try:
                password_reset.reset_password("x" * 43, f"new-password-{index}", request, session)
                return 204
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(consume, (1, 2))) == [204, 400]
    engine.dispose()
