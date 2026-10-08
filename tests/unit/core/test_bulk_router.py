"""Tests for BulkRouter and HealthRouter (WP-3).

Phần T1/T2/T3/R4/R5 (xem docs/PLAN_TIER1_ENGINE_v3.md §4 AC-1..AC-5) được
thêm ở cuối file: chúng bảo vệ đúng những chỗ từng nuốt lỗi.
"""

from __future__ import annotations

import inspect
import time

import pandas as pd
import pytest

from vnbroker.core import source_router
from vnbroker.core.bulk_router import BulkRouter
from vnbroker.core.health_router import HealthRouter
from vnbroker.core.registry import ProviderRegistry


@pytest.fixture(autouse=True)
def _clean_router(monkeypatch):
    monkeypatch.setenv("vnbroker_ROUTER_HEALTH_DB", "memory")
    source_router.reload_store()
    source_router.reset_router_state()
    yield
    source_router.reset_router_state()
    source_router.reload_store()


def _frame(symbol: str, rows: int = 2) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=rows, freq="D"),
            "open": [10.0] * rows,
            "high": [11.0] * rows,
            "low": [9.0] * rows,
            "close": [10.5] * rows,
            "volume": [1000] * rows,
        }
    )
    df.attrs["symbol"] = symbol
    return df


def _block_egress(monkeypatch) -> None:
    """Chặn MỌI đường thoát ra mạng.

    ``requests.Session.request`` không đủ: VCI đi qua
    ``vnbroker.core.utils.async_send_request`` (aiohttp), nên chỉ chặn
    requests thì VCI vẫn ra ngoài và test thành phụ thuộc mạng thật.
    """
    import requests

    def _no_network(*args, **kwargs):
        raise requests.exceptions.ConnectionError("EGRESS BLOCKED BY TEST")

    async def _no_network_async(*args, **kwargs):
        raise ConnectionError("EGRESS BLOCKED BY TEST")

    monkeypatch.setattr(requests.Session, "request", _no_network)
    monkeypatch.setattr("vnbroker.core.utils.async_send_request", _no_network_async)


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

    def mock_fetch_batch(provider, symbols, start, end, module, interval="1D"):
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

    def mock_fetch_batch(provider, symbols, start, end, module, interval="1D"):
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

    def mock_fetch_batch(provider, symbols, start, end, module, interval="1D"):
        if provider == "VCI":
            raise ConnectionError("VCI is down")
        return [pd.DataFrame({"symbol": symbols})]

    router._fetch_batch = mock_fetch_batch

    symbols = ["ACB", "BID", "CTG", "DPG"]
    result = router.fetch_history(symbols, "2024-01-01", "2024-12-31", module="quote")

    # Should have partial results
    assert "VCI" in result["errors"]
    assert result["symbols_returned"] > 0  # kbs should have succeeded


# ---------------------------------------------------------------------------
# T1/T2/T3/R4/R5 — bulk thực sự gọi được provider
# (PLAN_TIER1_ENGINE_v3.md §4 AC-1..AC-5)
# ---------------------------------------------------------------------------


class _SpyProvider:
    """Provider class giả, ghi lại mọi lần được gọi.

    AC-1 yêu cầu chứng minh bằng spy provider nào **thực sự** phục vụ frame,
    không được suy ra từ việc provider khác không được gọi.
    """

    calls: list = []

    @classmethod
    def fetch_multiple(cls, symbols, start=None, end=None, interval="1D"):
        cls.calls.append(("fetch_multiple", tuple(symbols), interval))
        return [_frame(sym) for sym in symbols]


class _AsyncSpyProvider:
    """Hình dạng provider của VCI: ``fetch_multiple`` là ``async classmethod``."""

    calls: list = []

    @classmethod
    async def fetch_multiple(cls, symbols, start=None, end=None, interval="1D"):
        cls.calls.append(("async_fetch_multiple", tuple(symbols), interval))
        return [_frame(sym) for sym in symbols]


class _HistoryOnlyProvider:
    """Không có ``fetch_multiple`` — buộc router đi nhánh ``history``."""

    calls: list = []

    def __init__(self, symbol: str):
        self.symbol = symbol
        type(self).calls.append(symbol)

    def history(self, start=None, end=None, interval="1D"):
        return _frame(self.symbol)


class _BrokenCtorProvider:
    """Lỗi lập trình: dựng instance không đủ tham số."""

    def __init__(self):
        raise TypeError("__init__() missing 1 required positional argument: 'symbol'")


class _MisboundSelfProvider:
    """Lỗi lập trình T2: ``history`` bị gọi không đúng ``self``.

    ``history`` trên provider thật không có tham số ``symbol``; nếu ai đó gọi
    nó trên **class** thì ``self`` bị bind vào chuỗi symbol và dòng đầu tiên
    chạm vào thuộc tính sẽ ném ``AttributeError``.
    """

    calls: list = []

    def __init__(self, symbol: str):
        self.symbol = symbol
        self._probe()
        type(self).calls.append(symbol)

    def _probe(self):
        # Giống hệt provider thật: chạm vào thuộc tính của self.
        _ = self.symbol

    def history(self, start=None, end=None, interval="1D"):
        return _frame(self.symbol)


class _AttributeErrorProvider:
    """Provider ném ``AttributeError`` — phải nổi lên, không bị nuốt."""

    def __init__(self, symbol: str):
        self.symbol = symbol

    def history(self, start=None, end=None, interval="1D"):
        raise AttributeError("'str' object has no attribute 'symbol'")


def _register(name: str, provider_class: type) -> str:
    """Đăng ký provider giả và trả về tên viết hoa của nó."""
    ProviderRegistry.register("quote", name, provider_class)
    provider_class.calls = []
    return name.upper()


def _router_with_only_real_providers_down() -> BulkRouter:
    """Router mà vci/kbs đang cooldown, provider giả là lựa chọn duy nhất."""
    hr = HealthRouter()
    for real in ("vci", "kbs"):
        hr.record_failure(real, ConnectionError("cooldown for test"), module="quote")
    return BulkRouter(health_router=hr)


def test_ac1_fetch_multiple_sync_provider_returns_rows(monkeypatch):
    """AC-1: bulk trả DỮ LIỆU, spy chứng minh đúng provider đã phục vụ."""
    _block_egress(monkeypatch)
    name = _register("spy1", _SpyProvider)
    router = _router_with_only_real_providers_down()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote", providers=[name]
    )

    assert result["errors"] == {}
    assert result["providers_used"] == [name]
    assert result["symbols_returned"] == 2
    assert all(not df.empty for frames in result["results"].values() for df in frames)
    # spy: đúng provider, đúng batch symbol, đúng interval
    assert _SpyProvider.calls == [("fetch_multiple", ("ACB", "VNM"), "1D")]


def test_ac1_async_fetch_multiple_is_awaited(monkeypatch):
    """AC-1/T3: ``fetch_multiple`` async của VCI phải được await.

    Không có bridge thì hàm trả coroutine, ``isinstance(result, list)`` và
    ``isinstance(result, dict)`` đều False nên batch rỗng bị coi là thành công.
    """
    _block_egress(monkeypatch)
    name = _register("spyasync", _AsyncSpyProvider)
    router = _router_with_only_real_providers_down()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote", providers=[name]
    )

    assert result["errors"] == {}
    assert result["symbols_returned"] == 2
    assert _AsyncSpyProvider.calls == [("async_fetch_multiple", ("ACB", "VNM"), "1D")]


def test_ac2_real_providers_registered_in_cold_process():
    """AC-2: provider thật phải tra được mà không cần ai import explorer trước."""
    assert ProviderRegistry.list_available("quote"), (
        "registry rỗng → ProviderRegistry.get() ném ValueError cho mọi provider"
    )
    for name in ("vci", "kbs"):
        assert ProviderRegistry.get("quote", name) is not None


def test_ac3_constructor_type_error_propagates():
    """AC-3: lỗi lập trình phải nổi lên, không đổi thành logger.warning."""
    name = _register("brokenaaa", _BrokenCtorProvider)
    router = _router_with_only_real_providers_down()

    with pytest.raises(TypeError):
        router.fetch_history(
            ["ACB"], "2024-01-01", "2024-01-31", module="quote", providers=[name]
        )


def test_ac3_misbound_self_is_not_reproduced():
    """AC-3/T2: ``history`` phải được gọi trên **instance** dựng đúng.

    Nếu router dựng ``provider_class()`` (thiếu ``symbol`` → TypeError) hoặc
    gọi ``history`` trên class thì ``self`` là chuỗi symbol và dòng
    ``self.symbol`` ném ``AttributeError``.
    """
    name = _register("mselfp", _MisboundSelfProvider)
    router = _router_with_only_real_providers_down()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote", providers=[name]
    )

    assert result["errors"] == {}
    assert result["symbols_returned"] == 2
    assert sorted(_MisboundSelfProvider.calls) == ["ACB", "VNM"]


def test_ac3_attribute_error_propagates():
    """AC-3: ``AttributeError`` từ provider phải nổi lên tới caller."""
    name = _register("attrerrr", _AttributeErrorProvider)
    router = _router_with_only_real_providers_down()

    with pytest.raises(AttributeError):
        router.fetch_history(
            ["ACB"], "2024-01-01", "2024-01-31", module="quote", providers=[name]
        )


def test_ac4_all_providers_runtime_error_is_reported():
    """AC-4: mọi provider ném ``RuntimeError`` (lỗi mạng) → ``errors`` có giá
    trị VÀ ``HealthRouter.record_failure`` được gọi, tức lỗi không bị nuốt
    trong ``_fetch_batch``."""

    class _Down:
        @classmethod
        def fetch_multiple(cls, symbols, start=None, end=None, interval="1D"):
            raise RuntimeError("network unreachable")

    names = [_register("downaaa", _Down), _register("downbbb", _Down)]
    router = _router_with_only_real_providers_down()

    recorded: list = []
    original = router._health.record_failure

    def spy_failure(provider, error, module="quote"):
        recorded.append((provider, module))
        return original(provider, error, module=module)

    router._health.record_failure = spy_failure

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote", providers=names
    )

    assert set(result["errors"]) == set(names)
    assert all("network unreachable" in msg for msg in result["errors"].values())
    assert result["symbols_returned"] == 0
    assert {provider for provider, _ in recorded} == set(names)
    assert {module for _, module in recorded} == {"quote"}


def test_ac4_empty_result_counts_as_provider_failure():
    """AC-4: provider nuốt lỗi rồi trả list rỗng vẫn phải bị báo thất bại.
    KBS ``fetch_multiple`` chính là hình dạng này."""

    class _Silent:
        @classmethod
        def fetch_multiple(cls, symbols, start=None, end=None, interval="1D"):
            return []

    name = _register("silentc", _Silent)
    router = _router_with_only_real_providers_down()

    result = router.fetch_history(
        ["ACB"], "2024-01-01", "2024-01-31", module="quote", providers=[name]
    )

    assert name in result["errors"], "list rỗng phải là thất bại, không phải thành công"


def test_ac5_interval_is_keyword_only_after_module():
    """AC-5: ``interval`` phải là keyword-only đặt SAU ``module`` để thứ tự
    tham số vị trí không đổi (AC-11)."""
    signature = inspect.signature(BulkRouter.fetch_history)
    interval_param = signature.parameters["interval"]
    assert interval_param.kind is inspect.Parameter.KEYWORD_ONLY
    assert interval_param.default == "1D"

    positional = [
        name
        for name, p in signature.parameters.items()
        if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]
    assert positional == ["self", "symbols", "start", "end", "module"]


def test_ac5_interval_reaches_provider(monkeypatch):
    """AC-5: giá trị ``interval`` đi tới ``fetch_multiple`` của provider."""
    _block_egress(monkeypatch)
    name = _register("spyint", _SpyProvider)
    router = _router_with_only_real_providers_down()

    router.fetch_history(
        ["ACB"],
        "2024-01-01",
        "2024-01-31",
        module="quote",
        interval="1m",
        providers=[name],
    )

    assert _SpyProvider.calls == [("fetch_multiple", ("ACB",), "1m")]


def test_history_fallback_passes_symbol_to_constructor():
    """T2: ``__init__`` cần ``symbol``; gọi thiếu sẽ ``TypeError``."""
    name = _register("histonly", _HistoryOnlyProvider)
    router = _router_with_only_real_providers_down()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote", providers=[name]
    )

    assert result["errors"] == {}
    assert result["symbols_returned"] == 2
    assert sorted(_HistoryOnlyProvider.calls) == ["ACB", "VNM"]


def test_normalize_multi_result_rejects_unknown_type():
    """Giá trị trả về không nhận diện được phải nổi lên, không bị bơm thành rỗng."""

    class _Weird:
        @classmethod
        def fetch_multiple(cls, symbols, start=None, end=None, interval="1D"):
            return "not-a-frame"

    name = _register("weirdd", _Weird)
    router = _router_with_only_real_providers_down()

    with pytest.raises(TypeError):
        router.fetch_history(
            ["ACB"], "2024-01-01", "2024-01-31", module="quote", providers=[name]
        )


def test_unregistered_provider_is_skipped_with_warning(caplog):
    """Provider healthy nhưng chưa đăng ký: bỏ qua kèm cảnh báo, không im lặng
    trả 0 frame trông như thành công."""
    name = _register("ghostpr", _SpyProvider)
    router = _router_with_only_real_providers_down()
    ProviderRegistry._registry.pop(("quote", "ghostpr"), None)

    result = router.fetch_history(
        ["ACB"], "2024-01-01", "2024-01-31", module="quote", providers=[name]
    )

    assert result["symbols_returned"] == 0
    assert "not registered" in caplog.text.lower()
