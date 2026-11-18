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

    llm_provider: str = "nvidia_nim"
    llm_model: str = "mistralai/mistral-large-4-1t-a52b"
    llm_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 120

    # RAG embeddings. "hashing" is offline/deterministic (no key); switch to
    # "openai_compatible" (NVIDIA NIM, OpenAI, local server) for real semantic search.
    # EMBEDDING_DIMENSION must match the pgvector column in migrations/001_knowledge_base.sql.
    embedding_provider: str = "hashing"
    embedding_model: str = "nvidia/nv-embed-v1"
    embedding_base_url: str = "https://integrate.api.nvidia.com/v1"
    embedding_api_key: str = ""
    embedding_dimension: int = 1024
    embedding_timeout_seconds: int = 30

    # RAG retrieval
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.55

    # Complaint conversation
    complaint_max_turns: int = 6
    complaint_min_confidence: float = 0.55
    knowledge_dir: str = "data/knowledge"

    # Browser origins allowed to call the API (comma-separated). Used by CORS middleware.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Duplicate complaint detection (Jaccard/overlap mix over normalized Arabic tokens).
    duplicate_similarity_threshold: float = 0.45

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins or "http://localhost:5173,http://127.0.0.1:5173"
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

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
