"""
Unit tests for vnbroker.api.bulk — BulkAPI class.

Tests the BulkAPI integration with BulkRouter, HealthRouter, and ProviderPool.

Phần T1/T3/R4/R5/D3/D7 (PLAN_TIER1_ENGINE_v3.md §4 AC-1, AC-4..AC-6, §6) được
thêm ở cuối file.
"""

import inspect

import pytest
import pandas as pd

from vnbroker.api.bulk import BulkAPI
from vnbroker.core import source_router
from vnbroker.core.registry import ProviderRegistry
from vnbroker.ui.market import Market


@pytest.fixture(autouse=True)
def _clean_health(monkeypatch):
    """Cô lập health store cho mọi test trong file.

    Không có fixture này thì một test ghi ``record_failure`` sẽ đẩy vci/kbs vào
    cooldown và làm các test chạy sau nhận ``ConnectionError``.
    """
    monkeypatch.setenv("vnbroker_ROUTER_HEALTH_DB", "memory")
    source_router.reload_store()
    source_router.reset_router_state()
    yield
    source_router.reset_router_state()
    source_router.reload_store()


def _frame(symbol: str) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.0, 9.5],
            "close": [10.2, 10.7],
            "volume": [1000, 1100],
        }
    )
    df.attrs["symbol"] = symbol
    return df


def _block_egress(monkeypatch) -> None:
    """Chặn MỌI đường thoát ra mạng.

    ``requests.Session.request`` không đủ: VCI đi qua
    ``vnbroker.core.utils.async_send_request`` (aiohttp), nên chỉ chặn requests
    thì VCI vẫn ra ngoài và test biến thành phụ thuộc mạng thật.
    """
    import requests

    def _no_network(*args, **kwargs):
        raise requests.exceptions.ConnectionError("EGRESS BLOCKED BY TEST")

    async def _no_network_async(*args, **kwargs):
        raise ConnectionError("EGRESS BLOCKED BY TEST")

    monkeypatch.setattr(requests.Session, "request", _no_network)
    monkeypatch.setattr("vnbroker.core.utils.async_send_request", _no_network_async)


class _ServingProvider:
    """Provider giả phục vụ đủ mọi symbol, có ghi lại lời gọi (spy của AC-1)."""

    calls: list = []

    @classmethod
    def fetch_multiple(cls, symbols, start=None, end=None, interval="1D"):
        cls.calls.append((tuple(symbols), interval))
        return [_frame(sym) for sym in symbols]


class _DownProvider:
    calls: list = []

    @classmethod
    def fetch_multiple(cls, symbols, start=None, end=None, interval="1D"):
        raise RuntimeError("network unreachable")


def _pool_with(monkeypatch, names):
    """Ép ProviderPool chỉ trả về `names`."""
    api = BulkAPI(source="AUTO", show_log=False)
    monkeypatch.setattr(
        api._provider_pool, "get_available_providers", lambda module: list(names)
    )
    return api


@pytest.mark.unit
@pytest.mark.api
class TestBulkAPI:
    """Test suite for BulkAPI."""

    def test_bulk_api_init(self):
        """BulkAPI can be instantiated."""
        api = BulkAPI(source="AUTO", show_log=False)
        assert api is not None
        assert api.source == "AUTO"
        assert api.show_log is False

    def test_bulk_api_default_source(self):
        """BulkAPI defaults to AUTO source."""
        api = BulkAPI(show_log=False)
        assert api.source == "AUTO"

    def test_bulk_history_empty_symbols(self):
        """Empty symbol list returns empty DataFrame without crashing."""
        api = BulkAPI(source="AUTO", show_log=False)
        df = api.history([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty
        assert "symbol" in df.columns

    def test_bulk_history_returns_dataframe(self):
        """Bulk history returns DataFrame with symbol column."""
        api = BulkAPI(source="AUTO", show_log=False)
        # Use a small symbol list — may return empty if no network,
        # but should always return a DataFrame
        df = api.history(["ACB"], start="2024-01-01", end="2024-01-31")
        assert isinstance(df, pd.DataFrame)
        assert "symbol" in df.columns

    def test_bulk_history_attrs(self):
        """Result has sources_used, failed, requested, returned attrs."""
        api = BulkAPI(source="AUTO", show_log=False)
        df = api.history(["ACB"], start="2024-01-01", end="2024-01-31")
        assert hasattr(df, "attrs")
        assert "sources_used" in df.attrs
        assert "failed" in df.attrs
        assert "requested" in df.attrs
        assert "returned" in df.attrs
        assert df.attrs["requested"] == 1

    def test_bulk_history_multiple_symbols(self):
        """Bulk history handles multiple symbols."""
        api = BulkAPI(source="AUTO", show_log=False)
        df = api.history(["ACB", "VNM", "FPT"], start="2024-01-01", end="2024-01-31")
        assert isinstance(df, pd.DataFrame)
        assert "symbol" in df.columns
        assert df.attrs["requested"] == 3

    def test_bulk_price_board_empty_symbols(self):
        """Price board with empty list returns DataFrame."""
        api = BulkAPI(source="AUTO", show_log=False)
        # Empty list should not crash
        df = api.price_board([])
        assert isinstance(df, pd.DataFrame)

    def test_market_bulk_property(self):
        """Market(auto=True).bulk returns BulkAPI."""
        mkt = Market(auto=True, show_log=False)
        bulk = mkt.bulk
        assert isinstance(bulk, BulkAPI)
        assert bulk.source == "AUTO"
        assert bulk.show_log is False

    def test_market_bulk_property_with_source(self):
        """Market(source='KBS').bulk returns BulkAPI with KBS source."""
        mkt = Market(source="KBS", show_log=False)
        bulk = mkt.bulk
        assert isinstance(bulk, BulkAPI)
        assert bulk.source == "KBS"

    def test_bulk_api_has_provider_pool(self):
        """BulkAPI has provider pool initialized."""
        api = BulkAPI(show_log=False)
        assert api._provider_pool is not None
        providers = api._provider_pool.get_available_providers("quote")
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_bulk_api_has_routers(self):
        """BulkAPI has health and bulk routers initialized."""
        api = BulkAPI(show_log=False)
        assert api._health_router is not None
        assert api._bulk_router is not None


# ---------------------------------------------------------------------------
# T1/T3/R4/R5/D3/D7 — BulkAPI thực sự lấy được dữ liệu
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.api
class TestBulkAPIDataPath:
    """AC-1, AC-4, AC-5, AC-6 và quyết định D3."""

    def test_ac1_history_returns_rows_and_names_real_provider(self, monkeypatch):
        """AC-1: với mọi đường mạng bị chặn và registry đã đầy, ``history``
        trả dữ liệu thật; ``attrs['sources_used']`` nêu đúng provider **thực sự**
        phục vụ, chứng minh bằng spy chứ không phải phỏng đoán."""
        _block_egress(monkeypatch)
        ProviderRegistry.register("quote", "servaa", _ServingProvider)
        _ServingProvider.calls = []
        api = _pool_with(monkeypatch, ["servaa"])

        df = api.history(["ACB", "VNM"], start="2024-01-01", end="2024-01-31")

        assert len(df) > 0, "bulk phải trả dữ liệu, không phải 0 dòng"
        assert df.attrs["returned"] == 2
        assert df.attrs["requested"] == 2
        assert df.attrs["failed"] == {}
        assert df.attrs["sources_used"] == {"ACB": "SERVAA", "VNM": "SERVAA"}
        assert sorted(df["symbol"].unique().tolist()) == ["ACB", "VNM"]
        # spy: provider được hỏi đúng batch, và frame đến từ chính nó
        assert _ServingProvider.calls == [(("ACB", "VNM"), "1D")]

    def test_ac1_real_registry_is_populated(self):
        """AC-2/T1: registry có provider thật ngay trong tiến trình lạnh."""
        available = ProviderRegistry.list_available("quote")
        assert available, "registry rỗng → toàn bộ đường bulk chết"
        assert {"vci", "kbs"} <= set(available)

    def test_ac4_all_providers_down_reports_failed(self, monkeypatch):
        """AC-4: mọi provider ném ``RuntimeError`` → ``attrs['failed']`` không
        rỗng và ``HealthRouter.record_failure`` được gọi."""
        _block_egress(monkeypatch)
        ProviderRegistry.register("quote", "downxx", _DownProvider)
        api = _pool_with(monkeypatch, ["downxx"])

        recorded: list = []
        original = api._health_router.record_failure

        def spy_failure(provider, error, module="quote"):
            recorded.append((provider, module))
            return original(provider, error, module=module)

        api._health_router.record_failure = spy_failure

        df = api.history(["ACB", "VNM"], start="2024-01-01", end="2024-01-31")

        assert df.empty
        assert df.attrs["failed"], "lỗi provider phải được báo ra, không nuốt im lặng"
        assert "DOWNXX" in df.attrs["failed"]
        assert ("DOWNXX", "quote") in recorded

    def test_ac5_interval_forwarded_to_router(self, monkeypatch):
        """AC-5: ``interval`` từ ``BulkAPI.history`` phải đi tới
        ``BulkRouter.fetch_history``."""
        seen: dict = {}
        original = BulkAPI(source="AUTO", show_log=False)._bulk_router.fetch_history

        def spy(symbols, start=None, end=None, module="quote", **kwargs):
            seen.update(kwargs)
            seen["module"] = module
            return original(symbols, start, end, module, **kwargs)

        api = BulkAPI(source="AUTO", show_log=False)
        monkeypatch.setattr(api._bulk_router, "fetch_history", spy)

        api.history(["ACB"], start="2024-01-01", end="2024-01-31", interval="1m")

        assert seen.get("interval") == "1m"
        assert seen.get("module") == "quote"

    def test_ac6_price_board_honours_self_source(self, monkeypatch):
        """AC-6/D7: cả ``Trading`` và ``Listing`` đều phải dùng ``self.source``,
        không còn ``source="KBS"`` hardcode trong ``bulk.py``."""
        import vnbroker.common.data as data_module

        created: list = []

        class _FakeListing:
            def __init__(self, source, show_log):
                created.append(("Listing", source))
                self.source = source

            def all_symbols(self):
                return pd.DataFrame({"symbol": ["ACB", "VNM"]})

        class _FakeTrading:
            def __init__(self, source, show_log):
                created.append(("Trading", source))
                self.source = source

            def price_board(self, symbols):
                return pd.DataFrame({"symbol": symbols})

        monkeypatch.setattr(data_module, "Listing", _FakeListing)
        monkeypatch.setattr(data_module, "Trading", _FakeTrading)

        api = BulkAPI(source="VCI", show_log=False)

        # Nhánh có truyền symbols
        api.price_board(["ACB"])
        # Nhánh symbols=None đi qua Listing
        api.price_board(None)

        # Thứ tự dựng đối tượng không phải điều kiện; điều cần chứng minh là
        # KHÔNG component nào nhận source khác `self.source`.
        assert created, "price_board phải dựng component"
        assert all(source == "VCI" for _, source in created), (
            f"price_board không theo self.source: {created}"
        )
        assert {name for name, _ in created} == {"Trading", "Listing"}

    def test_ac6_price_board_module_has_no_hardcoded_source(self):
        """AC-6/D7: không còn ``source="KBS"`` hardcode trong ``bulk.py``."""
        import inspect as _inspect

        from vnbroker.api import bulk as bulk_module

        source = _inspect.getsource(bulk_module)
        assert 'source="KBS"' not in source
        assert "source='KBS'" not in source

    def test_d3_empty_pool_raises_connection_error(self, monkeypatch):
        """D3: nhánh ``raise ConnectionError`` phải thật sự reachable — pool
        rỗng thì báo lỗi, thay vì chỉ là dead code như ở ``e5d8133``."""
        _block_egress(monkeypatch)
        api = _pool_with(monkeypatch, [])

        with pytest.raises(ConnectionError, match="No providers available"):
            api.history(["ACB"], start="2024-01-01", end="2024-01-31")

    def test_d3_pool_provider_without_implementation_raises(self, monkeypatch):
        """D3: pool có provider nhưng registry không có implementation →
        báo lỗi rõ ràng thay vì báo thành công rỗng."""
        _block_egress(monkeypatch)
        api = _pool_with(monkeypatch, ["khongco"])

        with pytest.raises(ConnectionError, match="No registered provider"):
            api.history(["ACB"], start="2024-01-01", end="2024-01-31")

    def test_d3_pool_drives_provider_selection(self, monkeypatch):
        """D3: ``ProviderPool`` thật sự là nguồn danh sách provider, không phải
        một lời gọi bị bỏ không."""
        _block_egress(monkeypatch)
        ProviderRegistry.register("quote", "poolaa", _ServingProvider)
        _ServingProvider.calls = []
        api = _pool_with(monkeypatch, ["poolaa"])

        df = api.history(["ACB"], start="2024-01-01", end="2024-01-31")

        assert df.attrs["returned"] == 1
        assert _ServingProvider.calls == [(("ACB",), "1D")]

    def test_bulk_api_history_signature_unchanged(self):
        """AC-11: thứ tự tham số vị trí của ``BulkAPI.history`` không đổi."""
        params = [
            name
            for name, p in inspect.signature(BulkAPI.history).parameters.items()
            if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        ]
        assert params == ["self", "symbols", "start", "end", "interval"]
