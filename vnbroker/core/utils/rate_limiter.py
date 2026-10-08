"""Token bucket rate limiter for API requests."""

import threading
import time
from typing import Optional


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate: float, capacity: Optional[float] = None):
        """
        Args:
            rate: Tokens added per second
            capacity: Bucket capacity (default: rate)
        """
        self._rate = rate
        self._capacity = capacity or rate
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

    def wait(self, tokens: float = 1.0) -> None:
        """Wait until tokens are available."""
        while not self.acquire(tokens):
            time.sleep(0.01)
