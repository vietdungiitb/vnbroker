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
#
# Provider giả được cài vào đúng slot 'vci'/'kbs' của AUTO candidates thay vì
# dùng tham số `providers=` mới. Lý do: nếu test chỉ dựa vào tham số mới thì
# ở e5d8133 nó chết vì "unexpected keyword argument" chứ không phải vì hành vi
# sai — đó là bằng chứng AC-12 yếu, và `pytest.raises(TypeError)` còn nuốt luôn
# chính lỗi đó khiến test xanh sai. Cài vào slot thật thì lỗi pre-fix là lỗi
# hành vi thật.
# ---------------------------------------------------------------------------


class _SpyProvider:
    """Provider class giả, ghi lại mọi lần được gọi.

    AC-1 yêu cầu chứng minh bằng spy provider nào **thực sự** phục vụ frame,
    không được suy ra từ việc provider khác không được gọi.

    ``__init__`` yêu cầu ``symbol`` giống hệt VCI/KBS thật — nếu để
    ``__init__`` không tham số thì ``provider_class()`` ở e5d8133 lại chạy
    được và test xanh sai.
    """

    calls: list = []

    def __init__(self, symbol: str):
        self.symbol = symbol

    @classmethod
    def fetch_multiple(cls, symbols, start=None, end=None, interval="1D"):
        cls.calls.append(("fetch_multiple", tuple(symbols), interval))
        return [_frame(sym) for sym in symbols]


class _AsyncSpyProvider:
    """Hình dạng provider của VCI: ``fetch_multiple`` là ``async classmethod``."""

    calls: list = []

    def __init__(self, symbol: str):
        self.symbol = symbol

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
    """Lỗi lập trình: dựng instance thiếu tham số bắt buộc."""

    def __init__(self):
        raise TypeError("__init__() missing 1 required positional argument: 'symbol'")


class _MisboundSelfProvider:
    """Bắt lỗi T2 'mis-bound self'.

    ``history`` trên provider thật không có tham số ``symbol``; nếu ai đó gọi
    nó trên **class** thì ``self`` bị bind vào chuỗi symbol. Dòng đầu tiên
    chạm vào thuộc tính sẽ ném ``AttributeError`` — y hệt dấu hiệu ban đầu.
    """

    calls: list = []

    def __init__(self, symbol: str):
        self.symbol = symbol
        self._probe()
        type(self).calls.append(symbol)

    def _probe(self):
        _ = self.symbol  # giống provider thật: chạm thuộc tính của self

    def history(self, start=None, end=None, interval="1D"):
        return _frame(self.symbol)


class _AttributeErrorProvider:
    """Provider ném ``AttributeError`` — phải nổi lên, không bị nuốt."""

    def __init__(self, symbol: str):
        self.symbol = symbol

    def history(self, start=None, end=None, interval="1D"):
        raise AttributeError("'str' object has no attribute 'symbol'")


def _install_as_vci(provider_class: type) -> None:
    """Cài provider giả vào slot ``vci`` và đẩy ``kbs`` vào cooldown.

    ``get_source_health_snapshot('quote')`` chỉ liệt kê AUTO candidates
    (``vci``, ``kbs``), nên provider lạ không bao giờ xuất hiện trong health
    snapshot. Cài vào slot thật giữ được cả hành vi cũ lẫn mới.
    """
    ProviderRegistry.register("quote", "vci", provider_class)
    provider_class.calls = []
    HealthRouter().record_failure("kbs", ConnectionError("cooldown"), module="quote")


def _router_for_vci() -> BulkRouter:
    hr = HealthRouter()
    hr.record_failure("kbs", ConnectionError("cooldown"), module="quote")
    return BulkRouter(health_router=hr)


def test_ac1_fetch_multiple_sync_provider_returns_rows(monkeypatch):
    """AC-1: bulk trả DỮ LIỆU, spy chứng minh đúng provider đã phục vụ."""
    _block_egress(monkeypatch)
    _install_as_vci(_SpyProvider)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert result["errors"] == {}
    assert result["providers_used"] == ["VCI"]
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
    _install_as_vci(_AsyncSpyProvider)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
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
    """AC-3: lỗi lập trình phải nổi lên, không đổi thành logger.warning.

    Gọi thẳng ``_fetch_batch`` để lỗi không bị che bởi tham số mới: ở e5d8133
    ``except Exception`` ở :136 nuốt TypeError rồi trả list rỗng.
    """
    ProviderRegistry.register("quote", "vci", _BrokenCtorProvider)
    router = _router_for_vci()

    with pytest.raises(TypeError):
        router._fetch_batch("VCI", ["ACB"], "2024-01-01", "2024-01-31", "quote")


def test_ac3_misbound_self_is_not_reproduced():
    """AC-3/T2: ``history`` phải được gọi trên **instance** dựng đúng.

    Nếu router dựng ``provider_class()`` (thiếu ``symbol`` → TypeError) hoặc gọi
    ``history`` trên class thì ``self`` là chuỗi symbol và dòng ``self.symbol``
    ném ``AttributeError``.
    """
    _install_as_vci(_MisboundSelfProvider)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert result["errors"] == {}
    assert result["symbols_returned"] == 2
    assert sorted(_MisboundSelfProvider.calls) == ["ACB", "VNM"]


def test_ac3_attribute_error_propagates():
    """AC-3: ``AttributeError`` từ provider phải nổi lên tới caller."""
    ProviderRegistry.register("quote", "vci", _AttributeErrorProvider)
    router = _router_for_vci()

    with pytest.raises(AttributeError):
        router._fetch_batch("VCI", ["ACB"], "2024-01-01", "2024-01-31", "quote")


def test_ac4_all_providers_runtime_error_is_reported():
    """AC-4: mọi provider ném ``RuntimeError`` (lỗi mạng) → ``errors`` có giá
    trị VÀ ``HealthRouter.record_failure`` được gọi, tức lỗi không bị nuốt
    trong ``_fetch_batch``."""

    class _Down:
        @classmethod
        def fetch_multiple(cls, symbols, start=None, end=None, interval="1D"):
            raise RuntimeError("network unreachable")

    ProviderRegistry.register("quote", "vci", _Down)
    ProviderRegistry.register("quote", "kbs", _Down)
    router = BulkRouter(health_router=HealthRouter())

    recorded: list = []
    original = router._health.record_failure

    def spy_failure(provider, error, module="quote"):
        recorded.append((provider, module))
        return original(provider, error, module=module)

    router._health.record_failure = spy_failure

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert set(result["errors"]) == {"VCI", "KBS"}
    assert all("network unreachable" in msg for msg in result["errors"].values())
    assert result["symbols_returned"] == 0
    assert {provider for provider, _ in recorded} == {"VCI", "KBS"}
    assert {module for _, module in recorded} == {"quote"}


def test_ac4_empty_result_counts_as_provider_failure():
    """AC-4: provider nuốt lỗi rồi trả list rỗng vẫn phải bị báo thất bại.
    KBS ``fetch_multiple`` chính là hình dạng này."""

    class _Silent:
        @classmethod
        def fetch_multiple(cls, symbols, start=None, end=None, interval="1D"):
            return []

    ProviderRegistry.register("quote", "vci", _Silent)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert "VCI" in result["errors"], "list rỗng phải là thất bại, không phải thành công"


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
    _install_as_vci(_SpyProvider)
    router = _router_for_vci()

    router.fetch_history(
        ["ACB"], "2024-01-01", "2024-01-31", module="quote", interval="1m"
    )

    assert _SpyProvider.calls == [("fetch_multiple", ("ACB",), "1m")]


def test_ac5_fetch_batch_accepts_interval_positionally_last():
    """``_fetch_batch`` phải nhận ``interval`` và chuyển tiếp nó xuống provider."""
    _install_as_vci(_SpyProvider)
    router = _router_for_vci()

    router._fetch_batch("VCI", ["ACB"], "2024-01-01", "2024-01-31", "quote", "15m")

    assert _SpyProvider.calls == [("fetch_multiple", ("ACB",), "15m")]


def test_history_fallback_passes_symbol_to_constructor():
    """T2: ``__init__`` cần ``symbol``; gọi thiếu sẽ ``TypeError``."""
    _install_as_vci(_HistoryOnlyProvider)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
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

    ProviderRegistry.register("quote", "vci", _Weird)
    router = _router_for_vci()

    with pytest.raises(TypeError):
        router._fetch_batch("VCI", ["ACB"], "2024-01-01", "2024-01-31", "quote")


def test_unregistered_provider_is_skipped_with_warning(caplog):
    """Provider healthy nhưng chưa đăng ký: bỏ qua kèm cảnh báo, không im lặng
    trả 0 frame trông như thành công."""
    hr = HealthRouter()
    hr.record_failure("kbs", ConnectionError("cooldown"), module="quote")
    hr.record_success("ghostpr", 1.0, module="quote")
    router = BulkRouter(health_router=hr)

    result = router._fetch_batch(
        "GHOSTPR", ["ACB"], "2024-01-01", "2024-01-31", "quote"
    )

    assert result == []
    assert "not registered" in caplog.text.lower()


def test_explicit_providers_argument_narrows_to_healthy(monkeypatch):
    """Tham số ``providers`` mới: danh sách của caller là chuẩn, health store
    chỉ dùng để loai provider đang cooldown."""
    _install_as_vci(_SpyProvider)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB"],
        "2024-01-01",
        "2024-01-31",
        module="quote",
        providers=["vci", "kbs"],
    )

    # kbs đang cooldown nên bị loại, chỉ vci chạy
    assert result["providers_used"] == ["VCI"]
    assert _SpyProvider.calls == [("fetch_multiple", ("ACB",), "1D")]


def test_explicit_providers_all_unhealthy_raises(monkeypatch):
    """Mọi provider được chỉ định đều cooldown → ConnectionError."""
    hr = HealthRouter()
    hr.record_failure("vci", ConnectionError("cooldown"), module="quote")
    hr.record_failure("kbs", ConnectionError("cooldown"), module="quote")
    router = BulkRouter(health_router=hr)

    with pytest.raises(ConnectionError, match="No healthy providers"):
        router.fetch_history(
            ["ACB"], "2024-01-01", "2024-01-31", module="quote", providers=["vci", "kbs"]
        )
