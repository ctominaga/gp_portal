from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Jump GP Portal"
    app_version: str = "0.1.0"
    environment: str = Field(default="dev")

    database_url: str = Field(default="postgresql+asyncpg://jump:jump@db:5432/jump_report")
    redis_url: str = Field(default="redis://redis:6379/0")

    jwt_secret: str = Field(default="change-me-in-prod")
    jwt_algorithm: str = "HS256"
    jwt_expires_hours: int = 8

    worker_shared_secret: str = Field(default="change-me-worker-token")
    worker_hmac_key: str = Field(default="change-me-worker-hmac")

    r2_account_id: str = Field(default="")
    r2_access_key: str = Field(default="")
    r2_secret_key: str = Field(default="")
    r2_bucket: str = Field(default="jump-report-proposals")
    r2_endpoint_url: str = Field(default="")

    resend_api_key: str = Field(default="")
    resend_from_email: str = Field(default="christopher.tominaga@jumplabel.com.br")

    sentry_dsn: str = Field(default="")
    cors_origins: str = Field(default="http://localhost:3000")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
