import base64
import hashlib
import hmac
import secrets
from datetime import timedelta
from urllib.parse import unquote, urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import auth
from app.database import get_session
from app.models import LoginSession, OIDCLogin, User, as_utc, utc_now

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower() if isinstance(value, str) else value


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name must not be empty")
        return value


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str
    has_password: bool


class AuthRead(BaseModel):
    user: UserRead
    csrf_token: str


def authenticated(user: User, csrf_token: str) -> AuthRead:
    return AuthRead(user=UserRead(id=user.id, email=user.email, display_name=user.display_name, has_password=user.password_hash is not None), csrf_token=csrf_token)


@router.get("/providers")
def providers():
    settings = auth.oidc_settings()
    return {
        "local": True,
        "registration_enabled": auth.env_bool("AUTH_ALLOW_REGISTRATION", True),
        "oidc": {"name": settings["name"], "login_url": "/api/auth/oidc/login"} if settings else None,
    }


@router.post("/register", response_model=AuthRead, status_code=201)
def register(payload: Registration, request: Request, response: Response, session: Session = Depends(get_session)):
    auth.check_origin(request)
    if not auth.env_bool("AUTH_ALLOW_REGISTRATION", True):
        raise HTTPException(status_code=403, detail="Registration is disabled")
    auth.rate_limit(session, f"register:{auth.client_key(request)}", 5, 3600)
    if session.exec(select(User).where(User.email == payload.email)).first():
        raise HTTPException(status_code=409, detail="This e-mail address is already registered")
    user = User(email=payload.email, display_name=payload.display_name, password_hash=auth.password_hash(payload.password))
    session.add(user)
    try:
        session.commit()
        session.refresh(user)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="This e-mail address is already registered") from exc
    return authenticated(user, auth.create_session(user, response, session))


@router.post("/login", response_model=AuthRead)
def login(payload: Credentials, request: Request, response: Response, session: Session = Depends(get_session)):
    auth.check_origin(request)
    auth.rate_limit(session, f"login-ip:{auth.client_key(request)}", 30, 900)
    auth.rate_limit(session, f"login-email:{payload.email}", 10, 900)
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not auth.verify_password(payload.password, user.password_hash if user else None):
        raise HTTPException(status_code=401, detail="Invalid e-mail address or password")
    return authenticated(user, auth.create_session(user, response, session))


@router.get("/me", response_model=AuthRead)
def me(request: Request, response: Response, user: User = Depends(auth.require_user)):
    response.headers["Cache-Control"] = "no-store"
    return authenticated(user, request.state.login_session.csrf_token)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, user: User = Depends(auth.require_user), session: Session = Depends(get_session)):
    session.delete(request.state.login_session)
    session.commit()
    response.delete_cookie(auth.SESSION_COOKIE, path="/", httponly=True, secure=auth.cookie_secure(), samesite="lax")


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


@router.post("/password", response_model=AuthRead)
def change_password(payload: PasswordChange, request: Request, response: Response, user: User = Depends(auth.require_user), session: Session = Depends(get_session)):
    auth.rate_limit(session, f"password:{user.id}", 10, 900)
    if not user.password_hash or not auth.verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    user.password_hash = auth.password_hash(payload.new_password)
    session.add(user)
    session.exec(delete(LoginSession).where(LoginSession.user_id == user.id))
    session.commit()
    return authenticated(user, auth.create_session(user, response, session))


@router.get("/oidc/login")
def oidc_login(request: Request, next: str = "/", session: Session = Depends(get_session)):
    settings = auth.oidc_settings()
    if not settings:
        raise HTTPException(status_code=404, detail="Single sign-on is not configured")
    auth.rate_limit(session, f"oidc:{auth.client_key(request)}", 20, 900)
    try:
        configuration = auth.openid_configuration(settings["issuer"])
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=502, detail="Unable to contact the sign-in provider") from exc
    if len(next) > 500 or not next.startswith("/") or next.startswith("//") or "\\" in unquote(next) or any(ord(ch) < 32 for ch in unquote(next)) or unquote(next).startswith("//"):
        raise HTTPException(status_code=400, detail="Invalid return path")
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    session.add(OIDCLogin(state_hash=auth.token_hash(state), nonce=nonce, verifier=verifier, next_path=next, expires_at=utc_now() + timedelta(minutes=10)))
    for expired in session.exec(select(OIDCLogin).where(OIDCLogin.expires_at < utc_now())).all():
        session.delete(expired)
    session.commit()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode({"response_type": "code", "client_id": settings["client_id"], "redirect_uri": settings["redirect_uri"], "scope": "openid email profile", "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"})
    response = RedirectResponse(f"{configuration['authorization_endpoint']}?{query}", status_code=302)
    response.set_cookie(auth.OIDC_COOKIE, state, max_age=600, httponly=True, secure=auth.cookie_secure(), samesite="lax", path="/api/auth/oidc")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/oidc/callback")
def oidc_callback(request: Request, state: str = "", code: str = "", session: Session = Depends(get_session)):
    settings = auth.oidc_settings()
    cookie_state = request.cookies.get(auth.OIDC_COOKIE, "")
    attempt = session.get(OIDCLogin, auth.token_hash(state)) if state else None
    if not settings or not state or not cookie_state or not hmac.compare_digest(state.encode(), cookie_state.encode()) or not attempt or as_utc(attempt.expires_at) <= utc_now() or not code:
        raise HTTPException(status_code=400, detail="The sign-in request expired or is invalid; please try again")
    verifier, nonce, next_path = attempt.verifier, attempt.nonce, attempt.next_path
    session.delete(attempt)
    session.commit()  # consume before exchanging; callback codes cannot be replayed
    try:
        configuration = auth.openid_configuration(settings["issuer"])
        data = {"grant_type": "authorization_code", "code": code, "redirect_uri": settings["redirect_uri"], "client_id": settings["client_id"], "code_verifier": verifier}
        kwargs = {"auth": (settings["client_id"], settings["client_secret"])} if settings["client_secret"] else {}
        tokens = httpx.post(configuration["token_endpoint"], data=data, timeout=15, **kwargs)
        tokens.raise_for_status()
        id_token = tokens.json()["id_token"]
        keys = httpx.get(configuration["jwks_uri"], timeout=10)
        keys.raise_for_status()
        header = jwt.get_unverified_header(id_token)
        algorithm = header.get("alg")
        if algorithm not in {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}:
            raise ValueError("Unsupported signing algorithm")
        key = next(key for key in keys.json()["keys"] if key.get("kid") == header.get("kid"))
        claims = jwt.decode(id_token, jwt.PyJWK.from_dict(key).key, algorithms=[algorithm], audience=settings["client_id"], issuer=settings["issuer"], options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]})
        if not hmac.compare_digest(str(claims["nonce"]).encode(), nonce.encode()):
            raise ValueError("Invalid nonce")
        if isinstance(claims["aud"], list) and len(claims["aud"]) > 1 and claims.get("azp") != settings["client_id"]:
            raise ValueError("Invalid authorized party")
        if claims.get("azp", settings["client_id"]) != settings["client_id"]:
            raise ValueError("Invalid authorized party")
        if not isinstance(claims["sub"], str) or not claims["sub"]:
            raise ValueError("Invalid subject")
    except (httpx.HTTPError, jwt.PyJWTError, ValueError, KeyError, StopIteration, TypeError) as exc:
        raise HTTPException(status_code=401, detail="The sign-in provider returned an invalid response") from exc
    user = session.exec(select(User).where(User.oidc_issuer == settings["issuer"], User.oidc_subject == claims["sub"])).first()
    if user is None:
        if not auth.env_bool("AUTH_ALLOW_REGISTRATION", True):
            raise HTTPException(status_code=403, detail="Registration is disabled")
        email = str(claims.get("email", "")).strip().lower()
        if claims.get("email_verified") is not True or not email or len(email) > 254 or "@" not in email:
            raise HTTPException(status_code=403, detail="A verified e-mail address is required from the sign-in provider")
        if session.exec(select(User).where(User.email == email)).first():
            raise HTTPException(status_code=409, detail="This e-mail already has an account; use its original sign-in method")
        user = User(email=email, display_name=str(claims.get("name") or email.split("@")[0]).strip()[:80] or "Speler", oidc_issuer=settings["issuer"], oidc_subject=claims["sub"])
        session.add(user)
        try:
            session.commit()
            session.refresh(user)
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="This account already exists; please sign in again") from exc
    response = RedirectResponse(f"{auth.app_origin()}{next_path}", status_code=302)
    auth.create_session(user, response, session)
    response.delete_cookie(auth.OIDC_COOKIE, path="/api/auth/oidc")
    return response
