"""Async HTTP client utilities for high-throughput API calls."""

from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, List, Optional, Union

import httpx
from asyncio_throttle import Throttler

from vnstock.core.utils.client import ProxyMode
from vnstock.core.utils.logger import get_logger

logger = get_logger(__name__)

# Backend-safe ceiling requested by user: 600 requests per minute.
REQUESTS_PER_MINUTE = 600
DEFAULT_MAX_CONNECTIONS = 200
DEFAULT_MAX_KEEPALIVE = 100
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 0.3

RATE_LIMITER = Throttler(rate_limit=REQUESTS_PER_MINUTE, period=60.0)


class AsyncClientManager:
    """Keep and reuse AsyncClient instances for direct/proxy traffic."""

    def __init__(
        self,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        max_keepalive_connections: int = DEFAULT_MAX_KEEPALIVE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._lock = asyncio.Lock()
        self._limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )
        self._timeout = timeout

    async def get_client(self, proxy_url: Optional[str] = None) -> httpx.AsyncClient:
        key = proxy_url or "__direct__"
        async with self._lock:
            if key not in self._clients:
                kwargs: Dict[str, Any] = {
                    "limits": self._limits,
                    "http2": True,
                    "timeout": self._timeout,
                }
                if proxy_url:
                    kwargs["proxy"] = proxy_url
                self._clients[key] = httpx.AsyncClient(**kwargs)
            return self._clients[key]

    async def close(self) -> None:
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            await client.aclose()


async_client_mgr = AsyncClientManager()


def _normalize_proxy_mode(proxy_mode: Union[str, ProxyMode]) -> str:
    if isinstance(proxy_mode, ProxyMode):
        return proxy_mode.value
    return str(proxy_mode).lower()


def _pick_proxy(
    proxy_list: Optional[List[str]],
    proxy_idx: int,
    proxy_mode: Union[str, ProxyMode],
) -> Optional[str]:
    if not proxy_list:
        return None

    mode = _normalize_proxy_mode(proxy_mode)
    if mode == ProxyMode.RANDOM.value:
        return random.choice(proxy_list)
    if mode in (ProxyMode.ROTATE.value, ProxyMode.TRY.value):
        return proxy_list[proxy_idx % len(proxy_list)]
    return proxy_list[0]


async def _send_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]],
    payload: Optional[Union[Dict[str, Any], str]],
    timeout: float,
    max_retries: int,
    retry_backoff_seconds: float,
) -> Any:
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            request_kwargs: Dict[str, Any] = {
                "headers": headers,
                "timeout": timeout,
            }
            if method == "GET":
                request_kwargs["params"] = params
            else:
                if isinstance(payload, dict):
                    request_kwargs["json"] = payload
                elif isinstance(payload, str):
                    request_kwargs["content"] = payload

            response = await client.request(method, url, **request_kwargs)

            # Retry transient responses (429 and 5xx) before raising.
            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()

            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            await asyncio.sleep(retry_backoff_seconds * (2 ** attempt))

    raise ConnectionError(f"Async API request failed after retries: {last_error}")


async def async_send_request(
    url: str,
    headers: Dict[str, str],
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    payload: Optional[Union[Dict[str, Any], str]] = None,
    proxy_idx: int = 0,
    proxy_list: Optional[List[str]] = None,
    proxy_mode: Union[str, ProxyMode] = ProxyMode.ROTATE,
    show_log: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> Any:
    """Async counterpart of send_request with global throttling and retries."""
    request_method = method.upper()
    selected_proxy = _pick_proxy(proxy_list, proxy_idx, proxy_mode)

    if show_log:
        logger.info(
            "Async %s %s proxy=%s idx=%s",
            request_method,
            url,
            selected_proxy or "direct",
            proxy_idx,
        )

    # Keep a call budget of <= 600 requests/min for backend stability.
    async with RATE_LIMITER:
        client = await async_client_mgr.get_client(selected_proxy)
        return await _send_with_retry(
            client=client,
            method=request_method,
            url=url,
            headers=headers,
            params=params,
            payload=payload,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )


async def fetch_multiple_requests(
    requests_list: List[Dict[str, Any]],
    max_concurrency: int = 24,
) -> List[Any]:
    """Run multiple async requests with bounded concurrency."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def bounded_send(idx: int, req: Dict[str, Any]) -> Any:
        async with semaphore:
            kwargs = dict(req)
            kwargs.setdefault("proxy_idx", idx)
            try:
                return await async_send_request(**kwargs)
            except Exception as exc:
                return {"error": str(exc)}

    tasks = [bounded_send(idx, req) for idx, req in enumerate(requests_list)]
    return await asyncio.gather(*tasks)


async def shutdown_async_clients() -> None:
    """Close all pooled async clients."""
    await async_client_mgr.close()


__all__ = [
    "async_send_request",
    "fetch_multiple_requests",
    "AsyncClientManager",
    "RATE_LIMITER",
    "REQUESTS_PER_MINUTE",
    "shutdown_async_clients",
]
