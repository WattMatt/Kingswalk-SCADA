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
    environment: str = "development"
    log_level: str = "info"
    cors_origins: list[str] = ["http://localhost:5173"]
    version: str = "0.1.0"


settings = Settings()  # type: ignore[call-arg]
