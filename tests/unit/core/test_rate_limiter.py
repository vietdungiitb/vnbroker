"""Tests for token bucket rate limiter."""

import threading
import time
import pytest
from vnbroker.core.utils.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    """Test suite for TokenBucketRateLimiter."""

    def test_rate_limiter_init(self):
        """Can be instantiated with default and custom parameters."""
        # Default capacity (capacity = rate)
        limiter = TokenBucketRateLimiter(rate=10.0)
        assert limiter._rate == 10.0
        assert limiter._capacity == 10.0
        assert limiter._tokens == 10.0

        # Custom capacity
        limiter2 = TokenBucketRateLimiter(rate=5.0, capacity=20.0)
        assert limiter2._rate == 5.0
        assert limiter2._capacity == 20.0
        assert limiter2._tokens == 20.0

    def test_rate_limiter_acquire(self):
        """Can acquire tokens when available."""
        limiter = TokenBucketRateLimiter(rate=10.0, capacity=10.0)
        # Should succeed immediately (bucket starts full)
        assert limiter.acquire(1.0) is True
        assert limiter._tokens == pytest.approx(9.0, abs=0.1)

        # Acquire multiple tokens
        assert limiter.acquire(5.0) is True
        assert limiter._tokens == pytest.approx(4.0, abs=0.1)

    def test_rate_limiter_exhausted(self):
        """Returns False when bucket is exhausted."""
        limiter = TokenBucketRateLimiter(rate=1.0, capacity=2.0)
        # Drain the bucket
        assert limiter.acquire(2.0) is True
        assert limiter._tokens == pytest.approx(0.0, abs=0.01)

        # Should fail now
        assert limiter.acquire(1.0) is False
        assert limiter._tokens == pytest.approx(0.0, abs=0.01)

    def test_rate_limiter_refill(self):
        """Tokens refill over time."""
        limiter = TokenBucketRateLimiter(rate=10.0, capacity=10.0)
        # Drain the bucket
        limiter.acquire(10.0)
        assert limiter._tokens == pytest.approx(0.0, abs=0.01)

        # Wait for refill (10 tokens/sec = 0.1 sec per token)
        time.sleep(0.15)
        # Trigger refill by attempting a small acquire (updates _tokens based on elapsed time)
        # Should have ~1.5 tokens now, so acquiring 0.1 should succeed
        assert limiter.acquire(0.1) is True
        assert limiter._tokens == pytest.approx(1.4, abs=0.2)
        assert limiter._tokens <= 10.0

        # Should be able to acquire 1 token
        assert limiter.acquire(1.0) is True

    def test_rate_limiter_thread_safe(self):
        """Concurrent access is safe."""
        limiter = TokenBucketRateLimiter(rate=1000.0, capacity=1000.0)
        results = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    acquired = limiter.acquire(1.0)
                    results.append(acquired)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0
        # All 100 acquires should succeed (capacity is 1000)
        assert len(results) == 100
        assert all(results)

    def test_rate_limiter_wait(self):
        """Wait blocks until tokens are available."""
        limiter = TokenBucketRateLimiter(rate=100.0, capacity=1.0)
        # Drain the bucket
        limiter.acquire(1.0)
        assert limiter._tokens == 0.0

        # Wait should block briefly then succeed
        start = time.monotonic()
        limiter.wait(1.0)
        elapsed = time.monotonic() - start

        # Should have waited at least a tiny bit (100 tokens/sec = 0.01 sec per token)
        assert elapsed >= 0.005
        # Token should be consumed
        assert limiter._tokens < 1.0
