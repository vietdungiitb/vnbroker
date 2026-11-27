"""SSOT Phase 1 — rate-limit 418/429 must failover, never retry same provider."""
import pandas as pd
import pytest

from vnbroker.core.exceptions import RateLimitError
from vnbroker.core.utils.async_client import _is_retryable_status
from vnbroker.explorer.dnse.quote import _FAILOVER_MARKERS, _raise_for_failover


def test_429_and_418_are_not_retryable_in_async_path():
    assert _is_retryable_status(429) is False
    assert _is_retryable_status(418) is False
    assert _is_retryable_status(500) is True


def test_dnse_markers_include_http_418():
    assert "418" in _FAILOVER_MARKERS


def test_dnse_preserves_rate_limit_error_and_retry_after():
    exc = RateLimitError("too many requests", details={"retry_after": 12})
    with pytest.raises(RateLimitError) as info:
        _raise_for_failover(exc, "history")
    assert info.value.details.get("retry_after") == 12


def test_provider_limiter_can_be_injected_by_caller():
    from vnbroker.core.utils.rate_limiter import (
        TokenBucketRateLimiter,
        get_provider_limiter,
        reset_provider_limiters,
        set_provider_limiter,
    )

    reset_provider_limiters()
    custom = TokenBucketRateLimiter(rate=7)
    set_provider_limiter("vci", custom)
    assert get_provider_limiter("vci", 999) is custom
    reset_provider_limiters()


def test_sync_and_async_share_one_provider_budget():
    from vnbroker.core.utils.rate_limiter import (
        get_provider_limiter,
        reset_provider_limiters,
    )

    reset_provider_limiters()
    first = get_provider_limiter("vci", 5)
    second = get_provider_limiter("vci", 1000)
    assert first is second
    assert first.rate == 5
    assert get_provider_limiter("kbs", 5) is not first
    reset_provider_limiters()


def test_benchmark_counts_418_as_throttled(monkeypatch):
    from vnbroker.core.utils import async_client as ac

    monkeypatch.setattr(ac, "ASYNC_STATS_ENABLED", True)
    ac.reset_async_request_stats()
    ac._record_response_status(418)
    assert ac.get_async_request_stats()["throttled_responses"] == 1


def test_unlabeled_frame_is_not_reported_as_unknown():
    from vnbroker.api.bulk import resolve_frame_symbol

    bare = pd.DataFrame({"close": [1.0]})
    assert resolve_frame_symbol(bare) is None
    bare.attrs["symbol"] = "TPB"
    assert resolve_frame_symbol(bare) == "TPB"


def test_bulk_router_requeues_symbols_when_provider_rate_limited(monkeypatch):
    """A provider hitting 418 mid-batch must not drop its symbols."""
    from vnbroker.core.bulk_router import BulkRouter

    router = BulkRouter.__new__(BulkRouter)
    router._health = type("H", (), {
        "record_success": lambda *a, **k: None,
        "record_failure": lambda *a, **k: None,
    })()

    def fake_fetch(provider, symbols, start, end, module, interval="1D"):
        if provider == "vci" and "TPB" in symbols:
            raise RateLimitError("418")
        df = pd.DataFrame({"close": [1.0]})
        df.attrs["symbol"] = symbols[0]
        return [df]

    monkeypatch.setattr(router, "_fetch_batch", fake_fetch)
    monkeypatch.setattr(
        router, "_select_providers", lambda module, providers: ["vci", "kbs"],
    )
    result = router.fetch_history(["TPB", "ACB"], module="quote")
    served = [
        df.attrs.get("symbol")
        for frames in result["results"].values()
        for df in frames
    ]
    assert set(served) >= {"TPB", "ACB"}
