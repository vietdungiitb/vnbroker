import pytest

from vnstock.api.listing import Listing
from vnstock.api.quote import Quote
from vnstock.core import source_router
from vnstock.core.registry import ProviderRegistry


class _HealthyListingProvider:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def all_symbols(self, **kwargs):
        return {"items": [], "kwargs": kwargs}


class _FailingListingProvider:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def all_symbols(self, **kwargs):
        raise ConnectionError("429 too many requests")


class _HealthyQuoteProvider:
    def __init__(self, symbol=None, **kwargs):
        self.symbol = symbol
        self.kwargs = kwargs

    def history(self, **kwargs):
        return {"symbol": self.symbol, "kwargs": kwargs}


@pytest.mark.unit
@pytest.mark.api
class TestAutoSourceRouter:
    def setup_method(self):
        source_router.reset_router_state()

    def teardown_method(self):
        source_router.reset_router_state()

    def test_auto_quote_uses_ordered_initial_source(self, monkeypatch):
        def fake_get(module_name, source_name):
            assert module_name == "quote"
            assert source_name == "kbs"
            return _HealthyQuoteProvider

        monkeypatch.setattr("vnstock.base.build_source_order", lambda *args, **kwargs: ["kbs", "vci"])
        monkeypatch.setattr(ProviderRegistry, "get", fake_get)

        quote = Quote(source="AUTO", symbol="ACB", show_log=False)

        assert quote.resolved_source == "kbs"

    def test_auto_listing_fails_over_when_primary_source_errors(self, monkeypatch):
        providers = {
            ("listing", "vci"): _FailingListingProvider,
            ("listing", "kbs"): _HealthyListingProvider,
        }

        def fake_get(module_name, source_name):
            return providers[(module_name, source_name)]

        monkeypatch.setattr("vnstock.base.build_source_order", lambda *args, **kwargs: ["vci", "kbs"])
        monkeypatch.setattr(ProviderRegistry, "get", fake_get)

        listing = Listing(source="AUTO", show_log=False)
        result = listing.all_symbols()

        assert result["source_used"] == "KBS"

    def test_router_cooldown_deprioritizes_failed_source_for_symbol(self):
        first_order = source_router.build_source_order("quote", symbol="ACB")

        assert first_order

        source_router.record_failure("quote", first_order[0])
        second_order = source_router.build_source_order("quote", symbol="ACB")

        assert second_order[0] != first_order[0]

    def test_vci_first_pool_always_starts_with_vci_when_healthy(self):
        """Single-item PRIMARY_SOURCE_POOLS["quote"]=["vci"] means every symbol
        gets VCI as the first attempt when VCI is healthy."""
        source_router.reset_router_state()
        symbols = ["ACB", "VNM", "HPG", "MSN", "VIC", "TCB", "FPT", "MWG", "BID", "CTG"]
        for sym in symbols:
            order = source_router.build_source_order("quote", symbol=sym)
            assert order[0] == "vci", (
                f"Symbol {sym}: expected vci first, got {order}"
            )

    def test_health_snapshot_reports_cooldown_and_counters(self):
        source_router.reset_router_state()

        source_router.record_failure("news", "vci")
        snapshot = source_router.get_source_health_snapshot("news")

        assert "VCI" in snapshot
        assert snapshot["VCI"]["failures"] >= 1
        assert snapshot["VCI"]["in_cooldown"] is True
        assert snapshot["VCI"]["cooldown_remaining_sec"] > 0

        source_router.record_success("news", "vci")
        snapshot2 = source_router.get_source_health_snapshot("news")

        assert snapshot2["VCI"]["failures"] == 0
        assert snapshot2["VCI"]["in_cooldown"] is False