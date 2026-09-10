import base64
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import auth
from app.main import app
from app.models import AuthThrottle, LoginSession, OIDCLogin, User, utc_now


def test_public_providers_and_health(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/api/auth/providers").json() == {"local": True, "registration_enabled": True, "oidc": None}


@pytest.mark.parametrize("path", ["/api/players", "/api/players/me", "/api/groups", "/api/groups/members", "/api/groups/invites", "/api/matches", "/api/stats", "/api/auth/me"])
def test_private_api_requires_cookie(client, path):
    assert client.get(path).status_code == 401


def test_registration_hashes_password_and_sets_private_cookie(client, db_engine):
    response = client.post("/api/auth/register", json={"email": " ADMIN@example.org ", "display_name": " Admin ", "password": "a-long-test-password"})
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "admin@example.org"
    assert response.json()["user"]["display_name"] == "Admin"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    with Session(db_engine) as session:
        user = session.exec(select(User)).one()
        assert user.password_hash.startswith("$argon2id$")
        assert auth.verify_password("a-long-test-password", user.password_hash)
        login = session.exec(select(LoginSession)).one()
        assert login.token_hash != client.cookies[auth.SESSION_COOKIE]
    assert client.get("/api/auth/me").json() == response.json()
    assert client.get("/api/groups").json() == []  # Registration never exposes legacy history.


def test_registration_validation_duplicate_and_switch(client, monkeypatch):
    payload = {"email": "person@example.org", "display_name": "Person", "password": "a-long-test-password"}
    assert client.post("/api/auth/register", json={**payload, "password": "short"}).status_code == 422
    assert client.post("/api/auth/register", json={**payload, "display_name": " "}).status_code == 422
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409
    monkeypatch.setenv("AUTH_ALLOW_REGISTRATION", "false")
    assert client.post("/api/auth/register", json={**payload, "email": "another@example.org"}).status_code == 403


def test_csrf_origin_and_logout(registered):
    client, _ = registered()
    assert client.post("/api/groups", json={"name": "Pool"}, headers={"X-CSRF-Token": ""}).status_code == 403
    assert client.post("/api/groups", json={"name": "Pool"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/groups", json={"name": "Pool"}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/groups", json={"name": "Pool"}, headers={"Origin": "http://testserver"}).status_code == 201
    raw = client.cookies[auth.SESSION_COOKIE]
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set(auth.SESSION_COOKIE, raw)
    assert client.get("/api/auth/me").status_code == 401


def test_login_registration_origin_protected(client):
    body = {"email": "attacker@example.org", "display_name": "Attacker", "password": "a-long-test-password"}
    assert client.post("/api/auth/register", json=body, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/auth/login", json=body, headers={"Origin": "https://evil.example"}).status_code == 403


def test_login_and_expired_session(registered, client_factory, db_engine):
    _, user = registered()
    client = client_factory()
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "incorrect"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "unknown@example.org", "password": "incorrect"}).status_code == 401
    response = client.post("/api/auth/login", json={"email": user["email"].upper(), "password": "a-long-test-password"})
    assert response.status_code == 200
    with Session(db_engine) as session:
        login = session.get(LoginSession, auth.token_hash(client.cookies[auth.SESSION_COOKIE]))
        login.expires_at = utc_now() - timedelta(seconds=1)
        session.add(login)
        session.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_rate_limit_is_durable_and_expires(registered, client_factory, db_engine):
    _, user = registered()
    for _ in range(10):
        assert client_factory().post("/api/auth/login", json={"email": user["email"], "password": "incorrect"}).status_code == 401
    response = client_factory().post("/api/auth/login", json={"email": user["email"], "password": "a-long-test-password"})
    assert response.status_code == 429 and int(response.headers["retry-after"]) > 0
    with Session(db_engine) as session:
        row = session.get(AuthThrottle, auth.token_hash(f"login-email:{user['email']}"))
        row.window_start = utc_now() - timedelta(hours=1)
        session.add(row)
        session.commit()
    assert client_factory().post("/api/auth/login", json={"email": user["email"], "password": "a-long-test-password"}).status_code == 200


def test_password_change_revokes_all_previous_sessions(registered, client_factory):
    client, user = registered()
    other = client_factory()
    assert other.post("/api/auth/login", json={"email": user["email"], "password": "a-long-test-password"}).status_code == 200
    old_cookie, old_csrf = client.cookies[auth.SESSION_COOKIE], client.headers["X-CSRF-Token"]
    assert client.post("/api/auth/password", json={"current_password": "incorrect", "new_password": "a-new-long-password"}).status_code == 401
    response = client.post("/api/auth/password", json={"current_password": "a-long-test-password", "new_password": "a-new-long-password"})
    assert response.status_code == 200
    assert response.json()["csrf_token"] != old_csrf
    assert client.cookies[auth.SESSION_COOKIE] != old_cookie
    assert client.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 401
    assert other.post("/api/auth/login", json={"email": user["email"], "password": "a-long-test-password"}).status_code == 401
    assert other.post("/api/auth/login", json={"email": user["email"], "password": "a-new-long-password"}).status_code == 200


def test_production_startup_requires_https_origin(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("AUTH_APP_ORIGIN")
    with pytest.raises(auth.AuthConfigurationError, match="HTTPS AUTH_APP_ORIGIN"):
        with TestClient(app):
            pass
    monkeypatch.setenv("AUTH_APP_ORIGIN", "https://pool.example.org")
    with pytest.raises(auth.AuthConfigurationError, match="AUTH_COOKIE_SECURE"):
        with TestClient(app):
            pass
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    with TestClient(app):
        pass


@pytest.fixture
def oidc(client, monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER", "https://identity.example.org")
    monkeypatch.setenv("OIDC_CLIENT_ID", "pnballie")
    config = {"issuer": "https://identity.example.org", "authorization_endpoint": "https://identity.example.org/authorize", "token_endpoint": "https://identity.example.org/token", "jwks_uri": "https://identity.example.org/keys"}
    monkeypatch.setattr(auth, "openid_configuration", lambda _: config)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()

    def encoded(number):
        return base64.urlsafe_b64encode(number.to_bytes((number.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()
    jwk = {"kty": "RSA", "kid": "test", "alg": "RS256", "n": encoded(numbers.n), "e": encoded(numbers.e)}
    return config, private, jwk


def _oidc_callback(client, oidc, monkeypatch, db_engine, overrides=None):
    config, private, jwk = oidc
    response = client.get("/api/auth/oidc/login?next=/join/invitation", follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    with Session(db_engine) as session:
        attempt = session.get(OIDCLogin, auth.token_hash(query["state"][0]))
        claims = {"iss": config["issuer"], "aud": "pnballie", "sub": "subject-1", "nonce": attempt.nonce, "exp": utc_now() + timedelta(minutes=5), "iat": utc_now(), "email": "oidc@example.org", "email_verified": True, "name": "SSO Person"}
    claims.update(overrides or {})
    token = jwt.encode(claims, private, algorithm="RS256", headers={"kid": "test"})

    class Reply:
        def __init__(self, value):
            self.value = value

        def raise_for_status(self):
            pass

        def json(self):
            return self.value

    monkeypatch.setattr(auth.httpx, "post", lambda *a, **kw: Reply({"id_token": token}))
    monkeypatch.setattr(auth.httpx, "get", lambda *a, **kw: Reply({"keys": [jwk]}))
    callback = f"/api/auth/oidc/callback?state={query['state'][0]}&code=code"
    return client.get(callback, follow_redirects=False), callback


def test_oidc_pkce_state_nonce_and_return_path(client, oidc, monkeypatch, db_engine):
    response, callback = _oidc_callback(client, oidc, monkeypatch, db_engine)
    assert response.status_code == 302
    assert response.headers["location"] == "http://testserver/join/invitation"
    assert client.get("/api/auth/me").json()["user"]["email"] == "oidc@example.org"
    assert client.get(callback, follow_redirects=False).status_code == 400


@pytest.mark.parametrize("overrides,status", [({"nonce": "wrong"}, 401), ({"aud": "other"}, 401), ({"iss": "https://evil.example"}, 401), ({"email_verified": False}, 403), ({"exp": 1}, 401), ({"aud": ["pnballie", "other"], "azp": "other"}, 401)])
def test_oidc_rejects_invalid_claims(client, oidc, monkeypatch, db_engine, overrides, status):
    response, _ = _oidc_callback(client, oidc, monkeypatch, db_engine, overrides)
    assert response.status_code == status
    assert client.get("/api/auth/me").status_code == 401


def test_oidc_never_links_by_email_alone(client, registered, oidc, monkeypatch, db_engine):
    registered("oidc@example.org")
    response, _ = _oidc_callback(client, oidc, monkeypatch, db_engine)
    assert response.status_code == 409


@pytest.mark.parametrize("next_path", ["https://evil.example", "//evil.example", "/%2f/evil.example", "/%5cevil.example"])
def test_oidc_rejects_external_return_path(client, oidc, next_path):
    assert client.get("/api/auth/oidc/login", params={"next": next_path}, follow_redirects=False).status_code == 400


def test_oidc_callback_requires_matching_browser_state(client, oidc):
    assert client.get("/api/auth/oidc/callback?state=unknown&code=test", follow_redirects=False).status_code == 400
    response = client.get("/api/auth/oidc/login", follow_redirects=False)
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    client.cookies.clear()
    assert client.get("/api/auth/oidc/callback", params={"state": state, "code": "test"}, follow_redirects=False).status_code == 400
