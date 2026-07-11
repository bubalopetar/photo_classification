from shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    # Async SQLAlchemy URL. Defaults to a local SQLite file so the service runs
    # with zero infrastructure during development; docker-compose / Kubernetes
    # override it with the Postgres URL (postgresql+asyncpg://...).
    database_url: str = "sqlite+aiosqlite:///./auth.db"

    # Set True behind HTTPS in production so the auth cookie is only sent over
    # TLS. False for local http development.
    cookie_secure: bool = False

    # If both are set, a superuser with these credentials is created/promoted on
    # startup — convenient for demos and first-run bootstrap. Leave unset in
    # environments where the admin is provisioned another way.
    admin_email: str | None = None
    admin_password: str | None = None

    # Per-IP budgets per rate_limit_window_seconds (shared config). Login is
    # the brute-force target; register is throttled harder against bulk
    # account creation.
    login_rate_limit: int = 10
    register_rate_limit: int = 5


settings = Settings()
