from fastapi import Depends, FastAPI

from app.backends import auth_backend, fastapi_users
from app.limits import login_rate_limit, register_rate_limit
from app.schemas import UserCreate, UserRead, UserUpdate


def include_api_routers(app: FastAPI) -> None:
    """Mount the fastapi-users JSON API routers on the given app."""
    # The router-level dependency also covers /auth/jwt/logout — harmless, and
    # fastapi-users doesn't expose a per-route hook to scope it tighter.
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth/jwt",
        tags=["auth"],
        dependencies=[Depends(login_rate_limit)],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
        dependencies=[Depends(register_rate_limit)],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )
