"""Application settings, loaded from the environment / .env (see .env.example).

Single source of truth for every connection string and tunable the rest of the
app reads. Nothing here reads config/datasets.yaml — that stays the research
pipeline's own config, resolved via ``common.config`` (see src/common/config.py).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = Field(default="development", alias="ENV")

    # --- Postgres ---
    database_url: str = Field(
        default="postgresql+asyncpg://ledger:ledger_dev_password@localhost:5432/shadow_ledger",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://ledger:ledger_dev_password@localhost:5432/shadow_ledger",
        alias="DATABASE_URL_SYNC",
    )
    db_pool_size: int = 20
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 10

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    cache_default_ttl_seconds: int = 60
    idempotency_key_ttl_seconds: int = 86400

    # --- Neo4j (optional) ---
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")

    # --- Auth ---
    secret_key: str = Field(default="dev-only-change-me", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_algorithm: str = "HS256"

    # --- CORS ---
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    # --- Observability ---
    glitchtip_dsn: str | None = Field(default=None, alias="GLITCHTIP_DSN")
    prometheus_enabled: bool = Field(default=True, alias="PROMETHEUS_ENABLED")

    # --- Fraud engine ---
    scoring_timeout_ms: int = Field(default=500, alias="SCORING_TIMEOUT_MS")
    scoring_circuit_breaker_failure_threshold: int = Field(
        default=5, alias="SCORING_CIRCUIT_BREAKER_FAILURE_THRESHOLD"
    )
    scoring_circuit_breaker_reset_seconds: int = Field(
        default=30, alias="SCORING_CIRCUIT_BREAKER_RESET_SECONDS"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
