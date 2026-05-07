"""Política de fallback entre rotas e providers.

Spec: 02_jump_agent_runner_spec.md, seção 9.
"""
from __future__ import annotations

from .types import FailureReason

# Razões que disparam fallback DENTRO do mesmo provider (headless → broker)
HEADLESS_TO_BROKER_REASONS: frozenset[FailureReason] = frozenset(
    {
        FailureReason.LOGIN_REQUIRED,
        FailureReason.INTERACTIVE_MODE_DETECTED,
        FailureReason.TIMEOUT_NO_ARTIFACT,
        FailureReason.EXECUTION_ERROR,
    }
)

# Razões que disparam fallback ENTRE providers (engine A → engine B)
PROVIDER_TO_PROVIDER_REASONS: frozenset[FailureReason] = frozenset(
    {
        FailureReason.QUOTA_EXCEEDED,
        FailureReason.LOGIN_REQUIRED,  # se broker tb não conseguir
        FailureReason.SENTINEL_NOT_OBSERVED,
        FailureReason.ARTIFACT_INVALID,
        FailureReason.BROKER_UNAVAILABLE,
    }
)
