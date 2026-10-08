"""Tests for token bucket rate limiter."""

import inspect
import threading
import time
import pytest
from vnbroker.core.utils.rate_limiter import TokenBucketRateLimiter


def run_within_deadline(fn, deadline_s):
    """Run ``fn()`` on a daemon thread and wait at most ``deadline_s``.

    Returns ``(finished, error)``. ``finished`` is False when the call was
    still blocked at the deadline — that is how the suite asserts "must never
    hang" without hanging itself on a regression.
    """
    box = {}

    def runner():
        try:
            fn()
        except BaseException as exc:  # noqa: BLE001 - the error is the assertion
            box["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(deadline_s)
    return not thread.is_alive(), box.get("error")


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


# ── VN-3 / AC-10: a slow limiter must still serve one request, and wait()
#    must never block forever ─────────────────────────────────────────────────
#
# `capacity = capacity or rate` gave a bucket smaller than one token when
# `rate < 1` (e.g. rate=0.5 -> capacity 0.5), so `acquire(1.0)` could never
# succeed. `wait()` had no bound at all, so it spun forever in that state.
# Note: `acquire()` itself never hung — it returns False immediately.

class TestSlowRateLimiter:
    """AC-10: rate below one token per second."""

    def test_capacity_is_never_below_one_token(self):
        """A bucket must be able to hold the one token a request needs."""
        limiter = TokenBucketRateLimiter(rate=0.5)
        assert limiter._capacity >= 1.0
        assert limiter._tokens >= 1.0

    def test_explicit_small_capacity_is_raised_to_one_token(self):
        """An explicit capacity below one token is raised, not honoured."""
        limiter = TokenBucketRateLimiter(rate=0.5, capacity=0.1)
        assert limiter._capacity >= 1.0

    def test_acquire_one_token_succeeds_on_a_slow_limiter(self):
        """AC-10: acquire(1.0) must return True at rate=0.5."""
        limiter = TokenBucketRateLimiter(rate=0.5)
        assert limiter.acquire(1.0) is True

    def test_wait_returns_within_two_seconds(self):
        """AC-10: wait(1.0) at rate=0.5 must terminate within 2s."""
        limiter = TokenBucketRateLimiter(rate=0.5)

        start = time.monotonic()
        finished, error = run_within_deadline(lambda: limiter.wait(1.0), 2.0)
        elapsed = time.monotonic() - start

        assert finished, "wait(1.0) was still blocked after 2s"
        assert error is None, f"wait(1.0) raised {error!r}"
        assert elapsed < 2.0

    def test_wait_raises_timeout_instead_of_hanging(self):
        """AC-10: a request the bucket can never satisfy raises TimeoutError."""
        limiter = TokenBucketRateLimiter(rate=0.5)
        limiter.acquire(1.0)  # drain the bucket

        finished, error = run_within_deadline(lambda: limiter.wait(2.0), 2.0)

        assert finished, "wait(2.0) hung instead of raising"
        assert isinstance(error, TimeoutError), f"expected TimeoutError, got {error!r}"

    def test_wait_honours_max_wait_on_a_drained_bucket(self):
        """wait() must give up once max_wait is spent."""
        limiter = TokenBucketRateLimiter(rate=0.5)
        limiter.acquire(1.0)  # drain the bucket; refilling 1 token takes 2s

        start = time.monotonic()
        finished, error = run_within_deadline(lambda: limiter.wait(1.0, max_wait=0.05), 2.0)
        elapsed = time.monotonic() - start

        assert finished, "wait(1.0, max_wait=0.05) hung"
        assert isinstance(error, TimeoutError), f"expected TimeoutError, got {error!r}"
        assert elapsed < 1.0, f"wait() overran max_wait by {elapsed:.3f}s"

    def test_wait_succeeds_when_tokens_arrive_in_time(self):
        """Positive case: max_wait must not break a legitimate wait."""
        limiter = TokenBucketRateLimiter(rate=1000.0, capacity=1.0)
        limiter.acquire(1.0)  # drain; 1 token arrives in ~1ms

        start = time.monotonic()
        finished, error = run_within_deadline(lambda: limiter.wait(1.0, max_wait=5.0), 2.0)
        elapsed = time.monotonic() - start

        assert finished, "wait() hung although tokens were seconds away"
        assert error is None, f"wait() raised {error!r}"
        assert elapsed < 2.0

    def test_wait_default_max_wait_is_a_finite_bound(self):
        """The default bound must stay finite — an unbounded default is the bug."""
        default = inspect.signature(TokenBucketRateLimiter.wait).parameters["max_wait"].default

        assert isinstance(default, (int, float))
        assert not isinstance(default, bool)
        assert 0 < default < 3600, f"max_wait default must be a sane bound, got {default!r}"

    def test_zero_max_wait_still_hands_out_available_tokens(self):
        """A zero budget means 'try once', not 'always fail'."""
        limiter = TokenBucketRateLimiter(rate=1000.0, capacity=10.0)
        limiter.wait(1.0, max_wait=0.0)
