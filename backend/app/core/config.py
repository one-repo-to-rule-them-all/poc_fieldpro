"""Application configuration via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
import json
from typing import Any

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_TITLE: str = "FieldPro API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://fieldpro:fieldpro_secret@localhost:5432/fieldpro"
    DATABASE_TEST_URL: str = "postgresql+asyncpg://fieldpro:fieldpro_secret@localhost:5432/fieldpro_test"

    # SQLAlchemy pool settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_PRE_PING: bool = True

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    ARQ_REDIS_URL: str = "redis://localhost:6379/1"  # Separate DB from main cache

    # --- JWT ---
    SECRET_KEY: str = "insecure-dev-secret-change-me"
    REFRESH_SECRET_KEY: str = "insecure-dev-refresh-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 1
    ALGORITHM: str = "HS256"

    # --- Trusted hosts ---
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"

    # --- CORS ---
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(origin).rstrip("/") for origin in parsed]
            except json.JSONDecodeError:
                # Comma-separated fallback
                return [origin.strip().rstrip("/") for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(origin).rstrip("/") for origin in v]
        raise ValueError(f"Cannot parse BACKEND_CORS_ORIGINS: {v!r}")

    # --- Superadmin seed ---
    FIRST_SUPERADMIN_EMAIL: str = "admin@fieldpro.dev"
    FIRST_SUPERADMIN_PASSWORD: str = "ChangeMe123!"

    # --- Analytics ---
    ANALYTICS_DEFAULT_LOOKBACK_DAYS: int = 30
    CREW_PRODUCTIVITY_DEFAULT_LOOKBACK_DAYS: int = 7

    # --- S3 ---
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 900  # 15 minutes

    # --- Background workers (ARQ) ---
    ARQ_JOB_TIMEOUT_SECONDS: int = 300   # 5 minutes
    ARQ_KEEP_RESULT_SECONDS: int = 3600  # 1 hour
    ARQ_MAX_TRIES: int = 3

    # --- Redis ---
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 2

    # --- AWS / S3 ---
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_REGION: str = "us-east-1"
    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = ""
    R2_ENDPOINT_URL: str = ""

    # --- Email ---
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = False   # Set True for port 587 (STARTTLS). False for MailHog/port 1025.
    EMAILS_FROM_EMAIL: str = "noreply@fieldpro.dev"
    EMAILS_FROM_NAME: str = "FieldPro"
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Twilio ---
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # --- Sentry ---
    SENTRY_DSN: str = ""

    # NOTE: mypy reports `[prop-decorator]` for `@computed_field` stacked on
    # `@property` — this is the documented Pydantic v2 pattern and a known
    # gap in mypy's pydantic plugin. Suppressed per-decorator below.

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def s3_endpoint_url(self) -> str | None:
        """Return R2 endpoint if configured, else None (uses standard AWS)."""
        return self.R2_ENDPOINT_URL or None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_s3_bucket(self) -> str:
        return self.R2_BUCKET or self.AWS_S3_BUCKET

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_aws_access_key(self) -> str:
        return self.R2_ACCESS_KEY_ID or self.AWS_ACCESS_KEY_ID

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_aws_secret_key(self) -> str:
        return self.R2_SECRET_ACCESS_KEY or self.AWS_SECRET_ACCESS_KEY


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
