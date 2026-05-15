from functools import lru_cache

from pydantic import Field, model_validator
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

    @model_validator(mode="after")
    def _validate_cors_origins_prod(self) -> "Settings":
        """F5.9a: em produção, recusa `*` como origem CORS.

        `*` em produção combinado com `allow_credentials=True` é vetor de
        CSRF/cookie leak. Setting fail-fast aqui evita um deploy silencioso
        com a porta aberta. Em dev/staging, `*` permanece aceito para
        ergonomia local.
        """
        if self.environment == "prod":
            origins = [o.strip() for o in self.cors_origins.split(",")]
            if any(o == "*" for o in origins):
                raise ValueError(
                    "CORS_ORIGINS=* não é permitido em ENVIRONMENT=prod. "
                    "Configure a URL exata do frontend (ex.: "
                    "https://app.example.com)."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
