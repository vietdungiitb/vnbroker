"""Tests for cache key generation — verifies no memory addresses in keys."""

import pytest
from vnbroker.core.utils.cache import TTLCache


class _FakeObj:
    """Simulates a domain object whose str() includes a memory address."""
    def __str__(self):
        return f"<FakeObj object at 0x{id(self):016X}>"


@pytest.fixture
def cache():
    return TTLCache(ttl_seconds=60, max_size=10, name="test")


# ── _make_key tests ──────────────────────────────────────────────────────────

def test_cache_key_no_object_id(cache):
    """Key must not contain memory addresses from object str()."""
    obj = _FakeObj()
    key = cache._make_key("func_name", obj, "arg1")
    assert "0x" not in key
    assert "object at" not in key


def test_cache_key_consistent(cache):
    """Same primitive args must produce the same key."""
    key1 = cache._make_key("func", "a", 1, 2.5, True, None)
    key2 = cache._make_key("func", "a", 1, 2.5, True, None)
    assert key1 == key2


def test_cache_key_different_args(cache):
    """Different args must produce different keys."""
    key1 = cache._make_key("func", "a")
    key2 = cache._make_key("func", "b")
    assert key1 != key2


def test_cache_key_kwargs_sorted(cache):
    """Kwargs order must not affect the key."""
    key1 = cache._make_key("func", x=1, y=2)
    key2 = cache._make_key("func", y=2, x=1)
    assert key1 == key2


def test_cache_key_filters_non_primitive_kwargs(cache):
    """Non-primitive kwargs values must be filtered out."""
    obj = _FakeObj()
    key = cache._make_key("func", bad=obj, good="ok")
    assert "0x" not in key
    assert "good=ok" in key


# ── Cache hit / miss integration ─────────────────────────────────────────────

def test_cache_hit_after_fix(cache):
    """Cache must hit when called twice with same primitive args."""
    call_count = 0

    def expensive(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    key = cache._make_key("expensive", 5)

    # First call — miss
    result1 = cache.get(key)
    assert result1 is None
    cache.set(key, expensive(5))

    # Second call — hit
    result2 = cache.get(key)
    assert result2 == 10
    assert call_count == 1  # function called only once


def test_cache_miss_different_args(cache):
    """Different args must produce a cache miss."""
    cache.set(cache._make_key("f", 1), "one")
    assert cache.get(cache._make_key("f", 2)) is None


def test_cache_stats_hit_rate(cache):
    """Stats should reflect hits and misses correctly."""
    key = cache._make_key("f", "x")
    cache.get(key)          # miss
    cache.set(key, 42)
    cache.get(key)          # hit
    stats = cache.stats()
    assert stats["hit_count"] == 1
    assert stats["total_count"] == 2
    assert stats["hit_rate"] == 0.5
