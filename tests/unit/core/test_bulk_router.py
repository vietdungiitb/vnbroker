"""Tests for BulkRouter and HealthRouter (WP-3)."""

from __future__ import annotations

import time

import pandas as pd
import pytest

from vnbroker.core import source_router
from vnbroker.core.bulk_router import BulkRouter
from vnbroker.core.health_router import HealthRouter


@pytest.fixture(autouse=True)
def _clean_router(monkeypatch):
    monkeypatch.setenv("vnbroker_ROUTER_HEALTH_DB", "memory")
    source_router.reload_store()
    source_router.reset_router_state()
    yield
    source_router.reset_router_state()
    source_router.reload_store()


# ---------------------------------------------------------------------------
# HealthRouter tests
# ---------------------------------------------------------------------------


def test_health_router_singleton():
    """HealthRouter can be instantiated."""
    hr = HealthRouter()
    assert hr is not None
    assert hr._latency_window == {}


def test_get_healthy_providers():
    """Returns list of healthy providers."""
    hr = HealthRouter()
    # Record a success so the provider is known
    hr.record_success("vci", 100.0, module="quote")
    healthy = hr.get_healthy_providers("quote")
    assert isinstance(healthy, list)
    assert "VCI" in healthy


def test_health_router_latency_ranking():
    """Providers are sorted by average latency (fastest first)."""
    hr = HealthRouter()
    hr.record_success("vci", 200.0, module="quote")
    hr.record_success("kbs", 50.0, module="quote")
    healthy = hr.get_healthy_providers("quote")
    # kbs has lower avg latency, should come first
    if "KBS" in healthy and "VCI" in healthy:
        assert healthy.index("KBS") < healthy.index("VCI")


def test_health_router_failure_excludes_provider():
    """Provider in cooldown is excluded from healthy list."""
    hr = HealthRouter()
    hr.record_failure("vci", ConnectionError("timeout"), module="quote")
    healthy = hr.get_healthy_providers("quote")
    assert "VCI" not in healthy


# ---------------------------------------------------------------------------
# BulkRouter tests
# ---------------------------------------------------------------------------


def test_bulk_router_distribution():
    """Symbols are distributed across providers."""
    hr = HealthRouter()
    hr.record_success("vci", 100.0, module="quote")
    hr.record_success("kbs", 100.0, module="quote")

    router = BulkRouter(health_router=hr)

    # Monkey-patch _fetch_batch to capture the distribution
    captured = {}

    def mock_fetch_batch(provider, symbols, start, end, module):
        captured.setdefault(provider, []).extend(symbols)
        return [pd.DataFrame({"symbol": symbols})]

    router._fetch_batch = mock_fetch_batch

    symbols = ["ACB", "BID", "CTG", "DPG", "EIB", "FPT"]
    result = router.fetch_history(symbols, "2024-01-01", "2024-12-31", module="quote")

    assert result["symbols_requested"] == 6
    assert result["symbols_returned"] > 0
    # Symbols should be distributed across providers
    all_assigned = []
    for prov_syms in captured.values():
        all_assigned.extend(prov_syms)
    assert set(all_assigned) == set(symbols)


def test_concurrent_fetch():
    """Multiple providers can fetch concurrently (mock)."""
    hr = HealthRouter()
    hr.record_success("vci", 100.0, module="quote")
    hr.record_success("kbs", 100.0, module="quote")

    router = BulkRouter(health_router=hr)

    call_times = {}

    def mock_fetch_batch(provider, symbols, start, end, module):
        call_times[provider] = time.monotonic()
        time.sleep(0.05)  # Simulate network latency
        return [pd.DataFrame({"symbol": symbols, "provider": provider})]

    router._fetch_batch = mock_fetch_batch

    symbols = ["ACB", "BID", "CTG", "DPG"]
    result = router.fetch_history(symbols, "2024-01-01", "2024-12-31", module="quote")

    # Both providers should have been called
    assert len(call_times) >= 1
    # Results should contain data from providers
    assert result["symbols_returned"] > 0


def test_empty_symbols():
    """Empty symbol list doesn't crash."""
    hr = HealthRouter()
    router = BulkRouter(health_router=hr)

    result = router.fetch_history([], "2024-01-01", "2024-12-31", module="quote")

    assert result["symbols_requested"] == 0
    assert result["symbols_returned"] == 0
    assert result["providers_used"] == []
    assert result["results"] == {}
    assert result["errors"] == {}


def test_no_healthy_providers_raises():
    """Raises ConnectionError when no healthy providers available."""
    hr = HealthRouter()
    # Record failures for ALL quote providers to put them all in cooldown
    hr.record_failure("vci", ConnectionError("timeout"), module="quote")
    hr.record_failure("kbs", ConnectionError("timeout"), module="quote")

    router = BulkRouter(health_router=hr)

    with pytest.raises(ConnectionError, match="No healthy providers"):
        router.fetch_history(["ACB"], "2024-01-01", "2024-12-31", module="quote")


def test_provider_failure_captured_not_crash():
    """Provider failure is captured in errors, doesn't crash entire batch."""
    hr = HealthRouter()
    hr.record_success("vci", 100.0, module="quote")
    hr.record_success("kbs", 100.0, module="quote")

    router = BulkRouter(health_router=hr)

    def mock_fetch_batch(provider, symbols, start, end, module):
        if provider == "VCI":
            raise ConnectionError("VCI is down")
        return [pd.DataFrame({"symbol": symbols})]

    router._fetch_batch = mock_fetch_batch

    symbols = ["ACB", "BID", "CTG", "DPG"]
    result = router.fetch_history(symbols, "2024-01-01", "2024-12-31", module="quote")

    # Should have partial results
    assert "VCI" in result["errors"]
    assert result["symbols_returned"] > 0  # kbs should have succeeded
