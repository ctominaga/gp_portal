"""Interface ObjectStorage — implementada por LocalStorage e R2Storage."""
from __future__ import annotations

from abc import ABC, abstractmethod


class StorageError(RuntimeError):
    """Erro genérico de operação de storage."""


class ObjectStorage(ABC):
    """Contrato comum a todos os backends de storage de arquivos."""

    @abstractmethod
    def put(
        self,
        content: bytes,
        key: str,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Grava `content` no key. Retorna o key efetivo gravado.

        Levanta StorageError em falha.
        """

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Lê `key`. Levanta StorageError(detail='not_found') quando não existe."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove `key`. Idempotente — não levanta se não existir."""

    @abstractmethod
    def get_signed_url(self, key: str, *, ttl_seconds: int = 300) -> str:
        """URL temporária para download. TTL em segundos."""
