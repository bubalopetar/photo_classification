"""Stateless JWT verification shared by every service.

Auth is the only service that ISSUES tokens (via fastapi-users). Every other
service VERIFIES them locally with the shared secret — no per-request call back
to Auth. The token carries `sub` (user id), plus `email` and `is_superuser`
claims that Auth adds so downstream services can authorize (e.g. admin-only
routes) without another round trip.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ALGORITHM = "HS256"


@dataclass(frozen=True)
class Principal:
    """The authenticated caller, reconstructed from JWT claims."""

    id: uuid.UUID
    email: str | None
    is_superuser: bool


def encode_token(
    *,
    user_id: uuid.UUID | str,
    secret: str,
    audience: str,
    lifetime_seconds: int,
    email: str | None = None,
    is_superuser: bool = False,
    now: int | None = None,
) -> str:
    """Mint a token. Auth uses fastapi-users for this in production; this helper
    exists so tests (and any non-fastapi-users issuer) produce identical tokens.
    """
    issued = now if now is not None else int(time.time())
    payload = {
        "sub": str(user_id),
        "aud": [audience],
        "email": email,
        "is_superuser": is_superuser,
        "exp": issued + lifetime_seconds,
        "iat": issued,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, *, secret: str, audience: str) -> Principal:
    """Verify signature, audience and expiry; return the Principal.

    Raises jwt.InvalidTokenError (or a subclass) on any problem.
    """
    payload = jwt.decode(token, secret, audience=audience, algorithms=[ALGORITHM])
    return Principal(
        id=uuid.UUID(payload["sub"]),
        email=payload.get("email"),
        is_superuser=bool(payload.get("is_superuser", False)),
    )


class JWTAuth:
    """FastAPI dependency factory.

    Reads the token from the `Authorization: Bearer` header (API clients) or,
    failing that, the auth cookie (browser navigation). Exposes two
    dependencies: `current_user` (any active user) and `current_superuser`
    (admin-only). Both are plain callables suitable for `Depends(...)`.
    """

    def __init__(self, *, secret: str, audience: str, cookie_name: str = "photoauth"):
        self._secret = secret
        self._audience = audience
        bearer_scheme = HTTPBearer(auto_error=False)

        def get_current_user(
            credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
            cookie_token: str | None = Cookie(default=None, alias=cookie_name),
        ) -> Principal:
            token = credentials.credentials if credentials else cookie_token
            return self._principal_from_token(token)

        def get_current_superuser(
            principal: Principal = Depends(get_current_user),
        ) -> Principal:
            if not principal.is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin privileges required",
                )
            return principal

        self.current_user = get_current_user
        self.current_superuser = get_current_superuser

    def _principal_from_token(self, token: str | None) -> Principal:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return decode_token(token, secret=self._secret, audience=self._audience)
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
