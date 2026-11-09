"""
Centralized application settings, loaded from environment variables / .env.

Everything the app needs to know that varies by environment lives here and
nowhere else — no module reaches into os.environ directly.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database — must point at the existing egcivic database (see README).
    database_url: str = Field(alias="DATABASE_URL")

    # JWT
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(default=10080, alias="REFRESH_TOKEN_EXPIRE_MINUTES")

    # AI service integration
    ai_service_url: str = Field(default="http://localhost:9000", alias="AI_SERVICE_URL")
    ai_service_timeout_seconds: int = Field(default=30, alias="AI_SERVICE_TIMEOUT_SECONDS")
    ai_service_shared_secret: str = Field(default="change-me-too", alias="AI_SERVICE_SHARED_SECRET")

    # App
    environment: str = Field(default="development", alias="ENVIRONMENT")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Settings are read once and cached — call get_settings() anywhere that needs them."""
    return Settings()
