"""Integration tests for failover and bulk normalization.

Tests that _auto_sources is properly set in production code and that
bulk history results are normalized through the Normalizer.
"""

from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.common.data import Quote
from vnbroker.core import source_router
from vnbroker.core.utils.normalizer import Normalizer

CANONICAL_TZ = "Asia/Ho_Chi_Minh"


@pytest.fixture(autouse=True)
def _clean_router_state():
    """Ensure clean health state for test isolation."""
    source_router.reset_router_state()
    yield
    source_router.reset_router_state()


def _frame(*, naive: bool, times: list[str]) -> pd.DataFrame:
    idx = pd.to_datetime(times)
    if not naive:
        idx = idx.tz_localize(CANONICAL_TZ)
    return pd.DataFrame(
        {
            "time": idx,
            "open": [1.0] * len(times),
            "high": [1.0] * len(times),
            "low": [1.0] * len(times),
            "close": [1.0] * len(times),
            "volume": [1] * len(times),
        }
    )


class _FailingSource:
    """Provider that always raises a network error."""

    symbol = "ACB"

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    def history(self, **kw):
        self.calls += 1
        raise self.exc


class _WorkingSource:
    """Provider that returns valid data."""

    symbol = "ACB"

    def __init__(self, *, naive: bool = False) -> None:
        self.naive = naive
        self.calls = 0

    def history(self, **kw):
        self.calls += 1
        return _frame(naive=self.naive, times=["2024-01-02", "2024-01-03"])


def _make_quote(sources: dict[str, object], *, order: list[str] | None = None) -> Quote:
    """Build Quote with real failover logic, only providers are faked."""
    q = Quote("ACB", "AUTO")
    q._auto_sources = sources  # type: ignore[attr-defined]
    if order is not None:
        def _fixed_order(module_name: str, symbol: str | None = None) -> list[str]:
            return [s for s in order if s in sources]
        q._fixed_source_order = _fixed_order  # type: ignore[attr-defined]
    return q


# ------------------------------------------------------------------ failover


def test_auto_source_has_auto_sources():
    """Quote('ACB', 'AUTO') must have _auto_sources attribute populated."""
    q = Quote("ACB", "AUTO")
    assert hasattr(q, "_auto_sources"), "Quote with AUTO source must have _auto_sources"
    assert isinstance(q._auto_sources, dict), "_auto_sources must be a dict"
    assert len(q._auto_sources) > 0, "_auto_sources must not be empty"
    # Should contain at least vci and kbs
    source_names = {s.lower() for s in q._auto_sources.keys()}
    assert "vci" in source_names or "kbs" in source_names, (
        f"Expected vci or kbs in auto sources, got: {source_names}"
    )


def test_failover_on_429():
    """Mock VCI to raise 429, verify KBS serves the request."""
    vci = _FailingSource(ConnectionError("429 rate limit"))
    kbs = _WorkingSource(naive=False)

    q = _make_quote({"vci": vci, "kbs": kbs}, order=["vci", "kbs"])
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert vci.calls > 0, "VCI should have been tried"
    assert kbs.calls >= 1, "KBS should have served after VCI failed"
    assert isinstance(df, pd.DataFrame)
    assert "time" in df.columns
    assert df["time"].dt.tz is not None


def test_bulk_normalization():
    """Bulk history returns tz-aware DataFrames."""
    # Simulate bulk result: list of DataFrames (some naive, some aware)
    naive_df = _frame(naive=True, times=["2024-01-02", "2024-01-03"])
    aware_df = _frame(naive=False, times=["2024-01-04", "2024-01-05"])

    result = Normalizer.normalize_history([naive_df, aware_df], "2024-01-01", "2024-01-31")

    assert isinstance(result, list)
    assert len(result) == 2
    for df in result:
        assert isinstance(df, pd.DataFrame)
        assert df["time"].dt.tz is not None, "All bulk results must be tz-aware"
        assert str(df["time"].dt.tz) == CANONICAL_TZ


def test_bulk_has_manifest():
    """Bulk result includes symbol information via attrs."""
    df = _frame(naive=True, times=["2024-01-02"])
    df.attrs["symbol"] = "ACB"

    result = Normalizer.normalize_history([df], "2024-01-01", "2024-01-31")

    assert isinstance(result, list)
    assert len(result) == 1
    # Normalizer preserves attrs
    assert result[0].attrs.get("symbol") == "ACB"


# ------------------------------------------- empty result must fail over (AC-7)


class _EmptyNoSchemaSource:
    """Provider that returns ``pd.DataFrame()`` WITHOUT raising.

    Mô phỏng provider im lặng chết: HTTP 200 nhưng payload rỗng. Đây là ca
    nguy hiểm nhất vì không có exception nào để bắt — `should_failover` chỉ xét
    exception, nên trước đây frame rỗng lọt thẳng tới người dùng kèm
    `record_success`.
    """

    symbol = "ACB"

    def __init__(self) -> None:
        self.calls = 0

    def history(self, **kw):
        self.calls += 1
        return pd.DataFrame()

    def intraday(self, **kw):
        self.calls += 1
        return pd.DataFrame()

    def price_depth(self, **kw):
        self.calls += 1
        return pd.DataFrame()


class _EmptyWithSchemaSource:
    """Provider that returns 0 rows BUT keeps the schema (non-trading day)."""

    symbol = "ACB"

    def __init__(self) -> None:
        self.calls = 0

    def history(self, **kw):
        self.calls += 1
        return pd.DataFrame(
            columns=["time", "open", "high", "low", "close", "volume"]
        )


def test_empty_result_triggers_failover():
    """AC-7: provider trả rỗng mà không ném lỗi ⇒ phải chuyển provider.

    Provider #1 trả `pd.DataFrame()` (0 cột, 0 dòng), provider #2 trả dữ liệu
    thật. Kỳ vọng: #2 được gọi, #1 KHÔNG được ghi `record_success`, và frame
    trả về có dữ liệu.
    """
    dead = _EmptyNoSchemaSource()
    alive = _WorkingSource(naive=False)

    q = _make_quote({"kbs": dead, "vci": alive}, order=["kbs", "vci"])
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert alive.calls == 1, (
        f"Phải fallback sang provider thứ 2, thực tế {alive.calls}"
    )
    assert len(df) > 0, f"Phải trả frame có dữ liệu, thực tế {len(df)} dòng"
    assert df.attrs.get("source_used") == "VCI", (
        "Frame phải đến từ provider thứ 2, không phải provider trả rỗng"
    )

    snapshot = source_router.get_source_health_snapshot("quote")
    kbs_state = snapshot.get("KBS") or {}
    assert int(kbs_state.get("failures", 0)) >= 1, (
        f"Provider trả rỗng phải bị ghi failure, thực tế: {kbs_state}"
    )


def test_empty_result_records_no_success_for_dead_provider(monkeypatch):
    """AC-7: tuyệt đối KHÔNG `record_success` cho provider trả rỗng.

    Đo trực tiếp lời gọi `record_success`/`record_failure` thay vì suy ra từ
    snapshot, để assertion bám đúng hành vi AC nêu.
    """
    recorded: list[tuple[str, str]] = []
    monkeypatch.setattr(
        source_router, "record_success",
        lambda module_name, source: recorded.append(("success", source)),
    )
    monkeypatch.setattr(
        source_router, "record_failure",
        lambda module_name, source: recorded.append(("failure", source)),
    )

    dead = _EmptyNoSchemaSource()
    alive = _WorkingSource(naive=False)
    q = _make_quote({"kbs": dead, "vci": alive}, order=["kbs", "vci"])
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert len(df) > 0
    assert ("success", "kbs") not in recorded, (
        f"Provider trả rỗng không được ghi success: {recorded}"
    )
    assert ("success", "vci") in recorded, (
        f"Provider phục vụ thật phải được ghi success: {recorded}"
    )


def test_empty_frame_with_schema_is_still_a_success():
    """Ranh giới của AC-7: ngày giao dịch rỗng KHÔNG phải provider chết.

    Provider trả 0 dòng **nhưng giữ schema** (`pd.DataFrame(columns=[...])`)
    nghĩa là provider đã làm đúng việc, chỉ là trong khoảng yêu cầu không có
    phiên (Tết, cuối tuần, mã chưa có dữ liệu). Frame này phải được coi là
    THÀNH CÔNG và trả về cho người dùng — nếu coi là thất bại thì mọi ngày nghỉ
    sẽ thành lỗi hệ thống.
    """
    quiet = _EmptyWithSchemaSource()
    q = _make_quote({"kbs": quiet})
    df = q.history(start="2024-01-06", end="2024-01-07")

    assert len(df) == 0, "Ngày nghỉ vẫn phải trả frame rỗng, không phải lỗi"
    assert "time" in df.columns, "Frame rỗng vẫn phải giữ schema hợp đồng"
    assert df["time"].dt.tz is not None, "Frame rỗng vẫn phải tz-aware"
    assert df.attrs.get("source_used") == "KBS"

    snapshot = source_router.get_source_health_snapshot("quote")
    state = snapshot.get("KBS") or {}
    assert int(state.get("failures", 0)) == 0, (
        f"Ngày giao dịch rỗng không phải lỗi provider: {state}"
    )

