import pytest

from vnstock.api.listing import Listing
from vnstock.api.quote import Quote
from vnstock.api.trading import Trading
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


class _RateLimitedTradingProvider:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def price_board(self, symbols_list, **kwargs):
        raise ConnectionError("429 too many requests")


class _HealthyTradingProvider:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def price_board(self, symbols_list, **kwargs):
        return {
            "symbols": symbols_list,
            "count": len(symbols_list),
        }


class _FailingTradingProvider:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def price_board(self, symbols_list, **kwargs):
        raise ConnectionError("service unavailable")


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

    def test_auto_trading_uses_kbs_as_initial_source(self, monkeypatch):
        def fake_get(module_name, source_name):
            assert module_name == "trading"
            assert source_name == "kbs"
            return _HealthyTradingProvider

        monkeypatch.setattr(ProviderRegistry, "get", fake_get)

        trading = Trading(source="AUTO", show_log=False)

        assert trading.resolved_source == "kbs"

    def test_auto_trading_price_board_fails_over_to_vci_when_kbs_errors(self, monkeypatch):
        providers = {
            ("trading", "kbs"): _FailingTradingProvider,
            ("trading", "vci"): _HealthyTradingProvider,
        }

        def fake_get(module_name, source_name):
            return providers[(module_name, source_name)]

        monkeypatch.setattr(ProviderRegistry, "get", fake_get)

        trading = Trading(source="AUTO", show_log=False)
        result = trading.price_board(symbols_list=["ACB", "VCB"])

        assert result["source_used"] == "VCI"
        assert result["count"] == 2
        assert trading.resolved_source == "vci"

        health = source_router.get_source_health_snapshot("trading")
        assert health["KBS"]["failures"] >= 1
        assert health["KBS"]["in_cooldown"] is True

        next_order = source_router.build_source_order("trading")
        assert next_order[0] == "vci"

    def test_auto_trading_price_board_rate_limit_triggers_cooldown_and_switches_active_source(self, monkeypatch):
        providers = {
            ("trading", "vci"): _RateLimitedTradingProvider,
            ("trading", "kbs"): _HealthyTradingProvider,
        }

        def fake_get(module_name, source_name):
            return providers[(module_name, source_name)]

        monkeypatch.setattr("vnstock.base.build_source_order", lambda *args, **kwargs: ["vci", "kbs"])
        monkeypatch.setattr(ProviderRegistry, "get", fake_get)

        trading = Trading(source="AUTO", show_log=False)
        result = trading.price_board(symbols_list=["ACB", "VCB"])

        assert result["source_used"] == "KBS"
        assert result["count"] == 2
        assert trading.resolved_source == "kbs"

        health = source_router.get_source_health_snapshot("trading")
        assert health["VCI"]["failures"] >= 1
        assert health["VCI"]["in_cooldown"] is True

        next_order = source_router.build_source_order("trading")
        assert next_order[0] == "kbs"

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

    def test_kbs_first_trading_pool_always_starts_with_kbs_when_healthy(self):
        symbols = ["ACB", "VCB", "TCB", "HPG"]
        for sym in symbols:
            order = source_router.build_source_order("trading", symbol=sym)
            assert order[0] == "kbs", (
                f"Symbol {sym}: expected kbs first, got {order}"
            )

    def test_trading_auto_primary_can_be_overridden_by_env(self, monkeypatch):
        monkeypatch.setenv("VNSTOCK_TRADING_AUTO_PRIMARY", "vci")
        order = source_router.build_source_order("trading", symbol="ACB")
        assert order[0] == "vci"

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