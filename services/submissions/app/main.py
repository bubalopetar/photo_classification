from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

from app import admin as admin_mod
from app import routers, web
from app.config import settings
from app.db import create_db_and_tables, engine, ping
from shared.cors import add_cors
from shared.health import health_router
from shared.logging import configure_logging

configure_logging(settings.log_level, service="submissions")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url.startswith("sqlite"):
        await create_db_and_tables()
    yield


app = FastAPI(title="Submissions Service", lifespan=lifespan)
add_cors(app, settings.cors_origins)

# This service's admin session lives in its own cookie ("submissions_session")
# rather than starlette's default "session": on localhost every service shares
# the host's cookie jar, so the default name would collide with the Auth
# panel's session and logging into one panel would log you out of the other.
SESSION_COOKIE = "submissions_session"

# Same secret and cookie as sqladmin's own SessionMiddleware on the /admin
# sub-app (below). This lets main-app routes — the photo endpoint — recognize
# a logged-in admin, so <img> previews inside the admin panel are authorized
# (see security.current_user_any_channel).
app.add_middleware(
    SessionMiddleware, secret_key=settings.secret, session_cookie=SESSION_COOKIE
)

# Register API/web routes BEFORE mounting the admin panel: sqladmin mounts at
# "/admin", which would otherwise shadow the JSON "GET /admin/submissions"
# endpoint (Starlette matches routes in registration order).
app.include_router(routers.router)
app.include_router(web.router)
app.include_router(health_router(service="submissions", readiness_check=ping))

class DashboardAdmin(Admin):
    async def index(self, request: Request) -> RedirectResponse:
        # Land on the submissions list instead of the default empty dashboard
        # (also where the login form redirects after success).
        return RedirectResponse(request.url_for("admin:list", identity="submission"))


# Admin panel over submissions (HTML), gated by a superuser JWT from Auth.
admin = DashboardAdmin(
    app,
    engine,
    authentication_backend=admin_mod.AdminAuth(
        secret_key=settings.secret, session_cookie=SESSION_COOKIE
    ),
)
admin.add_view(admin_mod.SubmissionAdmin)
