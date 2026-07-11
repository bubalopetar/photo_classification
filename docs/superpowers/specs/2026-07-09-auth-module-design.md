# Auth as a self-contained module (`app/auth/`)

Date: 2026-07-09

## Context

The app is a FastAPI monolith (fastapi-users JWT + cookie auth, sqladmin admin,
server-rendered login/register/logout screens). Auth code was spread across
top-level `app/` modules (`users.py`, `schemas.py`, `admin.py`, `web.py`) tangled
with the app shell. Goal: reorganize authentication into a **self-contained
package with a clean public interface** — a modular monolith. One process, one
database, no network boundaries. Purely structural; behavior is unchanged.

Decisions (user-approved): internal module boundary (not a separate service) ·
fine-grained file split · homepage `/` belongs to the shell · templating is
shared infrastructure.

## Target structure

```
app/
  app.py          # SHELL: FastAPI app, lifespan, DashboardAdmin, wires auth, homepage
  config.py       # shared Settings (SECRET) — unchanged
  db.py           # shared infra: engine, Base, session, create_db_and_tables (User REMOVED)
  templating.py   # NEW shared: one Jinja2Templates over [templates/, app/auth/templates/]
  auth/
    __init__.py   # PUBLIC INTERFACE (only thing the shell imports from auth)
    models.py     # User(SQLAlchemyBaseUserTableUUID, Base)
    schemas.py    # UserRead / UserCreate / UserUpdate
    manager.py    # UserManager, get_user_db, get_user_manager
    backends.py   # transports, JWT strategy, both backends, fastapi_users, current/optional deps
    routers.py    # include_api_routers(app)
    web.py        # APIRouter: login/register/logout screens
    admin.py      # AdminAuth, UserAdmin, password_helper
    templates/    # login.html, register.html
templates/        # base.html, home.html
create_superuser.py  # imports updated to app.auth
```

## Public interface — `app/auth/__init__.py`

`User`, `current_active_user`, `optional_current_user`, `web_router`,
`include_api_routers(app)`, `AdminAuth`, `UserAdmin`, `password_helper`.

## Boundary rules

- Dependencies flow one way: `auth` → shared infra (`db`, `config`,
  `templating`). `auth` never imports the shell; the shell touches `auth` only
  via `__init__.py`.
- No import cycles: `db.py` has no auth imports; `User` registers on
  `Base.metadata` simply by being imported (the shell's `from app import auth`
  and `create_superuser`'s `from app.auth import User` both trigger this before
  `create_db_and_tables` runs).
- Homepage `/` lives in the shell and consumes `auth.optional_current_user`.
  Only login/register/logout stay in `auth/web.py`.

## Templates

`app/templating.py` exposes one `Jinja2Templates(directory=[templates/,
app/auth/templates/])` (starlette 1.3.1 passes a sequence to
`FileSystemLoader`, verified). Auth screens keep extending the shared
`base.html`. Both shell and auth import this shared `templates`.

## Non-goals / unchanged

Same routes, URLs, cookie/JWT behavior, admin. No new dependencies. `config.py`
stays shared. This is not a git repo, so the doc is written but not committed.

## Verification

`python -c "from app.app import app"` imports clean; route count unchanged (12).
Re-run the full curl suite (unauth `/`→303 /login; register→303 + cookie; auth
`/`→200 w/ email; bad login→400; logout→303 + cleared cookie; bearer
`/auth/jwt/login`→token→`/authenticated-route`→200). Confirm
`create_superuser.py` still creates/promotes a superuser. Clean up test users.
