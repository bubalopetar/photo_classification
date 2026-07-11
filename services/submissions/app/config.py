from shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    # Owns its own database (database-per-service). Defaults to SQLite so the
    # service runs with no infrastructure in development; compose/K8s override
    # with Postgres.
    database_url: str = "sqlite+aiosqlite:///./submissions.db"

    # Internal URLs used for service-to-service calls (inside the cluster).
    classification_url: str = "http://localhost:8003"
    auth_url: str = "http://localhost:8001"
    # Public URL of Auth, used to redirect un-authenticated browsers to /login.
    auth_public_url: str = "http://localhost:8001"

    # Photo storage directory (a mounted volume in Docker). See app/storage.py
    # for the Storage protocol a cloud backend would plug into.
    storage_local_dir: str = "./uploads"

    # Per-IP uploads per rate_limit_window_seconds (shared config). Uploads
    # fan out into classification + storage, so they're the costliest request
    # this service serves.
    upload_rate_limit: int = 20

    # Upload safety limits (see app/safety.py).
    max_upload_bytes: int = 10 * 1024 * 1024
    max_image_dimension: int = 5000
    allowed_image_types: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")


settings = Settings()
