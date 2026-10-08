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
    """Cô lập health store **và registry** cho mọi test trong file.

    ``ProviderRegistry`` là singleton toàn cục, còn ``_install_as_vci`` cài
    provider giả vào đúng slot ``vci``. Không khôi phục lại thì provider giả sống
    tới hết phiên và làm các test chạy sau (kể cả file khác) nhận nhầm provider.
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
        # MAJOR-1: `provider` là tên NỘI BỘ, khớp khoá health store (lower-case).
        if provider == "vci":
            raise ConnectionError("VCI is down")
        return [pd.DataFrame({"symbol": symbols})]

    router._fetch_batch = mock_fetch_batch

    symbols = ["ACB", "BID", "CTG", "DPG"]
    result = router.fetch_history(symbols, "2024-01-01", "2024-12-31", module="quote")

    # Khoá trả về cho `api/bulk.py` vẫn UPPER-CASE.
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


class _DownProvider:
    """Provider chết theo hình dạng VCI/KBS (có ``parallel``).

    MAJOR-4: mọi provider thật đều có ``history`` và ``__init__(symbol)``; fakes
    chỉ có ``fetch_multiple`` classmethod sẽ chết vì ``TypeError``, tức là test
    chết vì hình dạng sai chứ không vì hành vi sai.
    """

    calls: list = []

    def __init__(self, symbol: str):
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
        type(self).calls.append(tuple(symbols or []))
        raise RuntimeError("network unreachable")


class _SilentProvider:
    """Nuốt lỗi rồi trả list rỗng — hình dạng ``fetch_multiple`` của KBS."""

    calls: list = []

    def __init__(self, symbol: str):
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
        type(self).calls.append(tuple(symbols or []))
        return []


class _SpyProvider:
    """Provider class giả, ghi lại mọi lần được gọi.

    AC-1 yêu cầu chứng minh bằng spy provider nào **thực sự** phục vụ frame,
    không được suy ra từ việc provider khác không được gọi.

    ``__init__`` yêu cầu ``symbol`` giống hệt VCI/KBS thật — nếu để
    ``__init__`` không tham số thì ``provider_class()`` lại chạy được và test
    xanh sai.

    MAJOR-4: ``history`` có cả ``parallel`` và ``symbols`` như VCI/KBS/TCBS thật,
    nên bulk gọi đúng một lần cho cả batch thay vì gọi ``fetch_multiple`` qua
    bridge riêng.
    """

    calls: list = []

    def __init__(self, symbol: str):
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
        type(self).calls.append(("history", tuple(symbols or []), interval, parallel))
        return [_frame(sym) for sym in (symbols or [self.symbol])]


class _AsyncSpyProvider:
    """Hình dạng provider VCI: ``history`` đồng bộ nhưng bên trong gọi
    ``fetch_multiple`` bất đồng bộ qua ``asyncio.run``.

    MAJOR-4: bulk không còn tự await gì cả — ``explorer/vci/quote.py:496`` đã
    giữ sẵn bridge đó. Provider giả ở đây giữ đúng hình dạng đó để chứng minh
    bulk vẫn nhận được frame qua ``history`` bất cứ provider bên dưới là sync
    hay async.
    """

    calls: list = []

    def __init__(self, symbol: str):
        self.symbol = symbol

    @classmethod
    async def fetch_multiple(cls, symbols, **kwargs):
        return [_frame(sym) for sym in symbols]

    def history(
        self,
        start=None,
        end=None,
        interval="1D",
        parallel=False,
        symbols=None,
        **kwargs,
    ):
        import asyncio

        targets = symbols or [self.symbol]
        type(self).calls.append(("history", tuple(targets), interval, parallel))
        return asyncio.run(type(self).fetch_multiple(symbols=targets))


class _HistoryOnlyProvider:
    """``history`` KHÔNG có ``parallel``/``symbols`` — hình dạng SSI/DNSE."""

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


def test_ac1_parallel_history_returns_rows(monkeypatch):
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
    assert _SpyProvider.calls == [("history", ("ACB", "VNM"), "1D", True)]


def test_ac1_async_provider_underneath_still_yields_rows(monkeypatch):
    """AC-1/T3: provider có ``fetch_multiple`` bất đồng bộ bên dưới vẫn ra frame.

    MAJOR-4: bulk không tự await gì — ``explorer/vci/quote.py:496`` đã giữ sẵn
    bridge đó trong ``history``. Test giữ đúng hình dạng đó (history đồng bộ,
    fetch_multiple bất đồng bộ) để chứng minh lớp `core` không còn phụ thuộc
    vào việc tự quản lý event loop.
    """
    _block_egress(monkeypatch)
    _install_as_vci(_AsyncSpyProvider)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert result["errors"] == {}
    assert result["symbols_returned"] == 2
    assert _AsyncSpyProvider.calls == [("history", ("ACB", "VNM"), "1D", True)]


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
    trị VÀ lỗi đó **tới được** health store (snapshot thấy failures>0 và
    cooldown), tức lỗi không bị nuốt trong ``_fetch_batch``."""
    ProviderRegistry.register("quote", "vci", _DownProvider)
    ProviderRegistry.register("quote", "kbs", _DownProvider)
    router = BulkRouter(health_router=HealthRouter())

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert set(result["errors"]) == {"VCI", "KBS"}
    assert all("network unreachable" in msg for msg in result["errors"].values())
    assert result["symbols_returned"] == 0

    # MAJOR-5: khẳng định HẬU QUẢ, không phải "hàm có được gọi không".
    # Spy `record_failure` trước đây vẫn xanh kể cả khi bulk ghi sai khoá
    # health store, vì nó forward sang bản thật — test chứng minh vô nghĩa.
    snapshot = source_router.get_source_health_snapshot("quote")
    for provider in ("VCI", "KBS"):
        assert snapshot[provider]["failures"] > 0, (
            f"{provider}: lỗi không tới được health store "
            f"(failures={snapshot[provider]['failures']})"
        )
        assert snapshot[provider]["in_cooldown"] is True


def test_ac4_empty_result_counts_as_provider_failure():
    """AC-4: provider nuốt lỗi rồi trả list rỗng vẫn phải bị báo thất bại.
    KBS ``fetch_multiple`` chính là hình dạng này."""
    ProviderRegistry.register("quote", "vci", _SilentProvider)
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
    """AC-5: giá trị ``interval`` đi tới ``history`` của provider."""
    _block_egress(monkeypatch)
    _install_as_vci(_SpyProvider)
    router = _router_for_vci()

    router.fetch_history(
        ["ACB"], "2024-01-01", "2024-01-31", module="quote", interval="1m"
    )

    assert _SpyProvider.calls == [("history", ("ACB",), "1m", True)]


def test_ac5_fetch_batch_accepts_interval_positionally_last():
    """``_fetch_batch`` phải nhận ``interval`` và chuyển tiếp nó xuống provider."""
    _install_as_vci(_SpyProvider)
    router = _router_for_vci()

    router._fetch_batch("VCI", ["ACB"], "2024-01-01", "2024-01-31", "quote", "15m")

    assert _SpyProvider.calls == [("history", ("ACB",), "15m", True)]


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
        def __init__(self, symbol: str):
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
            return "not-a-frame"

    ProviderRegistry.register("quote", "vci", _Weird)
    router = _router_for_vci()

    with pytest.raises(TypeError):
        router._fetch_batch("vci", ["ACB"], "2024-01-01", "2024-01-31", "quote")


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
    assert _SpyProvider.calls == [("history", ("ACB",), "1D", True)]


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


# ---------------------------------------------------------------------------
# MAJOR-1 — circuit breaker trên bulk path phải thật sự đóng
#
# `get_source_health_snapshot` đọc `_health_state[(module, s)]` với `s` lấy từ
# `get_auto_candidates` ('vci', 'kbs'). `_select_providers` trả tên UPPER-CASE
# nên `record_failure` ghi ('quote','VCI') — khoá mà snapshot KHÔNG đọc. Hệ quả:
# sau 6 lần bulk fail, failures=0, in_cooldown=False, circuit breaker không
# bao giờ đóng, và khoá chết vẫn được `_persist_state` ghi xuống SQLite.
#
# Test này khẳng định HẬU QUẢ (snapshot), không khẳng định "hàm có được gọi
# không" — spy kiểu AC-4 cũ vẫn xanh với key sai vì nó forward sang bản thật.
# ---------------------------------------------------------------------------


def test_bulk_failure_is_visible_in_health_snapshot():
    """MAJOR-1: failure của bulk phải hiện ra trong health snapshot."""

    ProviderRegistry.register("quote", "vci", _DownProvider)
    ProviderRegistry.register("quote", "kbs", _DownProvider)
    router = BulkRouter(health_router=HealthRouter())

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert set(result["errors"]) == {"VCI", "KBS"}

    snapshot = source_router.get_source_health_snapshot("quote")
    for provider in ("VCI", "KBS"):
        assert snapshot[provider]["failures"] > 0, (
            f"{provider}: health snapshot không thấy failure của bulk path "
            f"(failures={snapshot[provider]['failures']})"
        )
        assert snapshot[provider]["in_cooldown"] is True, (
            f"{provider}: circuit breaker chưa đóng"
        )


def test_bulk_failure_uses_health_store_key_that_snapshot_reads():
    """MAJOR-1: bulk không ghi khoá chết mà snapshot không đọc tới."""

    ProviderRegistry.register("quote", "vci", _DownProvider)
    ProviderRegistry.register("quote", "kbs", _DownProvider)
    router = BulkRouter(health_router=HealthRouter())
    router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    readable = set(source_router.get_auto_candidates("quote"))
    written = {source for module, source in source_router._health_state if module == "quote"}
    assert written <= readable, (
        f"bulk ghi khoá health store không ai đọc: {sorted(written - readable)}"
    )


def test_bulk_circuit_breaker_blocks_next_call_after_failure():
    """MAJOR-1: sau khi provider chết, lần gọi kế tiếp bị chặn thay vì thử lại."""

    ProviderRegistry.register("quote", "vci", _DownProvider)
    ProviderRegistry.register("quote", "kbs", _DownProvider)
    router = BulkRouter(health_router=HealthRouter())

    # 2 symbol: round-robin phải giao cho CẢ HAI provider, nếu không provider
    # còn lại chưa bao giờ hỏng thì circuit breaker chưa có lý do đóng.
    router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    with pytest.raises(ConnectionError, match="No healthy providers"):
        router.fetch_history(
            ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
        )


def test_bulk_returned_keys_stay_upper_case_for_api_layer():
    """MAJOR-1 sửa bằng lower-case nội bộ — khoá trả về KHÔNG được đổi.

    `api/bulk.py` đưa khoá này thẳng vào `attrs['sources_used']` và
    `attrs['failed']`, phải khớp `df.attrs['source']`.
    """
    _install_as_vci(_SpyProvider)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert result["providers_used"] == ["VCI"]
    assert set(result["results"]) == {"VCI"}


# ---------------------------------------------------------------------------
# MAJOR-2 — tiêu chí "không dùng được" phải là SCHEMA, không phải số dòng
#
# `common/data.py:442` phân biệt bằng schema: 0 cột = provider hỏng, đủ cột +
# 0 dòng = ngày nghỉch giao dịch = thành công. Bulk dùng tiêu chí "0 frame" và
# `_normalize_multi_result` lọc `not df.empty`, nên mọi ngày nghỉch đều bị quy
# thành provider chết — giống hệt nhau với provider thật sự hỏng.
# --------------------------------------------------------------------------


QUOTE_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


class _HolidayProvider:
    """Frame ĐÚNG schema nhưng 0 dòng — không có phiên giao dịch trong kỳ."""

    calls: list = []

    def __init__(self, symbol: str):
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
        targets = symbols or [self.symbol]
        type(self).calls.append(tuple(targets))
        return [pd.DataFrame(columns=QUOTE_COLUMNS) for _ in targets]


class _ZeroColumnProvider:
    """Frame 0 cột — provider không sinh ra cấu trúc."""

    calls: list = []

    def __init__(self, symbol: str):
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
        targets = symbols or [self.symbol]
        type(self).calls.append(tuple(targets))
        return [pd.DataFrame() for _ in targets]


def test_m2_well_shaped_zero_row_frame_is_success():
    """MAJOR-2: ngày nghỉch giao dịch KHÔNG phải lỗi provider."""
    _install_as_vci(_HolidayProvider)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert result["errors"] == {}, (
        f"ngày nghỉch giao dịch bị quy thành provider hỏng: {result['errors']}"
    )
    frames = result["results"]["VCI"]
    assert len(frames) == 2
    assert all(list(df.columns) == QUOTE_COLUMNS for df in frames)
    assert all(df.empty for df in frames)


def test_m2_well_shaped_zero_row_frame_does_not_mark_provider_unhealthy():
    """MAJOR-2: provider sống qua ngày nghỉch thì KHÔNG rơi vào cooldown."""
    _install_as_vci(_HolidayProvider)
    router = _router_for_vci()

    router.fetch_history(["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote")

    snapshot = source_router.get_source_health_snapshot("quote")
    assert snapshot["VCI"]["failures"] == 0
    assert snapshot["VCI"]["in_cooldown"] is False


def test_m2_zero_column_frame_is_failure():
    """MAJOR-2: 0 cột thì vẫn là provider hỏng — ranh giới nằm ở schema."""
    _install_as_vci(_ZeroColumnProvider)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert "VCI" in result["errors"], "frame 0 cột phải bị báo lỗi"
    assert "unusable" in result["errors"]["VCI"]


def test_m2_bulk_reuses_the_data_module_schema_criterion():
    """MAJOR-2: bulk dùng CHUNG helper với `common.data`, không viết lại.

    Nếu ai đó đổi tiêu chí ở một chỗ, chỗ kia phải đổi theo — nếu không hai
    đường đi lại lệch nhau và lỗi ngày nghỉch quay trở lại.
    """
    from vnbroker.common.data import _is_unusable_provider_result as data_criterion
    from vnbroker.core.bulk_router import _is_unusable

    cases = [
        None,
        pd.DataFrame(),
        pd.DataFrame(columns=QUOTE_COLUMNS),
        pd.DataFrame({"time": [1]}),
        [],
        (),
        {},
        {"a"},
        [pd.DataFrame(columns=QUOTE_COLUMNS)],
    ]
    for value in cases:
        assert _is_unusable(value) == data_criterion(value), (
            f"bulk va common.data lech tai {value!r}"
        )


def test_m2_history_path_treats_zero_row_frame_as_usable():
    """MAJOR-2: nhánh fallback `history` cũng phải giữ frame 0 dòng."""

    class _HistoryHoliday:
        def __init__(self, symbol: str):
            self.symbol = symbol

        def history(self, start=None, end=None, interval="1D"):
            return pd.DataFrame(columns=QUOTE_COLUMNS)

    ProviderRegistry.register("quote", "vci", _HistoryHoliday)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert result["errors"] == {}
    assert len(result["results"]["VCI"]) == 2


# ---------------------------------------------------------------------------
# MAJOR-4 — `core` không được import `api`; bridge thuộc về provider
#
# `core/bulk_router.py` từng import `call_provider_sync` từ `vnbroker.api.quote`
# để tự gọi `fetch_multiple` — tức là (a) tầng dưới leo lên tầng trên và
# (b) viết lại cái bridge đã có sẵn trong `explorer/*/quote.py:history`
# (`explorer/vci/quote.py:496`). Nay bulk gọi thẳng `history` của provider.
# --------------------------------------------------------------------------


def test_m4_core_does_not_import_the_api_layer():
    """MAJOR-4: `core` không được phụ thuộc `vnbroker.api.*`."""
    import ast
    import inspect
    import pathlib

    tree = ast.parse(pathlib.Path(inspect.getfile(BulkRouter)).read_text(encoding="utf-8"))
    upward = sorted(
        {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and (node.module or "").startswith("vnbroker.api")
        }
        | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
            if alias.name.startswith("vnbroker.api")
        }
    )
    assert upward == [], f"core/bulk_router.py import tầng trên: {upward}"


def test_m4_call_provider_sync_is_no_longer_used():
    """MAJOR-4: bridge trùng lặp đã bị gỡ khỏi đường gọi của bulk.

    Kiểm tra trên CÂY AST (không phải chuỗi) vì docstring cố tình nhắc tên
    `call_provider_sync` để giải thích vì sao nó bị gỡ — quét chuỗi thô sẽ báo
    động giả.
    """
    import ast
    import inspect
    import pathlib

    tree = ast.parse(pathlib.Path(inspect.getfile(BulkRouter)).read_text(encoding="utf-8"))
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "call_provider_sync" not in calls, "vẫn còn gọi call_provider_sync"
    assert "call_provider_sync" not in imported, "vẫn còn import call_provider_sync"


def test_m4_parallel_history_is_used_when_provider_supports_it():
    """MAJOR-4: provider có `parallel`+`symbols` thì bulk gọi MỘT lần cho cả batch."""

    class _Parallel:
        calls: list = []

        def __init__(self, symbol: str):
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
            type(self).calls.append((tuple(symbols or []), parallel))
            return [_frame(sym) for sym in (symbols or [])]

    _install_as_vci(_Parallel)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB", "VNM", "FPT"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert result["errors"] == {}
    assert result["symbols_returned"] == 3
    assert _Parallel.calls == [(("ACB", "VNM", "FPT"), True)], (
        "phải gọi history(symbols=..., parallel=True) đúng một lần"
    )


def test_m4_provider_without_parallel_falls_back_to_sequential():
    """MAJOR-4: SSI/DNSE không có `parallel` thì gọi tuần tự từng symbol."""

    class _Sequential:
        calls: list = []

        def __init__(self, symbol: str):
            self.symbol = symbol
            type(self).calls.append(symbol)

        def history(self, start=None, end=None, interval="1D", **kwargs):
            return _frame(self.symbol)

    _install_as_vci(_Sequential)
    router = _router_for_vci()

    result = router.fetch_history(
        ["ACB", "VNM"], "2024-01-01", "2024-01-31", module="quote"
    )

    assert result["errors"] == {}
    assert result["symbols_returned"] == 2
    assert sorted(_Sequential.calls) == ["ACB", "VNM"]


def test_m4_parallel_capability_detection_ignores_var_kwargs():
    """MAJOR-4: chỉ tin tham số tường minh, không tin `**kwargs`.

    SSI/DNSE có `**kwargs` nên gửi `symbols`/`parallel` vào sẽ bị nuốt im lặng
    thay vì chạy song song — im lặng là thứ tệ nhất, nên phải rơi về tuần tự.
    """

    class _SsiShaped:
        def __init__(self, symbol: str):
            self.symbol = symbol

        def history(self, start=None, end=None, interval="1D", **kwargs):
            raise AssertionError("parallel=True phải bị chặn, không gửi vào **kwargs")

    assert BulkRouter._supports_parallel_history(_SsiShaped) is False
    assert BulkRouter._supports_parallel_history(_SpyProvider) is True


def test_m4_real_provider_signatures_are_detected_correctly():
    """MAJOR-4: phát hiện năng lực khớp với provider THẬT, không chỉ fake."""
    from vnbroker.explorer.dnse.quote import DNSEQuote
    from vnbroker.explorer.kbs.quote import Quote as KBSQuote
    from vnbroker.explorer.ssi.quote import SSIQuote
    from vnbroker.explorer.tcbs.quote import Quote as TCBSQuote
    from vnbroker.explorer.vci.quote import Quote as VCIQuote

    assert BulkRouter._supports_parallel_history(VCIQuote) is True
    assert BulkRouter._supports_parallel_history(KBSQuote) is True
    assert BulkRouter._supports_parallel_history(TCBSQuote) is True
    assert BulkRouter._supports_parallel_history(SSIQuote) is False
    assert BulkRouter._supports_parallel_history(DNSEQuote) is False


def test_m4_kwargs_are_filtered_against_real_provider_signature():
    """MAJOR-4: kwarg phải được lọc theo signature thật, không gửi thừa.

    VCI/KBS/TCBS **không** có ``**kwargs`` nên kwarg lạ sẽ ném ``TypeError`` —
    đó là chỗ cần lọc. SSI/DNSE có ``**kwargs`` nên `_filter_kwargs` cho qua
    toàn bộ (đúng hành vi của helper, và cũng vô hại vì không sinh TypeError).
    """
    import inspect

    from vnbroker.core.bulk_router import _filter_kwargs
    from vnbroker.explorer.vci.quote import Quote as VCIQuote

    wanted = {"start": "2024-01-01", "end": "2024-01-31", "interval": "1D"}
    filtered = _filter_kwargs(VCIQuote.history, dict(wanted, bogus=1))
    assert filtered == wanted, "kwarg lạ phải bị loại với provider không có **kwargs"
    # Gọi được thật, không TypeError
    inspect.signature(VCIQuote.history).bind(None, **filtered)
