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

    # Rate limiting
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Governance integrity watchdog (auto-detect + self-heal tampering)
    integrity_watchdog_enabled: bool = True
    integrity_watchdog_interval_seconds: int = 15

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
