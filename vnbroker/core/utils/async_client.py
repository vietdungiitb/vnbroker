"""Async HTTP client utilities for high-throughput API calls."""

from __future__ import annotations

import asyncio
import os
import random
import threading
import time
import weakref
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlsplit

import httpx

from vnbroker.core.exceptions import RateLimitError
from vnbroker.core.utils.rate_limiter import get_provider_limiter

from vnbroker.config import Config
from vnbroker.core.utils.client import ProxyMode
from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_CONNECTIONS = 200
DEFAULT_MAX_KEEPALIVE = 100
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 0.3
ASYNC_STATS_ENABLED = os.getenv("vnbroker_ASYNC_STATS_ENABLED", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for async requests.
    
    Allows burst traffic up to bucket capacity while enforcing
    a sustained rate limit (requests per minute).
    """
    
    def __init__(self, rpm: int = 500):
        """
        Initialize rate limiter.

        Args:
            rpm: Requests per minute (0 = disabled)
        """
        self.rpm = rpm
        self._enabled = rpm > 0
        if self._enabled:
            # Token bucket: capacity = rpm, refill rate = rpm/60 per second
            self._capacity = rpm
            self._tokens = float(rpm)
            self._refill_rate = rpm / 60.0
            self._last_refill = time.monotonic()
        # Intentionally NO asyncio.Lock here. A lock created at import binds the
        # first running loop it is contended on (BL-1); every later loop then
        # fails with "is bound to a different event loop". Mutexes are created
        # per running loop on first use instead; token fields are guarded by a
        # plain threading lock that is never held across `await`.
        self._state_guard = threading.Lock()
        self._loop_locks: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, asyncio.Lock
        ] = weakref.WeakKeyDictionary()

    def _loop_lock(self) -> asyncio.Lock:
        """Return the mutex for the running loop, creating it on first use."""
        loop = asyncio.get_running_loop()
        with self._state_guard:
            lock = self._loop_locks.get(loop)
            if lock is None:
                lock = asyncio.Lock()
                self._loop_locks[loop] = lock
            return lock

    async def __aenter__(self) -> "TokenBucketRateLimiter":
        if not self._enabled:
            return self

        async with self._loop_lock():
            while True:
                with self._state_guard:
                    self._refill()
                    if self._tokens >= 1.0:
                        self._tokens -= 1.0
                        return self
                    # Calculate wait time for next token
                    wait_time = (1.0 - self._tokens) / self._refill_rate
                await asyncio.sleep(min(wait_time, 1.0))  # Cap at 1 second to re-check
        return self
    
    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now


# Initialize rate limiter from config (can be overridden by env var)
RATE_LIMITER = TokenBucketRateLimiter(Config.RATE_LIMIT_RPM)


@dataclass
class AsyncRequestStats:
    """Lightweight counters for async request diagnostics."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_attempts: int = 0
    retry_attempts: int = 0
    throttled_responses: int = 0
    server_error_responses: int = 0
    timeout_errors: int = 0
    transport_errors: int = 0
    other_errors: int = 0
    direct_requests: int = 0
    proxied_requests: int = 0
    status_counts: Dict[int, int] = field(default_factory=dict)
    last_error: str = ""


_stats_lock = threading.Lock()
_request_stats = AsyncRequestStats()


def reset_async_request_stats() -> None:
    """Reset collected async request counters."""
    global _request_stats
    with _stats_lock:
        _request_stats = AsyncRequestStats()


def get_async_request_stats() -> Dict[str, Any]:
    """Return a snapshot of collected async request counters."""
    with _stats_lock:
        return {
            "total_requests": _request_stats.total_requests,
            "successful_requests": _request_stats.successful_requests,
            "failed_requests": _request_stats.failed_requests,
            "total_attempts": _request_stats.total_attempts,
            "retry_attempts": _request_stats.retry_attempts,
            "throttled_responses": _request_stats.throttled_responses,
            "server_error_responses": _request_stats.server_error_responses,
            "timeout_errors": _request_stats.timeout_errors,
            "transport_errors": _request_stats.transport_errors,
            "other_errors": _request_stats.other_errors,
            "direct_requests": _request_stats.direct_requests,
            "proxied_requests": _request_stats.proxied_requests,
            "status_counts": dict(_request_stats.status_counts),
            "last_error": _request_stats.last_error,
        }


def _record_request_started(selected_proxy: Optional[str]) -> None:
    if not ASYNC_STATS_ENABLED:
        return
    with _stats_lock:
        _request_stats.total_requests += 1
        if selected_proxy:
            _request_stats.proxied_requests += 1
        else:
            _request_stats.direct_requests += 1


def _record_attempt(attempt: int) -> None:
    if not ASYNC_STATS_ENABLED:
        return
    with _stats_lock:
        _request_stats.total_attempts += 1
        if attempt > 0:
            _request_stats.retry_attempts += 1


def _record_response_status(status_code: int) -> None:
    if not ASYNC_STATS_ENABLED:
        return
    with _stats_lock:
        _request_stats.status_counts[status_code] = (
            _request_stats.status_counts.get(status_code, 0) + 1
        )
        if status_code in (418, 429):
            # VCI trả 418 khi rate-limit; benchmark phải đếm cả hai (D-05/AC6).
            _request_stats.throttled_responses += 1
        elif status_code >= 500:
            _request_stats.server_error_responses += 1


def _record_success() -> None:
    if not ASYNC_STATS_ENABLED:
        return
    with _stats_lock:
        _request_stats.successful_requests += 1


def _record_failure(exc: Exception) -> None:
    if not ASYNC_STATS_ENABLED:
        return
    with _stats_lock:
        _request_stats.failed_requests += 1
        _request_stats.last_error = str(exc)
        if isinstance(exc, httpx.TimeoutException):
            _request_stats.timeout_errors += 1
        elif isinstance(exc, httpx.RequestError):
            _request_stats.transport_errors += 1
        else:
            _request_stats.other_errors += 1


class _LoopClientState:
    """Per-event-loop client pool. Never shared across loops (BL-1)."""

    def __init__(self) -> None:
        self.clients: Dict[str, httpx.AsyncClient] = {}
        self.lock = asyncio.Lock()


class AsyncClientManager:
    """Keep and reuse AsyncClient instances for direct/proxy traffic."""

    def __init__(
        self,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        max_keepalive_connections: int = DEFAULT_MAX_KEEPALIVE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        # httpx clients (and the creation mutex) are bound to the loop that
        # made them, so pools are kept per running loop and die with it.
        self._loop_states: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, _LoopClientState
        ] = weakref.WeakKeyDictionary()
        self._states_guard = threading.Lock()
        self._limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )
        self._timeout = timeout

    def _state_for_running_loop(self) -> _LoopClientState:
        loop = asyncio.get_running_loop()
        with self._states_guard:
            state = self._loop_states.get(loop)
            if state is None:
                state = _LoopClientState()
                self._loop_states[loop] = state
            return state

    async def get_client(self, proxy_url: Optional[str] = None) -> httpx.AsyncClient:
        state = self._state_for_running_loop()
        key = proxy_url or "__direct__"
        client = state.clients.get(key)
        if client is not None:
            return client

        async with state.lock:
            client = state.clients.get(key)
            if client is not None:
                return client

            kwargs: Dict[str, Any] = {
                "limits": self._limits,
                "http2": True,
                "timeout": self._timeout,
            }
            if proxy_url:
                kwargs["proxy"] = proxy_url
            state.clients[key] = httpx.AsyncClient(**kwargs)
            return state.clients[key]

    async def close(self) -> None:
        with self._states_guard:
            states = list(self._loop_states.values())
            self._loop_states.clear()
        pooled: List[httpx.AsyncClient] = []
        for state in states:
            async with state.lock:
                pooled.extend(state.clients.values())
                state.clients.clear()
        for client in pooled:
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


def _is_retryable_status(status_code: int) -> bool:
    # 418/429 là lời "chậm lại" của provider — retry cùng provider chỉ đốt
    # quota. Phải failover sang provider khác (SSOT Rev.2 D-05).
    return status_code >= 500


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
        _record_attempt(attempt)
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
            _record_response_status(response.status_code)

            if response.status_code in (418, 429):
                # Rate-limit KHÔNG retry cùng provider (D-05): ném ngay để
                # HealthRouter mở cooldown và BulkRouter requeue symbol.
                retry_after = getattr(response, "headers", {}).get("Retry-After")
                raise RateLimitError(
                    provider=urlsplit(url).netloc or url,
                    retry_after=float(retry_after) if retry_after and retry_after.isdigit() else None,
                    details={"status_code": response.status_code},
                )

            response.raise_for_status()
            _record_success()
            return response.json()
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status_code = exc.response.status_code if exc.response is not None else 0
            if not _is_retryable_status(status_code):
                break
            if attempt >= max_retries:
                break
            await asyncio.sleep(retry_backoff_seconds * (2 ** attempt))
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            await asyncio.sleep(retry_backoff_seconds * (2 ** attempt))
        except RateLimitError:
            # 418/429 phải giữ nguyên retry_after để HealthRouter cooldown đúng.
            raise
        except Exception as exc:
            last_error = exc
            break

    if last_error is not None:
        _record_failure(last_error)
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
    """Async counterpart of send_request with retries and no internal throttling."""
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

    _record_request_started(selected_proxy)

    # Shared per-provider budget — sync client dùng cùng registry này (D-05/AC4).
    async with get_provider_limiter(
        urlsplit(url).netloc or "default", Config.RATE_LIMIT_RPM
    ):
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
    """Run multiple async requests with bounded concurrency.

    Uses a worker queue to keep only ``max_concurrency`` in-flight tasks,
    which significantly reduces memory pressure for very large request lists.
    """
    if not requests_list:
        return []

    worker_count = max(1, min(max_concurrency, len(requests_list)))
    queue: asyncio.Queue[Any] = asyncio.Queue()
    results: List[Any] = [None] * len(requests_list)

    for idx, req in enumerate(requests_list):
        queue.put_nowait((idx, req))
    for _ in range(worker_count):
        queue.put_nowait(None)

    async def worker() -> None:
        while True:
            item = await queue.get()
            try:
                if item is None:
                    return

                idx, req = item
                kwargs = dict(req)
                kwargs.setdefault("proxy_idx", idx)
                try:
                    results[idx] = await async_send_request(**kwargs)
                except Exception as exc:
                    results[idx] = {"error": str(exc)}
            finally:
                queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
    await queue.join()
    await asyncio.gather(*workers)
    return results


async def shutdown_async_clients() -> None:
    """Close all pooled async clients."""
    await async_client_mgr.close()


__all__ = [
    "async_send_request",
    "fetch_multiple_requests",
    "AsyncClientManager",
    "TokenBucketRateLimiter",
    "RATE_LIMITER",
    "ASYNC_STATS_ENABLED",
    "get_async_request_stats",
    "reset_async_request_stats",
    "shutdown_async_clients",
]
