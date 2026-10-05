"""Application configuration loaded from environment variables.

All settings are validated through ``pydantic-settings``. A single cached
``Settings`` instance is exposed via :func:`get_settings`.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

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
    # Frozen evaluation/training pools written at training time. Every candidate and
    # the live model are scored on the same ``holdout`` rows (see ml/feedback.py).
    holdout_path: str = "./data/holdout.parquet"
    train_pool_path: str = "./data/train_pool.parquet"
    # Benchmark (PaySim) run artifacts - kept apart from the live demo model.
    benchmark_model_path: str = "./data/benchmark_model.joblib"
    benchmark_metrics_path: str = "./data/benchmark_metrics.json"
    # PaySim benchmark CSV (never downloaded by the code - see ml/datasets/paysim.py).
    paysim_path: str = ""
    paysim_max_rows: int = 0            # 0 = all rows; N = first N rows in step order
    # Training-set negative:positive cap. Only the TRAIN split is undersampled;
    # validation/test keep the true base rate. Calibration is fitted on the untouched
    # validation split, which corrects the probability shift this introduces.
    train_negative_ratio: int = 50
    # Risk-tier cutoffs. Precedence: explicit RISK_LOW_MAX/RISK_MEDIUM_MAX, then the
    # cost-optimal pair in the live model's metrics if USE_LEARNED_THRESHOLDS=true, then
    # the legacy 30/70. Learned cutoffs are tied to the model they were tuned on, and the
    # demo model's are tuned at a 13% fraud rate, so they are opt-in.
    risk_low_max: Optional[int] = None
    risk_medium_max: Optional[int] = None
    use_learned_thresholds: bool = False
    # Cost matrix for threshold selection (ml/thresholds.py).
    cost_false_positive: float = 1.0      # blocking a legitimate payment
    cost_false_negative: float = 50.0     # allowing a fraudulent payment (1:50)
    cost_stepup_legit: float = 0.1        # OTP friction on a legitimate payment
    stepup_fraud_leak: float = 0.2        # share of step-up frauds that still get through

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
    # If ``groq_api_key`` is empty the endpoint transparently falls back to a
    # deterministic template, so the app works with zero configuration.
    groq_api_key: str = ""
    explain_model: str = "llama-3.1-8b-instant"  # small/fast/cheap; short structured completion
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
    feedback_regression_prauc_drop: float = 0.03      # PR-AUC is the headline metric (AUC-ROC kept too)
    # Corrections are floored to this share of total sample mass (see ml/feedback.py);
    # ``feedback_correction_weight`` is the minimum per-correction weight.
    feedback_correction_target_share: float = 0.05
    feedback_max_correction_weight: float = 500.0

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
