from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://scada:scada_dev@localhost:5432/kingswalk_scada"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str
    jwt_issuer: str = "kingswalk-scada"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 604800
    csrf_secret: str
    # MFA secret encryption key — base64-encoded 32 bytes
    # Generate: python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"  # noqa: E501
    mfa_encryption_key: str
    environment: str = "development"
    log_level: str = "info"
    cors_origins: list[str] = ["http://localhost:5173"]
    resend_api_key: str = ""  # Empty = skip email sending (dev mode)
    app_url: str = "http://localhost:5173"
    version: str = "0.1.0"


settings = Settings()  # type: ignore[call-arg]
