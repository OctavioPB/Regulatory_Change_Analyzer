import logging
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://rca_user:rca_pass@localhost:5432/regulatory_db"
    database_url_sync: str = "postgresql://rca_user:rca_pass@localhost:5432/regulatory_db"

    # LLM
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"

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
