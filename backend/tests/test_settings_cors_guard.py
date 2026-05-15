"""F5.9a — Settings recusa CORS_ORIGINS=`*` em ENVIRONMENT=prod.

Guard em `app/core/config.py` (model_validator after-mode). Em
dev/staging permanece permissivo para ergonomia local.
"""
from __future__ import annotations

import pytest

from app.core.config import Settings


def test_cors_estrela_aceito_em_dev() -> None:
    s = Settings(environment="dev", cors_origins="*")
    assert "*" in s.cors_origins_list


def test_cors_estrela_aceito_em_staging() -> None:
    s = Settings(environment="staging", cors_origins="*")
    assert s.cors_origins_list == ["*"]


def test_cors_estrela_rejeitado_em_prod() -> None:
    with pytest.raises(ValueError, match="CORS_ORIGINS=\\* não é permitido"):
        Settings(environment="prod", cors_origins="*")


def test_cors_estrela_misturado_em_prod_tambem_rejeita() -> None:
    """Mesmo com outras origens válidas na mesma string, `*` precisa
    falhar — caso contrário um typo (`https://app,*`) passaria."""
    with pytest.raises(ValueError, match="CORS_ORIGINS=\\* não é permitido"):
        Settings(
            environment="prod",
            cors_origins="https://app.jumplabel.com.br,*",
        )


def test_cors_url_explicita_aceita_em_prod() -> None:
    s = Settings(
        environment="prod",
        cors_origins="https://app.jumplabel.com.br,https://staging.jumplabel.com.br",
    )
    assert s.cors_origins_list == [
        "https://app.jumplabel.com.br",
        "https://staging.jumplabel.com.br",
    ]
