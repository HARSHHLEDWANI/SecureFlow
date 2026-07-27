"""Application configuration loaded from environment variables.

All settings are validated through ``pydantic-settings``. A single cached
``Settings`` instance is exposed via :func:`get_settings`.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "SecureFlow"
    environment: str = "development"
    log_level: str = "INFO"
    api_port: int = 8000
    # Comma-separated string in the environment; exposed as a list via the property.
    cors_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "sqlite:///./data/secureflow.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security / JWT
    jwt_secret: str = "change_me_in_production"
    jwt_refresh_secret: str = "change_me_too_in_production"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ML
    model_path: str = "./data/fraud_model.joblib"
    model_metrics_path: str = "./data/model_metrics.json"

    # Blockchain
    blockchain_path: str = "./data/chain.json"
    blockchain_difficulty: int = 2
    # Where the audit chain is persisted: "file" (local JSON, dev/tests) or "db"
    # (a chain_blocks table in the persistent database — used in production so the
    # immutable audit trail survives redeploys on ephemeral hosting).
    blockchain_storage: str = "file"

    # Rate limiting
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Governance integrity watchdog (auto-detect + self-heal tampering)
    integrity_watchdog_enabled: bool = True
    integrity_watchdog_interval_seconds: int = 15

    # "Explain This Decision" (Feature A) — the one feature with an external cost.
    # If ``anthropic_api_key`` is empty the endpoint transparently falls back to a
    # deterministic template, so the app works with zero configuration.
    anthropic_api_key: str = ""
    explain_model: str = "claude-haiku-4-5"  # small/fast/cheap; short structured completion
    explain_timeout_seconds: float = 5.0
    explain_max_tokens: int = 220
    explain_cache_ttl_seconds: int = 86400   # cache per-txn so repeat clicks don't re-spend
    explain_rate_limit_requests: int = 10    # tighter than the general limiter (costs money)

    # Governance → model feedback loop (Feature B).
    feedback_model_dir: str = "./data/models"          # versioned candidate models live here
    feedback_min_examples: int = 1                      # min corrections to allow a retrain
    feedback_correction_weight: float = 5.0            # weight of real corrections vs synthetic
    feedback_regression_auc_drop: float = 0.03        # block promotion if AUC drops beyond this
    feedback_regression_recall_drop: float = 0.05     # ...or recall drops beyond this
    feedback_retrain_fast: bool = False               # skip grid search on retrain (tests set True)

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS origins parsed from the comma-separated configuration string."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
