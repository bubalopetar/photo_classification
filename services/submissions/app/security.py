"""Auth for this service: verify Auth-issued JWTs locally (no call to Auth)."""

import jwt
from fastapi import HTTPException, Request, status

from app.config import settings
from shared.security import JWTAuth, Principal, decode_token

_auth = JWTAuth(
    secret=settings.secret,
    audience=settings.jwt_audience,
    cookie_name=settings.auth_cookie_name,
)

current_user = _auth.current_user
current_superuser = _auth.current_superuser


def _decode(token: str) -> Principal | None:
    try:
        return decode_token(token, secret=settings.secret, audience=settings.jwt_audience)
    except jwt.InvalidTokenError:
        return None


async def current_user_any_channel(request: Request) -> Principal:
    """Like `current_user`, but also accepts the sqladmin session.

    Used only by the photo endpoint: <img> tags in the admin panel send the
    panel's signed session cookie (which stores the admin's JWT at login, see
    admin.AdminAuth), not a bearer header. Tries, in order: Authorization
    header, the photoauth cookie, then the admin session token.
    """
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        principal = _decode(header[7:])
        if principal:
            return principal

    cookie_token = request.cookies.get(settings.auth_cookie_name)
    if cookie_token:
        principal = _decode(cookie_token)
        if principal:
            return principal

    try:  # request.session raises if SessionMiddleware isn't installed
        session_token = request.session.get("token")
    except AssertionError:
        session_token = None
    if session_token:
        principal = _decode(session_token)
        if principal:
            return principal

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
