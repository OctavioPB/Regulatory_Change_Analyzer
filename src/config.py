import logging
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://rca_user:rca_pass@localhost:5432/regulatory_db"
    database_url_sync: str = "postgresql://rca_user:rca_pass@localhost:5432/regulatory_db"

    # LLM — "anthropic" (Claude API) or "ollama" (local models such as Qwen / Gemma)
    llm_provider: Literal["anthropic", "ollama"] = "anthropic"
    anthropic_api_key: str = ""
    # Claude model id, or an Ollama tag (e.g. "qwen3:4b-instruct-2507-q4_K_M") when provider is ollama
    llm_model: str = "claude-opus-5-5"
    ollama_url: str = "http://localhost:11434"
    ollama_num_ctx: int = 32768       # Ollama defaults to 4096, too small for agent transcripts
    ollama_timeout_s: float = 900.0   # large local models can be slow on partial GPU offload

    @property
    def llm_enabled(self) -> bool:
        """Whether LLM features run for real (else they use their no-LLM fallbacks)."""
        return self.llm_provider == "ollama" or bool(self.anthropic_api_key)

    # Storage
    data_dir: Path = Path("./data")
    raw_dir: Path = Path("./data/raw")
    processed_dir: Path = Path("./data/processed")
    contracts_dir: Path = Path("./data/contracts")
    cache_dir: Path = Path("./data/cache")

    # Task queue
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    # Scraping
    scrape_interval_hours: int = 24

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-this-in-production"
    # SQL echo is very noisy and slows every request — opt-in only
    db_echo: bool = False
    # Comma-separated list of allowed CORS origins ("*" = any, without credentials)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Max upload size for contract files (bytes)
    max_upload_bytes: int = 20 * 1024 * 1024

    # RBAC — JSON map of {"api-key": "role"}, empty = dev mode (admin)
    api_keys: str = "{}"

    # Task manager integration
    jira_base_url: str = ""          # e.g. https://yourorg.atlassian.net
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "COMP"
    asana_access_token: str = ""
    asana_project_gid: str = ""
    task_manager: str = "none"       # "jira" | "asana" | "none"

    # Rate limiting (requests per minute per IP on ingest endpoints)
    ingest_rate_limit: int = 10

    @field_validator("data_dir", "raw_dir", "processed_dir", "contracts_dir", "cache_dir", mode="after")
    @classmethod
    def ensure_dir_exists(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v


settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)
