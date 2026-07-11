from types import SimpleNamespace

from fastapi import APIRouter, Depends, Form, Request
from fastapi_users import exceptions as fu_exceptions
from starlette.responses import RedirectResponse, Response

from app.backends import cookie_transport, get_jwt_strategy
from app.limits import login_rate_limit, register_rate_limit
from app.manager import get_user_manager
from app.models import User
from app.schemas import UserCreate
from app.templating import templates

router = APIRouter(tags=["auth-web"])


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set the auth cookie, sourcing every parameter from the shared
    CookieTransport so login/logout config stays in one place."""
    response.set_cookie(
        cookie_transport.cookie_name,
        token,
        max_age=cookie_transport.cookie_max_age,
        path=cookie_transport.cookie_path,
        domain=cookie_transport.cookie_domain,
        secure=cookie_transport.cookie_secure,
        httponly=cookie_transport.cookie_httponly,
        samesite=cookie_transport.cookie_samesite,
    )


async def _login_redirect(user: User, to: str = "/") -> RedirectResponse:
    token = await get_jwt_strategy().write_token(user)
    response = RedirectResponse(url=to, status_code=303)
    _set_auth_cookie(response, token)
    return response


@router.get("/login")
async def login_get(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


# Shares the "login" budget with POST /auth/jwt/login: both are the same
# brute-force surface, so they must drain one bucket.
@router.post("/login", dependencies=[Depends(login_rate_limit)])
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    user_manager=Depends(get_user_manager),
):
    credentials = SimpleNamespace(username=email, password=password)
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid credentials or inactive account.", "email": email},
            status_code=400,
        )
    return await _login_redirect(user)


@router.get("/register")
async def register_get(request: Request):
    return templates.TemplateResponse(request, "register.html", {})


@router.post("/register", dependencies=[Depends(register_rate_limit)])
async def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    user_manager=Depends(get_user_manager),
):
    try:
        user = await user_manager.create(
            UserCreate(email=email, password=password), safe=True, request=request
        )
    except fu_exceptions.UserAlreadyExists:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "A user with that email already exists.", "email": email},
            status_code=400,
        )
    except fu_exceptions.InvalidPasswordException as exc:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": f"Invalid password: {exc.reason}", "email": email},
            status_code=400,
        )
    return await _login_redirect(user)


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(
        cookie_transport.cookie_name,
        path=cookie_transport.cookie_path,
        domain=cookie_transport.cookie_domain,
    )
    return response
