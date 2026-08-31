import os
from functools import lru_cache

import httpx
import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWK


class AuthConfigurationError(RuntimeError):
    pass


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AuthConfigurationError(f"Missing required authentication setting: {name}")
    return value


def validate_auth_configuration() -> None:
    _required_env("ENTRA_TENANT_ID")
    _required_env("ENTRA_AUDIENCE")
    _required_env("ENTRA_REQUIRED_SCOPE")


@lru_cache(maxsize=4)
def _openid_configuration(tenant_id: str) -> dict:
    url = f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
    response = httpx.get(url, timeout=5.0)
    response.raise_for_status()
    return response.json()


@lru_cache(maxsize=4)
def _jwks(jwks_uri: str) -> dict:
    response = httpx.get(jwks_uri, timeout=5.0)
    response.raise_for_status()
    return response.json()


def _unauthorized(detail: str = "Invalid or missing bearer token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_entra_token(request: Request) -> dict:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()

    try:
        tenant_id = _required_env("ENTRA_TENANT_ID")
        audience = _required_env("ENTRA_AUDIENCE")
        required_scope = _required_env("ENTRA_REQUIRED_SCOPE")
        configuration = _openid_configuration(tenant_id)
        issuer = configuration["issuer"]
        jwks = _jwks(configuration["jwks_uri"])
        header = jwt.get_unverified_header(token)
        key_data = next(key for key in jwks["keys"] if key.get("kid") == header.get("kid"))
        claims = jwt.decode(
            token,
            key=PyJWK.from_dict(key_data).key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "iss", "aud", "tid"]},
        )
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (httpx.HTTPError, KeyError, StopIteration, jwt.PyJWTError, ValueError, TypeError) as exc:
        raise _unauthorized() from exc

    if claims.get("tid") != tenant_id:
        raise _unauthorized()
    if required_scope not in set(str(claims.get("scp", "")).split()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Required scope is missing")
    return claims
