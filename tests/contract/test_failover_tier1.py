"""GĐ3 — Failover tầng 1: người dùng không cần biết provider nào phục vụ.

Hợp đồng: `Market(auto=True)` gọi một lần, hệ thống tự chọn provider ổn định và
xoay vòng khi gặp rate-limit / mất kết nối. Người dùng luôn nhận DataFrame
CÙNG schema bất kể provider nào đã phục vụ.

GĐ2 đã bảo đảm phần "cùng schema" bằng `_normalize_quote_result` ở tầng data.
Bộ test này khoá phần "tự xoay vòng" — trước đó nó KHÔNG tồn tại trên đường chính.

Không gọi mạng: provider được thay bằng fake, cơ chế thật của source_router
(build_source_order / should_failover / record_failure) được dùng nguyên vẹn.
"""

from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.common.data import Quote
from vnbroker.core import source_router

REQUIRED_COLUMNS = {"time", "open", "high", "low", "close", "volume"}
CANONICAL_TZ = "Asia/Ho_Chi_Minh"


@pytest.fixture(autouse=True)
def _clean_router_state():
    """Bảo đảm health state sạch — test phải độc lập với thứ tự chạy."""
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
    """Provider giả luôn ném lỗi mạng — mô phỏng rate-limit/mất kết nối."""

    symbol = "ACB"

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    def history(self, **kw):
        self.calls += 1
        raise self.exc


class _WorkingSource:
    """Provider giả trả dữ liệu hợp lệ."""

    symbol = "ACB"

    def __init__(self, *, naive: bool) -> None:
        self.naive = naive
        self.calls = 0

    def history(self, **kw):
        self.calls += 1
        return _frame(naive=self.naive, times=["2024-01-02", "2024-01-03"])


def _make_quote(sources: dict[str, object], *, order: list[str] | None = None) -> Quote:
    """Dựng Quote với lớp failover thật, chỉ thay provider bằng fake.

    ``order`` ghim thứ tự provider để test có tính xác định. Mặc định dùng
    ``build_source_order`` thật (hash-shard theo symbol), nên thứ tự phụ thuộc
    symbol — với vì vậy test failover phải ghim thứ tự thay vì giả định KBS
    luôn đứng đầu.
    """
    q = Quote("ACB", "AUTO")
    q._auto_sources = sources  # type: ignore[attr-defined]
    if order is not None:
        def _fixed_order(module_name: str, symbol: str | None = None) -> list[str]:
            return [s for s in order if s in sources]
        q._fixed_source_order = _fixed_order  # type: ignore[attr-defined]
    return q


# ------------------------------------------------------------------ failover


def test_failover_switches_provider_and_returns_valid_frame():
    """Provider đầu lỗi mạng → phải tự thử provider kế tiếp, trả frame hợp lệ."""
    kbs = _FailingSource(ConnectionError("429 rate limit"))
    vci = _WorkingSource(naive=False)

    q = _make_quote({"kbs": kbs, "vci": vci}, order=["kbs", "vci"])
    df = q.history(start="2024-01-01", end="2024-01-31")

    # Provider lỗi mạng tạm thời được retry TỪNG provider trước khi chuyển
    # (DEFAULT_RETRIES=3) — đây là hành vi mong muốn.
    assert kbs.calls == 3, f"Provider lỗi phải retry 3 lần, thực tế {kbs.calls}"
    assert vci.calls == 1, f"Phải fallback sang provider kế tiếp, thực tế {vci.calls}"
    assert isinstance(df, pd.DataFrame)
    assert REQUIRED_COLUMNS <= set(df.columns)


def test_failover_result_has_same_schema_regardless_of_provider():
    """Kết quả phải GIỐNG NHAU dù provider nào phục vụ — đây là ý nghĩa của GĐ2.

    Provider trả tz-naive (kiểu KBS) và tz-aware (kiểu VCI) phải ra cùng schema
    ở đường người dùng, nếu không thì failover tự động là sai ẩm thầm.
    """
    naive_df = _make_quote({"kbs": _WorkingSource(naive=True)}).history(
        start="2024-01-01", end="2024-01-31"
    )
    aware_df = _make_quote({"vci": _WorkingSource(naive=False)}).history(
        start="2024-01-01", end="2024-01-31"
    )

    assert list(naive_df.columns) == list(aware_df.columns)
    assert naive_df["time"].dt.tz is not None
    assert str(naive_df["time"].dt.tz) == CANONICAL_TZ
    assert str(aware_df["time"].dt.tz) == CANONICAL_TZ


def test_failover_records_health_for_deprioritization():
    """Provider lỗi phải bị ghi nhận để lần sau ưu tiên provider khác."""
    kbs = _FailingSource(ConnectionError("429 rate limit"))
    q = _make_quote({"kbs": kbs, "vci": _WorkingSource(naive=False)}, order=["kbs", "vci"])

    q.history(start="2024-01-01", end="2024-01-31")

    snapshot = source_router.get_source_health_snapshot("quote")
    kbs_state = snapshot.get("KBS") or {}
    assert int(kbs_state.get("failures", 0)) >= 1, (
        f"Phải ghi nhận failure của KBS, thực tế: {kbs_state}"
    )


def test_success_records_no_failure():
    """Provider trả tốt thì KHÔNG được ghi failure."""
    q = _make_quote({"kbs": _WorkingSource(naive=False)})
    q.history(start="2024-01-01", end="2024-01-31")

    snapshot = source_router.get_source_health_snapshot("quote")
    kbs_state = snapshot.get("KBS") or {}
    assert int(kbs_state.get("failures", 0)) == 0


def test_result_annotated_with_source_used():
    """Gắn provider đã dùng vào attrs để người dùng debug được."""
    q = _make_quote({"vci": _WorkingSource(naive=False)})
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert df.attrs.get("source_used") == "VCI"


# --------------------------------------------------------------- exhaustion


def test_raises_original_error_when_all_providers_fail():
    """Hết provider → ném lỗi gốc, KHÔNG trả DataFrame rỗng.

    Đây là điểm mấu chốt: một frame rỗng khiến người dùng tưởng là 'hôm nay
    không có giao dịch' thay vì 'đã lỗi mạng' — lỗi âm thầm nguy hiểm nhất.
    """
    q = _make_quote(
        {
            "kbs": _FailingSource(ConnectionError("429 kbs down")),
            "vci": _FailingSource(ConnectionError("429 vci down")),
        },
        order=["kbs", "vci"],
    )

    with pytest.raises(ConnectionError):
        q.history(start="2024-01-01", end="2024-01-31")


def test_does_not_failover_on_programming_errors():
    """Lỗi lập trình (TypeError, AttributeError) KHÔNG được xoay vòng che lỗi."""
    kbs = _FailingSource(TypeError("bug trong provider"))
    q = _make_quote({"kbs": kbs})

    with pytest.raises(TypeError):
        q.history(start="2024-01-01", end="2024-01-31")

    # Lỗi lập trình không phải lỗi mạng: không retry, không ghi health state.
    assert kbs.calls == 1, f"Lỗi lập trình không được retry, thực tế {kbs.calls} calls"
    snapshot = source_router.get_source_health_snapshot("quote")
    state = snapshot.get("KBS") or {}
    assert int(state.get("failures", 0)) == 0, "Lỗi lập trình không được ghi failure"


def test_single_provider_no_retry_loop():
    """Chỉ 1 provider thì không lặp vô hạn."""
    from vnbroker.common.data import Config

    vci = _FailingSource(ConnectionError("boom"))
    q = _make_quote({"vci": vci})

    with pytest.raises(ConnectionError):
        q.history(start="2024-01-01", end="2024-01-31")

    # Chỉ 1 provider: thử đúng DEFAULT_RETRIES lần rồi ném lỗi gốc — KHÔNG lặp vô hạn.
    assert vci.calls == Config.DEFAULT_RETRIES, (
        f"Phải thử đúng {Config.DEFAULT_RETRIES} lần, thực tế {vci.calls}"
    )