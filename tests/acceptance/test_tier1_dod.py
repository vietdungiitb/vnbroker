"""Acceptance gate for the Tier-1 data engine.

Why this file exists: the DoD measurement used to live in a throwaway script
outside the repo, so nobody -- reviewer, CI, or the next agent -- could
reproduce the number it produced. This is the same measurement expressed as a
real pytest gate.

Run it like any other gate:

    python -m pytest tests/acceptance/test_tier1_dod.py -v

Every check below was measured FAILING at baseline commit `e5d8133`. They are
written to assert CONSEQUENCE (what the caller observes), never "a function was
called" -- an earlier version of one of these asserted only the call, and it
stayed green while the circuit breaker was completely inert.

No network egress: providers are fakes, or egress is blocked.
"""
from __future__ import annotations

import inspect
from datetime import date

import pandas as pd
import pytest
import requests

from vnbroker.core import source_router


OHLCV_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


def _ohlcv(rows: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2024-01-02", periods=rows, freq="D"),
            "open": [1.0] * rows,
            "high": [1.0] * rows,
            "low": [1.0] * rows,
            "close": [1.0] * rows,
            "volume": [10] * rows,
        }
    )


def _holiday() -> pd.DataFrame:
    """Correct schema, zero rows: a market holiday, not an outage."""
    return pd.DataFrame(columns=OHLCV_COLUMNS)


def _broken() -> pd.DataFrame:
    """Zero columns: the provider lost its contract."""
    return pd.DataFrame()


# --------------------------------------------------------------------------
# Registry must be populated by a plain `import vnbroker` (baseline: [])
# --------------------------------------------------------------------------
def test_registry_populated_after_plain_import():
    import vnbroker  # noqa: F401
    from vnbroker.core.registry import ProviderRegistry

    available = ProviderRegistry.list_available("quote")
    assert available, "registry is empty after `import vnbroker`"
    for src in ("vci", "kbs"):
        assert src in [a.lower() for a in available], f"{src} not registered"


def test_provider_reachable_and_usable():
    from vnbroker.core.unified_registry import get_provider

    for src in ("vci", "kbs"):
        cls = get_provider("quote", src)
        instance = cls(symbol="ACB")
        assert callable(getattr(instance, "history", None)), f"{src}.history missing"


# --------------------------------------------------------------------------
# Failover on an unusable result; a holiday must NOT be an outage
# --------------------------------------------------------------------------
class _FakeQuote:
    """Minimal provider surface for the failover path."""

    def __init__(self, tag: str, frames):
        self.tag = tag
        self._frames = frames
        self.calls: list[str] = []

    def history(self, *args, **kwargs):
        self.calls.append("history")
        return next(self._frames)


def _pin(quote, order):
    quote._fixed_source_order = lambda module, symbol: list(order)
    return quote


def _reset_health():
    source_router._health_state.clear()


def test_empty_without_schema_triggers_failover():
    from vnbroker.common.data import Quote

    _reset_health()
    a, b = _FakeQuote("a", iter([_broken()])), _FakeQuote("b", iter([_ohlcv()]))
    q = _pin(Quote("ACB", "AUTO", show_log=False), ["a", "b"])
    q._auto_sources = {"a": a, "b": b}

    df = q.history(start="2024-01-01", end="2024-01-10")

    assert b.calls, "failover never reached the healthy provider"
    assert len(df) > 0, "caller received an empty frame instead of real data"


def test_holiday_is_success_not_failure():
    """A correctly-shaped 0-row frame is a trading day with no trades.

    Treating it as an outage turns every public holiday into a system error and
    marks a healthy provider as broken. This is the exact mistake the bulk
    path used to make.
    """
    from vnbroker.common.data import Quote

    _reset_health()
    holiday = _FakeQuote("h", iter([_holiday()]))
    q = _pin(Quote("ACB", "AUTO", show_log=False), ["h"])
    q._auto_sources = {"h": holiday}

    df = q.history(start="2024-01-01", end="2024-01-10")

    assert len(df) == 0, "holiday frame should carry no rows"
    assert set(OHLCV_COLUMNS).issubset(set(df.columns)), "holiday frame lost its schema"
    snapshot = source_router.get_source_health_snapshot("quote")
    for entry in snapshot.values():
        assert entry.get("failures", 0) == 0, "a holiday was recorded as a provider failure"


# --------------------------------------------------------------------------
# Retry must not be nested: measure CALL COUNTS, never source text.
# `history`'s docstring literally contains the string "@retry", so any
# getsource()/grep check gives a false positive.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("method_name", ["history", "intraday", "price_depth"])
def test_no_nested_retry(method_name):
    from vnbroker.common.data import Quote
    import vnbroker.common.data as cd

    pool = ["p0", "p1"]

    class Counting:
        def __init__(self, tag):
            self.tag = tag
            self.calls = 0

        def _bump(self):
            self.calls += 1
            raise requests.exceptions.ConnectionError("simulated")

        def history(self, *a, **kw):
            self._bump()

        def intraday(self, *a, **kw):
            self._bump()

        def price_depth(self, *a, **kw):
            self._bump()

    sources = {tag: Counting(tag) for tag in pool}
    q = _pin(Quote("ACB", "AUTO", show_log=False), pool)
    q._auto_sources = sources

    retries = cd.Config.DEFAULT_RETRIES
    with pytest.raises(Exception):
        getattr(q, method_name)(start="2024-01-01", end="2024-01-03")

    total = sum(s.calls for s in sources.values())
    # Guard against a vacuous pass: a run that never called a provider proves
    # nothing about retries.
    assert total > 0, f"{method_name}: no provider was ever called -- test is vacuous"
    assert total <= retries * len(pool), (
        f"{method_name}: {total} provider calls > retries({retries}) x pool({len(pool)}); "
        "retry is nested"
    )


# --------------------------------------------------------------------------
# Bulk must actually reach the network layer
# --------------------------------------------------------------------------
def test_bulk_reaches_provider_layer_and_reports_failure():
    """Assert CONSEQUENCE: the failing provider appears in attrs['failed'].

    Not "record_failure was called" -- an earlier test asserted exactly that
    and stayed green while the circuit breaker was inert.
    """
    from vnbroker.api.bulk import BulkAPI
    from vnbroker.core.registry import ProviderRegistry

    _reset_health()

    class Down:
        def __init__(self, *a, **kw):
            raise requests.exceptions.ConnectionError("simulated outage")

    ProviderRegistry.register("quote", "vci", Down)

    orig_request = requests.Session.request

    def blocked(*a, **kw):
        raise requests.exceptions.ConnectionError("egress blocked")

    requests.Session.request = blocked
    try:
        api = BulkAPI(source="AUTO", show_log=False)
        df = api.history(["ACB", "VNM"], start="2024-01-01", end="2024-01-05")
        failed = dict(df.attrs.get("failed", {}))
    finally:
        requests.Session.request = orig_request

    assert failed, (
        "every provider failed but attrs['failed'] is empty -- the error was swallowed"
    )
    snapshot = source_router.get_source_health_snapshot("quote")
    entries = {k.lower(): v for k, v in snapshot.items()}
    assert any(v.get("failures", 0) > 0 for v in entries.values()), (
        "a provider failed but the health store recorded no failure -- "
        "the circuit breaker cannot work if its bookkeeping is mis-keyed"
    )


def test_bulk_does_not_import_api_layer():
    """`core` must not import `api`.

    Parsed with `ast`, not grepped: a plain text scan matches the docstring that
    *documents* this rule, which is how the first version of this test failed
    for the wrong reason.
    """
    import ast
    import pathlib

    import vnbroker.core.bulk_router as br

    tree = ast.parse(pathlib.Path(br.__file__).read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders += [a.name for a in node.names if a.name.startswith("vnbroker.api")]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("vnbroker.api"):
                offenders.append(f"{module}.{', '.join(a.name for a in node.names)}")
    assert not offenders, f"core layer imports the api layer: {offenders}"


# --------------------------------------------------------------------------
# Cache keys: distinct queries must not share a key; equal ones must
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "left, right",
    [
        (("all_symbols", date(2024, 1, 1)), ("all_symbols", date(2026, 10, 8))),
        ((["ACB", "VNM"],), (["VNM", "ACB"],)),
        (({"a": 1},), ({"a": 2},)),
        ((None,), ("None",)),
        ((0,), ("0",)),
        ((1,), (True,)),
        ((1,), (1.0,)),
        ((pd.DataFrame({"a": [1, 2, 3]}),), (pd.DataFrame({"a": [9, 9, 9]}),)),
    ],
    ids=[
        "date-differs",
        "list-order-differs",
        "dict-value-differs",
        "none-vs-string",
        "int-zero-vs-string",
        "int-one-vs-bool",
        "int-one-vs-float",
        "dataframe-content-differs",
    ],
)
def test_cache_keys_do_not_collide(left, right):
    from vnbroker.core.utils.cache import TTLCache

    cache = TTLCache(ttl_seconds=60)
    assert cache._make_key(*left) != cache._make_key(*right), (
        f"{left} and {right} share a cache key"
    )


def test_cache_still_hits_for_equal_arguments():
    from vnbroker.core.utils.cache import TTLCache

    cache = TTLCache(ttl_seconds=60)
    cache.set("all_symbols", "PAYLOAD")
    assert cache.get("all_symbols") == "PAYLOAD", "cache stopped working for equal args"
    assert cache.get("all_symbols") is not None


def test_cache_does_not_serve_wrong_payload():
    """The failure that motivated the encoder fix: writing under one key and
    reading under a different query returned the first payload."""
    from vnbroker.core.utils.cache import TTLCache

    cache = TTLCache(ttl_seconds=60)
    df1, df2 = pd.DataFrame({"a": [1, 2, 3]}), pd.DataFrame({"a": [9, 9, 9]})
    # Route through _make_key: the store is keyed by the derived token, and a
    # DataFrame is itself unhashable.
    cache.set(cache._make_key(df1), "PAYLOAD_FOR_DF1")
    assert cache.get(cache._make_key(df2)) is None, (
        "cache served another query's payload"
    )


# --------------------------------------------------------------------------
# Rate limiter: the hang is in wait(), not acquire()
# --------------------------------------------------------------------------
@pytest.mark.parametrize("rate", [0.1, 0.5, 1, 10])
def test_rate_limiter_capacity_allows_one_token(rate):
    from vnbroker.core.utils.rate_limiter import TokenBucketRateLimiter

    limiter = TokenBucketRateLimiter(rate=rate)
    assert limiter._capacity >= 1.0, (
        f"rate={rate} gives capacity {limiter._capacity}; a single request "
        "could never be served"
    )
    assert limiter.acquire(1.0) is True


@pytest.mark.parametrize("rate", [0.1, 0.5, 1.0])
def test_wait_terminates_or_raises(rate):
    from vnbroker.core.utils.rate_limiter import TokenBucketRateLimiter

    limiter = TokenBucketRateLimiter(rate=rate)
    limiter._tokens = 0.0  # drained, so wait() has to block
    try:
        limiter.wait(1.0, max_wait=0.2)
    except TimeoutError:
        return  # bounded and loud: acceptable
    except Exception as exc:  # pragma: no cover - would be a regression
        pytest.fail(f"wait() raised an unexpected {type(exc).__name__}: {exc}")
    pytest.fail("wait() returned even though no token was available")