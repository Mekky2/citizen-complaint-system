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

    # --- LLM gateway (resilience) -------------------------------------------
    # Comma-separated extra keys for the primary provider. LLM_API_KEY is still honoured, so
    # an existing .env keeps working. Rotation happens on 401/403/429/quota errors.
    llm_api_keys: str = ""

    # Optional secondary OpenAI-compatible provider (for example another NIM endpoint).
    # Leave the keys empty to disable it.
    llm_secondary_name: str = "secondary"
    llm_secondary_model: str = ""
    llm_secondary_base_url: str = ""
    llm_secondary_api_keys: str = ""
    llm_secondary_timeout_seconds: float = 60.0

    llm_max_tokens: int = 1024
    llm_max_input_tokens: int = 6000
    # Hard cap on a single provider call (never longer than LLM_TIMEOUT_SECONDS).
    llm_max_call_seconds: float = 30.0
    llm_max_attempts: int = 3
    llm_backoff_base_seconds: float = 0.25
    llm_backoff_max_seconds: float = 3.0
    llm_retry_after_default_seconds: float = 5.0

    # Circuit breaker per provider key.
    llm_circuit_failure_threshold: int = 3
    llm_circuit_open_seconds: float = 30.0
    llm_auth_cooldown_seconds: float = 300.0

    # Offline fallback is always available; this switch only exists for emergency disabling.
    llm_offline_fallback: bool = True

    # Token / request budgets. Counts are estimates (characters/3, closer for Arabic) so no
    # tokenizer is required.
    llm_global_daily_token_budget: int = 2_000_000
    llm_user_daily_token_budget: int = 50_000
    llm_global_daily_request_budget: int = 20_000
    llm_user_daily_request_budget: int = 500

    # Concurrency: simultaneous provider calls and how long a caller waits for a slot.
    llm_max_concurrent_calls: int = 8
    llm_queue_timeout_seconds: float = 5.0

    # --- Answer cache / sessions / API load ---------------------------------
    rag_cache_ttl_seconds: int = 300
    rag_cache_max_entries: int = 500

    session_ttl_seconds: int = 1800
    session_max_entries: int = 5000
    session_max_history_messages: int = 40

    api_max_concurrent_requests: int = 32
    api_queue_timeout_seconds: float = 10.0
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 20

    # Citizen uploads
    upload_max_files: int = 5
    upload_max_mb: int = 5
    upload_allowed_types: str = "image/jpeg,image/png"


@lru_cache
def get_settings() -> Settings:
    return Settings()
