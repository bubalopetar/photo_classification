from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Settings common to every service.

    Each service subclasses this and adds its own fields. All values are read
    from environment variables (or a local .env during development), never
    hard-coded — see the `secret` note below.
    """

    # Signs and verifies JWTs across ALL services. Because every service shares
    # this one secret, each can validate a token issued by Auth locally, with no
    # network call back to Auth. MUST be a long random value in production and
    # supplied only via a secret store / env var — never committed.
    secret: str

    # fastapi-users' default audience. Kept here so the issuer (Auth) and every
    # verifier (Submissions, ...) agree on it.
    jwt_audience: str = "fastapi-users:auth"

    # Access-token lifetime; also the auth cookie max-age.
    jwt_lifetime_seconds: int = 3600

    # Name of the browser auth cookie. Cookies are scoped by host (not port), so
    # a cookie set by Auth on localhost is also sent to the other services during
    # local development.
    auth_cookie_name: str = "photoauth"

    # Rate limiting (see shared/ratelimit.py). The window is shared config;
    # each service defines its own per-endpoint budgets. The kill switch
    # exists for load tests and local debugging.
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60

    # Comma-separated origins allowed to call this service from a browser
    # (see shared/cors.py). Empty — the default — means deny all cross-origin
    # access: the server-rendered UI is same-origin and needs nothing.
    cors_allow_origins: str = ""

    log_level: str = "INFO"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
