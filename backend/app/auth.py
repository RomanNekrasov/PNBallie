"""Portable authentication: opaque cookie sessions and optional standard OIDC."""

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from urllib.parse import urlparse

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import case, delete, or_
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session

from app.database import get_session
from app.models import (
    AuthThrottle,
    Group,
    LoginSession,
    Membership,
    User,
    as_utc,
    utc_now,
)

SESSION_COOKIE = "pnballie_session"
OIDC_COOKIE = "pnballie_oidc_state"
SESSION_DAYS = 14
_password_hasher = PasswordHasher()
# Equalize the expensive verification path for unknown accounts.
_dummy_password_hash = _password_hasher.hash(secrets.token_urlsafe(32))


class AuthConfigurationError(RuntimeError):
    pass


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.lower() in {"1", "true", "yes"}


def production() -> bool:
    return os.getenv("APP_ENV", "development").lower() == "production"


def cookie_secure() -> bool:
    return env_bool("AUTH_COOKIE_SECURE", production())


def app_origin() -> str:
    return os.getenv("AUTH_APP_ORIGIN", "http://localhost:5173").rstrip("/")


def oidc_settings() -> dict | None:
    issuer = os.getenv("OIDC_ISSUER", "").rstrip("/")
    client_id = os.getenv("OIDC_CLIENT_ID", "").strip()
    if not issuer and not client_id:
        return None
    if not issuer or not client_id:
        raise AuthConfigurationError("OIDC_ISSUER and OIDC_CLIENT_ID must both be configured")
    return {
        "issuer": issuer,
        "client_id": client_id,
        "client_secret": os.getenv("OIDC_CLIENT_SECRET", ""),
        "name": os.getenv("OIDC_NAME", "Single sign-on"),
        "redirect_uri": f"{app_origin()}/api/auth/oidc/callback",
    }


def validate_auth_configuration() -> None:
    origin = urlparse(app_origin())
    if origin.scheme not in {"http", "https"} or not origin.netloc or origin.path or origin.query or origin.fragment:
        raise AuthConfigurationError("AUTH_APP_ORIGIN must be an HTTP(S) origin without a path")
    if production():
        if not os.getenv("AUTH_APP_ORIGIN") or origin.scheme != "https":
            raise AuthConfigurationError("Production requires an HTTPS AUTH_APP_ORIGIN")
        if not cookie_secure():
            raise AuthConfigurationError("Production requires AUTH_COOKIE_SECURE=true")
    settings = oidc_settings()
    if settings and urlparse(settings["issuer"]).scheme != "https":
        if production() or urlparse(settings["issuer"]).hostname not in {"localhost", "127.0.0.1"}:
            raise AuthConfigurationError("OIDC_ISSUER must use HTTPS (localhost HTTP allowed in development)")


def check_origin(request: Request) -> None:
    # Browser requests include Origin. Nonbrowser clients still need the CSRF
    # token whenever they use a session for a state-changing API call.
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") != app_origin():
        raise HTTPException(status_code=403, detail="Request origin is not allowed")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="Cross-site request is not allowed")


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        return _password_hasher.verify(encoded or _dummy_password_hash, password) and encoded is not None
    except (VerificationError, InvalidHashError):
        return False


def rate_limit(session: Session, key: str, limit: int, seconds: int) -> None:
    """Atomic durable counters across SQLite workers; no raw IPs/e-mails stored."""
    now = utc_now()
    key = token_hash(key)
    expired = AuthThrottle.window_start <= now - timedelta(seconds=seconds)
    statement = insert(AuthThrottle).values(key=key, window_start=now, attempts=1)
    statement = statement.on_conflict_do_update(
        index_elements=["key"],
        set_={
            "window_start": case((expired, now), else_=AuthThrottle.window_start),
            "attempts": case((expired, 1), else_=AuthThrottle.attempts + 1),
        },
        where=or_(expired, AuthThrottle.attempts < limit),
    ).returning(AuthThrottle.key)
    accepted = session.execute(statement).first()
    session.commit()  # Failed credential checks must retain their counter.
    if accepted is None:
        row = session.get(AuthThrottle, key)
        retry = max(1, seconds - int((now - as_utc(row.window_start)).total_seconds()))
        raise HTTPException(status_code=429, detail="Too many attempts; please try again later", headers={"Retry-After": str(retry)})
    session.exec(delete(AuthThrottle).where(AuthThrottle.window_start < now - timedelta(days=2)).execution_options(synchronize_session=False))
    session.commit()


def client_key(request: Request) -> str:
    # Uvicorn accepts forwarded headers only from its configured trusted proxy.
    return request.client.host if request.client else "unknown"


def create_session(user: User, response: Response, session: Session) -> str:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    session.add(LoginSession(token_hash=token_hash(token), user_id=user.id, csrf_token=csrf, expires_at=utc_now() + timedelta(days=SESSION_DAYS)))
    session.exec(delete(LoginSession).where(LoginSession.expires_at < utc_now()).execution_options(synchronize_session=False))
    session.commit()
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, secure=cookie_secure(), samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return csrf


def require_user(request: Request, session: Session = Depends(get_session)) -> User:
    raw = request.cookies.get(SESSION_COOKIE, "")
    login = session.get(LoginSession, token_hash(raw)) if raw else None
    if login is None or as_utc(login.expires_at) <= utc_now():
        raise HTTPException(status_code=401, detail="Please sign in")
    user = session.get(User, login.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        submitted = request.headers.get("x-csrf-token", "")
        if not submitted or not hmac.compare_digest(submitted.encode(), login.csrf_token.encode()):
            raise HTTPException(status_code=403, detail="CSRF token is missing or invalid")
    request.state.login_session = login
    return user


@dataclass(frozen=True)
class GroupContext:
    id: int
    role: str
    user: User


def require_group(request: Request, user: User = Depends(require_user), session: Session = Depends(get_session)) -> GroupContext:
    raw = request.headers.get("x-group-id", "")
    try:
        group_id = int(raw)
        if group_id <= 0:
            raise ValueError
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Select a group with X-Group-ID") from exc
    membership = session.get(Membership, (group_id, user.id))
    if membership is None or session.get(Group, group_id) is None:
        # Conceal whether a foreign group's identifier exists.
        raise HTTPException(status_code=404, detail="Group not found")
    return GroupContext(id=group_id, role=membership.role, user=user)


def require_group_admin(group: GroupContext = Depends(require_group)) -> GroupContext:
    if group.role != "admin":
        raise HTTPException(status_code=403, detail="Group administrator access is required")
    return group


@lru_cache(maxsize=4)
def openid_configuration(issuer: str) -> dict:
    response = httpx.get(f"{issuer}/.well-known/openid-configuration", timeout=10)
    response.raise_for_status()
    config = response.json()
    if config.get("issuer") != issuer:
        raise ValueError("OIDC discovery issuer does not match configuration")
    for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        endpoint = urlparse(config.get(name, ""))
        if endpoint.scheme != "https" and not (not production() and endpoint.scheme == "http" and endpoint.hostname in {"localhost", "127.0.0.1"}):
            raise ValueError("OIDC endpoint must use HTTPS")
    return config
