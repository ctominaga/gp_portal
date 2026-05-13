"""Cliente HTTP do worker para callbacks autenticados ao backend.

Reusa `httpx.AsyncClient` durante toda a vida do worker. `post_signed`:
1. serializa o payload canonicamente,
2. monta os 3 headers HMAC,
3. envia com `content=body` (bytes idênticos aos assinados),
4. faz retry com backoff exponencial em erros transitórios.

**Política de retry:**
- 5xx ou 408 (request timeout) → retry com backoff exponencial até 3x.
- Erros de rede (ConnectError, ReadTimeout, WriteTimeout) → idem.
- 4xx (exceto 408) → falha definitiva, sem retry (provável erro de auth/payload).
"""
from __future__ import annotations

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import get_settings
from .hmac_signer import build_auth_headers, serialize_body

log = structlog.get_logger("worker.http")


class RetryableHttpError(Exception):
    """Erro que justifica retry (5xx, 408, falha de rede)."""


class WorkerHttpClient:
    """Cliente assinado para o backend. Instância única por processo."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        secret: str | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = base_url or settings.backend_url
        self._token = token or settings.worker_shared_secret
        self._secret = secret or settings.worker_hmac_key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=settings.callback_timeout_s,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def post_signed(self, path: str, payload: dict) -> httpx.Response:
        """POST com HMAC + Bearer. Retorna response 2xx ou levanta após esgotar retry."""

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(RetryableHttpError),
            reraise=True,
        )
        async def _do() -> httpx.Response:
            body = serialize_body(payload)
            headers = build_auth_headers(body, token=self._token, secret=self._secret)
            try:
                resp = await self._client.post(path, content=body, headers=headers)
            except (
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.RemoteProtocolError,
            ) as exc:
                log.warning("post_signed.network_error", path=path, exc=str(exc))
                raise RetryableHttpError(str(exc)) from exc

            if resp.status_code >= 500 or resp.status_code == 408:
                log.warning(
                    "post_signed.transient_status",
                    path=path,
                    status=resp.status_code,
                )
                raise RetryableHttpError(f"HTTP {resp.status_code}")

            if resp.status_code >= 400:
                # 4xx (exceto 408): erro definitivo do cliente, sem retry
                log.error(
                    "post_signed.client_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:300],
                )
                resp.raise_for_status()

            return resp

        return await _do()
