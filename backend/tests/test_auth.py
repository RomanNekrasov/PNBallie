import base64
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import auth
from app.main import app

TENANT = "11111111-1111-1111-1111-111111111111"
AUDIENCE = "api://pnballie"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"
KID = "test-key"


def _encode_int(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture
def keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private_key.public_key().public_numbers()
    jwk = {"kty": "RSA", "kid": KID, "use": "sig", "alg": "RS256", "n": _encode_int(public.n), "e": _encode_int(public.e)}
    return private_key, jwk


@pytest.fixture(autouse=True)
def entra(monkeypatch, keys):
    monkeypatch.setenv("ENTRA_TENANT_ID", TENANT)
    monkeypatch.setenv("ENTRA_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("ENTRA_REQUIRED_SCOPE", "user")
    monkeypatch.setattr(auth, "_openid_configuration", lambda _: {"issuer": ISSUER, "jwks_uri": "https://entra.test/keys"})
    monkeypatch.setattr(auth, "_jwks", lambda _: {"keys": [keys[1]]})


def token(private_key, **overrides) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "tid": TENANT,
        "scp": "user",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": KID})


def test_health_endpoints_are_public():
    client = TestClient(app)
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_every_api_endpoint_rejects_missing_token():
    client = TestClient(app)
    api_routes = [route for route in app.routes if getattr(route, "path", "").startswith("/api/")]
    assert api_routes
    for route in api_routes:
        method = next(method for method in route.methods if method not in {"HEAD", "OPTIONS"})
        path = route.path.replace("{player_id}", "1").replace("{match_id}", "1")
        assert client.request(method, path).status_code == 401, f"{method} {path} was not protected"


def test_valid_token_is_accepted(keys):
    response = TestClient(app).get("/api/players", headers={"Authorization": f"Bearer {token(keys[0])}"})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        {"iss": "https://login.microsoftonline.com/wrong/v2.0"},
        {"tid": "wrong-tenant"},
        {"aud": "api://wrong"},
    ],
)
def test_invalid_claims_return_401(keys, overrides):
    response = TestClient(app).get("/api/players", headers={"Authorization": f"Bearer {token(keys[0], **overrides)}"})
    assert response.status_code == 401


def test_invalid_signature_returns_401(keys):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    response = TestClient(app).get("/api/players", headers={"Authorization": f"Bearer {token(other_key)}"})
    assert response.status_code == 401


def test_missing_scope_returns_403(keys):
    response = TestClient(app).get("/api/players", headers={"Authorization": f"Bearer {token(keys[0], scp='other')}"})
    assert response.status_code == 403


def test_production_startup_requires_auth_configuration(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    for name in ("ENTRA_TENANT_ID", "ENTRA_AUDIENCE", "ENTRA_REQUIRED_SCOPE"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(auth.AuthConfigurationError, match="ENTRA_TENANT_ID"):
        with TestClient(app):
            pass
