"""Token bucket rate limiter for API requests."""

import asyncio
import threading
import time
from typing import Optional

#: One request costs at least one token, so a bucket smaller than this can
#: never serve a single request. With `capacity = capacity or rate`, any
#: `rate < 1` produced such a bucket and `acquire(1.0)` could never succeed.
MIN_CAPACITY: float = 1.0

#: Upper bound for :meth:`TokenBucketRateLimiter.wait`, in seconds. `wait()`
#: used to loop with no bound at all, so a request the bucket could never
#: satisfy blocked the calling thread forever.
DEFAULT_MAX_WAIT: float = 30.0

#: How long to sleep between acquisition attempts while waiting.
POLL_INTERVAL: float = 0.01


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter."""

    @property
    def rate(self) -> float:
        """Tokens added per second — needed to share the same budget safely."""
        return self._rate

    async def __aenter__(self) -> "TokenBucketRateLimiter":
        """Async path uses the SAME bucket as the sync path (D-05/AC4)."""
        await asyncio.to_thread(self.wait)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


    def __init__(self, rate: float, capacity: Optional[float] = None):
        """
        Args:
            rate: Tokens added per second
            capacity: Bucket capacity (default: rate, never below
                :data:`MIN_CAPACITY` so that one request always fits)
        """
        self._rate = rate
        requested = rate if capacity is None else capacity
        self._capacity = max(requested, MIN_CAPACITY)
        self._tokens = self._capacity
        self._last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> bool:
        """Acquire tokens. Returns True if successful."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_update = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def wait(self, tokens: float = 1.0, max_wait: float = DEFAULT_MAX_WAIT) -> None:
        """Wait until tokens are available, or give up after ``max_wait``.

        Args:
            tokens: Tokens to acquire.
            max_wait: Seconds to wait at most.

        Raises:
            TimeoutError: If the tokens could not be acquired within
                ``max_wait`` seconds. This includes the unsatisfiable case
                ``tokens > capacity``, which used to hang forever.
        """
        if tokens > self._capacity:
            msg = (
                f"Cannot wait for {tokens} tokens: "
                f"bucket capacity is {self._capacity}"
            )
            raise TimeoutError(msg)

        budget = max(0.0, max_wait)
        deadline = time.monotonic() + budget
        while True:
            if self.acquire(tokens):
                return

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                msg = (
                    f"Timed out after {budget}s waiting for {tokens} tokens "
                    f"(rate={self._rate}/s, capacity={self._capacity})"
                )
                raise TimeoutError(msg)

            time.sleep(min(POLL_INTERVAL, remaining))


# Provider-scoped buckets. Both the sync and async HTTP clients MUST use this
# registry so a provider has ONE budget instead of two independent limiters
# (SSOT Rev.2 D-05 / AC4).
_provider_limiters: dict[str, TokenBucketRateLimiter] = {}
_registry_lock = threading.Lock()


def get_provider_limiter(provider: str, rate: float,
                         capacity: float | None = None) -> TokenBucketRateLimiter:
    """Return the shared limiter for ``provider``, creating it on first use."""
    with _registry_lock:
        limiter = _provider_limiters.get(provider)
        if limiter is None:
            limiter = TokenBucketRateLimiter(rate=rate, capacity=capacity or rate)
            _provider_limiters[provider] = limiter
        return limiter


def set_provider_limiter(provider: str, limiter: TokenBucketRateLimiter) -> None:
    """Inject a caller-owned limiter (e.g. Redis-backed adapter from vninvest)."""
    with _registry_lock:
        _provider_limiters[provider] = limiter


def reset_provider_limiters() -> None:
    """Test-only helper: drop all shared buckets."""
    with _registry_lock:
        _provider_limiters.clear()
