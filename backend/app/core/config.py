"""Central configuration (plan task 0.5). All tunable values come from env vars."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"

    # Supabase Postgres via the session pooler (set in backend/.env, never committed)
    database_url: str = ""

    # File storage: "local" until task 0.3 switches it to Supabase Storage
    storage_backend: str = "local"
    storage_local_path: str = "./data/uploads"

    llm_api_key: str = ""

    # Tool-call limiting (docs/system_architecture.md)
    tool_call_limit_per_ticket: int = 8
    tool_call_limit_per_tool: int = 3
    tool_timeout_seconds: int = 15
    ticket_timeout_seconds: int = 60
    tool_retry_max: int = 2

    # Citizen uploads
    upload_max_files: int = 5
    upload_max_mb: int = 5
    upload_allowed_types: str = "image/jpeg,image/png"


@lru_cache
def get_settings() -> Settings:
    return Settings()
