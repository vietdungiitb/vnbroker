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
    """Cô lập health store **và registry** cho mọi test trong file.

    Không có health fixture thì một test ghi ``record_failure`` sẽ đẩy vci/kbs vào
    cooldown và làm các test chạy sau nhận ``ConnectionError``.

    Phần registry là bắt buộc vì ``ProviderRegistry`` là singleton toàn cục:
    MAJOR-5 buộc provider giả phải cài vào slot AUTO thật (``vci``) để quan sát
    được health snapshot, mà slot đó cũng chính là slot provider thật. Không khôi
    phục lại thì ``_DownProvider`` (ném ``RuntimeError("network unreachable")``) sống
    tới hết phiên và làm ``test_quote_price_unit_consistency`` chết bằng
    ``tenacity.RetryError`` — đã quan sát thật trước khi thêm fixture này.
    """
    from vnbroker.core.registry import ProviderRegistry

    monkeypatch.setenv("vnbroker_ROUTER_HEALTH_DB", "memory")
    source_router.reload_store()
    source_router.reset_router_state()
    saved_registry = dict(ProviderRegistry._registry)
    yield
    ProviderRegistry._registry.clear()
    ProviderRegistry._registry.update(saved_registry)
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
    """Provider giả phục vụ đủ mọi symbol, có ghi lại lời gọi (spy của AC-1).

    MAJOR-4: có ``history`` + ``parallel`` + ``__init__(symbol)`` giống provider
    thật. Fake chỉ có ``fetch_multiple`` sẽ chết vì ``TypeError`` ở
    ``provider_class(symbol=...)`` — tức test chết vì hình dạng sai.
    """

    calls: list = []

    def __init__(self, symbol=None):
        self.symbol = symbol

    def history(
        self,
        start=None,
        end=None,
        interval="1D",
        parallel=False,
        symbols=None,
        **kwargs,
    ):
        targets = list(symbols or ([self.symbol] if self.symbol else []))
        type(self).calls.append((tuple(targets), interval))
        return [_frame(sym) for sym in targets]


class _DownProvider:
    calls: list = []

    def __init__(self, symbol=None):
        self.symbol = symbol

    def history(
        self,
        start=None,
        end=None,
        interval="1D",
        parallel=False,
        symbols=None,
        **kwargs,
    ):
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
        """AC-4: mọi provider ném ``RuntimeError`` → ``attrs['failed']`` không rỗng
        VÀ lỗi **tới được** health store.

        MAJOR-5: test cũ spy ``HealthRouter.record_failure`` rồi assert
        ``("DOWNXX", "quote") in recorded``. Đó chỉ chứng minh *hàm được gọi*, và
        nó vẫn xanh cả khi bulk ghi sai khoá health store vì spy forward sang bản
        thật. Nay khẳng định hậu quả thật trên ``get_source_health_snapshot``.

        Provider giả phải cài vào slot AUTO thật (``vci``): snapshot chỉ liệt kê
        ``get_auto_candidates('quote')``, nên "sức khoẻ của provider lạ" như
        ``downxx`` vốn không quan sát được từ đâu cả.
        """
        _block_egress(monkeypatch)
        ProviderRegistry.register("quote", "vci", _DownProvider)
        api = _pool_with(monkeypatch, ["vci"])

        df = api.history(["ACB", "VNM"], start="2024-01-01", end="2024-01-31")

        assert df.empty
        assert df.attrs["failed"], "lỗi provider phải được báo ra, không nuốt im lặng"
        assert "VCI" in df.attrs["failed"]

        snapshot = source_router.get_source_health_snapshot("quote")
        assert snapshot["VCI"]["failures"] > 0, (
            f"lỗi không tới được health store (failures={snapshot['VCI']['failures']})"
        )
        assert snapshot["VCI"]["in_cooldown"] is True

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

    def test_d3_pool_is_never_empty_so_empty_pool_branch_is_dead_code(self):
        """D3/MAJOR-5: nhánh ``raise ConnectionError("No providers available")``
        ở ``bulk.py:72`` **chưa reachable**, và test cũ đã che điều đó.

        ``test_d3_empty_pool_raises_connection_error`` (đã xoá) monkeypatch
        ``get_available_providers`` trả ``[]``. Nhưng ``NO_AUTH_PROVIDERS`` là
        list hardcode ``["vci", "kbs"]`` nên hàm luôn trả ít nhất 2 phần tử —
        test xanh ở **cả commit gốc**, tức nó không chứng minh được gì về
        reachability. Không được dùng nó làm bằng chứng cho bất kỳ fix nào.

        Test thay thế khẳng định điều kiện thật: pool luôn khác rỗng. Nếu ai đó
        làm rỗng ``NO_AUTH_PROVIDERS`` thì test này ĐỎ, buộc phải xét lại nhánh
        dead code kia.
        """
        from vnbroker.core.provider_pool import ProviderPool

        assert list(ProviderPool.NO_AUTH_PROVIDERS), (
            "NO_AUTH_PROVIDERS rỗng → nhánh ConnectionError ở bulk.py:72 trở nên "
            "reachable; phải viết lại test cho nhánh đó"
        )
        assert ProviderPool().get_available_providers("quote")

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
