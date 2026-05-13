"""Settings do processo jump-worker — lê de .env via Pydantic Settings.

Espelha o subset de variáveis do .env compartilhado com o backend
(WORKER_SHARED_SECRET e WORKER_HMAC_KEY precisam ser idênticos nos dois
lados para o HMAC do callback bater).
"""
from __future__ import annotations

import socket
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_workspace_root() -> Path:
    return Path.home() / ".jump-runner" / "jobs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    redis_url: str = "redis://localhost:6379/0"
    backend_url: str = "http://localhost:8000"
    worker_shared_secret: str
    worker_hmac_key: str
    worker_id: str = Field(default_factory=socket.gethostname)
    workspace_root: Path = Field(default_factory=_default_workspace_root)
    heartbeat_s: int = 30
    brpop_timeout_s: int = 30
    callback_timeout_s: float = 15.0


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_cache() -> None:
    """Hook para testes — invalida o cache do singleton."""
    global _settings
    _settings = None
