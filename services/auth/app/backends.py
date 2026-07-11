import uuid

from fastapi_users import FastAPIUsers, models
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.jwt import generate_jwt

from app.config import settings
from app.manager import get_user_manager
from app.models import User


class ClaimsJWTStrategy(JWTStrategy):
    """JWTStrategy that embeds `email` and `is_superuser` in the token.

    fastapi-users only puts `sub` (the user id) in the token. We add these two
    claims so the OTHER services (Submissions) can authorize a request — decide
    whether the caller is an admin — by verifying the token locally, with no
    network call back to Auth. Reading the token here still works because
    fastapi-users only reads `sub` on the way in; extra claims are ignored.
    """

    async def write_token(self, user: User) -> str:
        data = {
            "sub": str(user.id),
            "aud": self.token_audience,
            "email": user.email,
            "is_superuser": user.is_superuser,
        }
        return generate_jwt(
            data, self.encode_key, self.lifetime_seconds, algorithm=self.algorithm
        )


def get_jwt_strategy() -> JWTStrategy[models.UP, models.ID]:
    return ClaimsJWTStrategy(
        secret=settings.secret, lifetime_seconds=settings.jwt_lifetime_seconds
    )


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# Cookie backend for the browser UI, alongside the JWT bearer backend (API
# clients). The cookie is host-scoped, so it is also sent to the Submissions
# service during local development.
cookie_transport = CookieTransport(
    cookie_name=settings.auth_cookie_name,
    cookie_max_age=settings.jwt_lifetime_seconds,
    cookie_secure=settings.cookie_secure,
    cookie_httponly=True,
    cookie_samesite="lax",
)

cookie_auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager, [auth_backend, cookie_auth_backend]
)

current_active_user = fastapi_users.current_user(active=True)
optional_current_user = fastapi_users.current_user(active=True, optional=True)
