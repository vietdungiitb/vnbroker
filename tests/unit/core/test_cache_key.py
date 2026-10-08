"""Tests for cache key generation — verifies no memory addresses in keys."""

from datetime import date, datetime

import pytest
from vnbroker.core.utils.cache import TTLCache


class _FakeObj:
    """Simulates a domain object whose str() includes a memory address."""
    def __str__(self):
        return f"<FakeObj object at 0x{id(self):016X}>"


class _OtherObj:
    """A second domain object type, also with an address in str()."""
    def __str__(self):
        return f"<OtherObj object at 0x{id(self):016X}>"


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


# ── VN-2 / AC-9: no argument may be silently dropped from the key ───────────
#
# `_make_key` used to keep only str/int/float/bool/None arguments, so every
# call whose arguments were `date`, `list` or `dict` produced the SAME key and
# the cache served one call's payload for another's arguments.

def test_date_arguments_do_not_collide(cache):
    """Two different dates must not produce the same key."""
    old = cache._make_key("all_symbols", date(2024, 1, 1))
    new = cache._make_key("all_symbols", date(2026, 10, 8))
    assert old != new


def test_list_order_is_part_of_the_key(cache):
    """A list is ordered: ['ACB','VNM'] must differ from ['VNM','ACB']."""
    assert cache._make_key("f", ["ACB", "VNM"]) != cache._make_key("f", ["VNM", "ACB"])


def test_dict_values_are_part_of_the_key(cache):
    """A dict's values must not be dropped from the key."""
    assert cache._make_key("f", {"a": 1}) != cache._make_key("f", {"a": 2})


def test_list_and_tuple_are_distinguished(cache):
    """A list and a tuple with the same items are different arguments."""
    assert cache._make_key("f", ["ACB"]) != cache._make_key("f", ("ACB",))


def test_datetime_and_date_are_distinguished(cache):
    """A datetime must not share the key of the date it falls on."""
    day = date(2024, 1, 1)
    moment = datetime(2024, 1, 1, 9, 30)
    assert cache._make_key("f", day) != cache._make_key("f", moment)


def test_nested_arguments_are_distinguished(cache):
    """Structure inside an argument must still change the key."""
    assert cache._make_key("f", ["a", {"b": 1}]) != cache._make_key("f", ["a", {"b": 2}])
    assert cache._make_key("f", {"a": ["x"]}) != cache._make_key("f", {"a": ["y"]})


def test_kwarg_container_values_are_distinguished(cache):
    """The rule applies to kwargs exactly as it does to positional args."""
    assert cache._make_key("f", symbols=["ACB"]) != cache._make_key("f", symbols=["VNM"])


def test_unknown_object_types_are_distinguished_without_addresses(cache):
    """Domain objects collapse to their type name, never to a memory address."""
    key = cache._make_key("f", _FakeObj())
    assert "0x" not in key
    assert cache._make_key("f", _FakeObj()) != cache._make_key("f", _OtherObj())


def test_same_arguments_still_produce_one_stable_key(cache):
    """Positive case: equal arguments must keep producing an equal key."""
    assert cache._make_key("f", date(2024, 1, 1), ["ACB"], {"a": 1}) == \
        cache._make_key("f", date(2024, 1, 1), ["ACB"], {"a": 1})


def test_cache_still_hits_for_repeated_non_primitive_arguments(cache):
    """Positive case: the cache must still hit, so the fix costs no reuse."""
    calls = []

    def expensive(*_args, **_kwargs):
        calls.append(1)
        return "computed"

    def cached(*args, **kwargs):
        key = cache._make_key("expensive", *args, **kwargs)
        hit = cache.get(key)
        if hit is not None:
            return hit
        result = expensive(*args, **kwargs)
        cache.set(key, result)
        return result

    day = date(2024, 1, 1)
    symbols = ["ACB", "VNM"]

    assert cached(day, symbols=symbols) == "computed"
    assert cached(day, symbols=symbols) == "computed"
    assert len(calls) == 1  # second call served from the cache

    # Different arguments must still miss.
    assert cached(date(2026, 10, 8), symbols=symbols) == "computed"
    assert cached(day, symbols=["VNM", "ACB"]) == "computed"
    assert len(calls) == 3


def test_cache_does_not_serve_another_dates_payload(cache):
    """End-to-end corruption check: write under one date, read under another."""
    cache.set(cache._make_key("all_symbols", date(2024, 1, 1)), "payload-2024-01-01")

    assert cache.get(cache._make_key("all_symbols", date(2026, 10, 8))) is None
    assert cache.get(cache._make_key("all_symbols", date(2024, 1, 1))) == "payload-2024-01-01"


def test_cache_does_not_serve_another_list_order_payload(cache):
    """End-to-end corruption check for list ordering."""
    cache.set(cache._make_key("all_symbols", ["ACB", "VNM"]), "payload-acb-vnm")

    assert cache.get(cache._make_key("all_symbols", ["VNM", "ACB"])) is None
    assert cache.get(cache._make_key("all_symbols", ["ACB", "VNM"])) == "payload-acb-vnm"


def test_cache_does_not_serve_another_dict_payload(cache):
    """End-to-end corruption check for dict values."""
    cache.set(cache._make_key("all_symbols", {"a": 1}), "payload-a=1")

    assert cache.get(cache._make_key("all_symbols", {"a": 2})) is None
    assert cache.get(cache._make_key("all_symbols", {"a": 1})) == "payload-a=1"
