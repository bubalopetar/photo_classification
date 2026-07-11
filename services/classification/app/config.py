from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """The classification service is stateless and trust-boundary-internal: it
    is only reachable from other services inside the cluster, so it needs no JWT
    secret or database of its own.
    """

    log_level: str = "INFO"
    # Reject payloads larger than this many bytes before decoding.
    max_image_bytes: int = 10 * 1024 * 1024

    # EfficientNet-Lite0 weights — downloaded at Docker build time, or via the
    # curl command in the README for a bare-python run.
    model_path: str = "models/efficientnet_lite0.tflite"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
