from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from sqladmin import Admin
from starlette.responses import RedirectResponse

from app import admin as admin_mod
from app import backends, routers, web
from app.backends import cookie_transport
from app.bootstrap import ensure_superuser
from app.config import settings
from app.db import create_db_and_tables, engine, ping
from app.submissions_client import SUBMISSIONS_PUBLIC_URL, fetch_my_submissions
from app.templating import templates
from shared.cors import add_cors
from shared.health import health_router
from shared.logging import configure_logging

configure_logging(settings.log_level, service="auth")


class DashboardAdmin(Admin):
    async def index(self, request: Request) -> RedirectResponse:
        return RedirectResponse(request.url_for("admin:list", identity="user"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On SQLite (dev/test) create tables directly; on Postgres, Alembic has
    # already migrated the schema, so create_all is a harmless no-op safety net.
    if settings.database_url.startswith("sqlite"):
        await create_db_and_tables()
    await ensure_superuser()
    yield


app = FastAPI(title="Auth Service", lifespan=lifespan)
add_cors(app, settings.cors_origins)

admin = DashboardAdmin(
    app, engine, authentication_backend=admin_mod.AdminAuth(secret_key=settings.secret)
)
admin.add_view(admin_mod.UserAdmin)

routers.include_api_routers(app)
app.include_router(web.router)
app.include_router(health_router(service="auth", readiness_check=ping))


@app.get("/")
async def home(
    request: Request,
    user=Depends(backends.optional_current_user),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    # The user is already authenticated, so the cookie token is present; it is
    # forwarded so Submissions authorizes the call as the user themself.
    token = request.cookies.get(cookie_transport.cookie_name)
    submissions = await fetch_my_submissions(token) if token else None
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "user": user,
            "submissions_url": SUBMISSIONS_PUBLIC_URL,
            "submissions": submissions,
        },
    )
