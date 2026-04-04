"""Application configuration via environment variables.

Uses pydantic-settings to load config from .env files and environment
variables. All settings have sensible defaults for local development.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API keys
    finnhub_api_key: str = ""
    resend_api_key: str = ""

    # Alert settings
    alert_email_to: str = ""
    alert_email_from: str = "screener@option-screener.dev"
    dashboard_url: str = "http://localhost:3000"

    # Database
    db_path: str = "data/screener.db"

    # Screening parameters
    max_trades: int = 15
    scan_cache_ttl_seconds: int = 3600  # 1 hour

    # Universe source
    use_fallback_symbols: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
