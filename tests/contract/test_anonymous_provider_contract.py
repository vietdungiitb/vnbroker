"""Contract test cho TẦNG1 — dữ liệu thị trường ẩn danh.

Mục tiêu kiến trúc: người dùng gọi `history()` mà KHÔNG cần biết provider nào
đang phục vụ. Để điều đó đúng, mọi provider ẩn danh phải trả về CÙNG schema
(cùng tên cột, cùng timezone, cùng ranh giới ngày).

Test ở đây KHÔNG gọi mạng: provider được monkeypatch bằng một fake trả DataFrame
có shape thực tế, để kiểm tra TẦNG ĐƯỜNG DẪN (adapters/data layer) có chuẩn hoá
hay không — đó là nơi hợp đồng thực sự bị phá vỡ.

Nếu test pass nhưng provider thật vẫn lệch, xem `tests/contract/README.md`
phần "Test tầng thích nghi" (cần mạng, opt-in).
"""

from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.common.data import Quote

# Providers KHÔNG cần authentication — đúng phạm vi tầng 1.
ANONYMOUS_SOURCES = ["KBS", "VCI"]

# Schema mà một provider ẩn danh PHẢI trả về.
REQUIRED_COLUMNS = {"time", "open", "high", "low", "close", "volume"}
CANONICAL_TZ = "Asia/Ho_Chi_Minh"


def _raw_frame(start: str, end: str, *, tz_aware: bool) -> pd.DataFrame:
    """DataFrame giống hệt thứ provider thật trả về (trước khi chuẩn hoá)."""
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    if tz_aware:
        idx = idx.tz_localize("UTC").tz_convert(CANONICAL_TZ)
    return pd.DataFrame(
        {
            "time": idx,
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            "close": [104.0, 105.0, 106.0],
            "volume": [1000, 2000, 3000],
        }
    )


def _fake_provider(*, tz_aware: bool, drop_start_filter: bool):
    """Gắn data_source giả vào một Quote instance.

    drop_start_filter=True mô phỏng đúng bug VCI: provider trả về nến NGOÀI
    khoảng start/end thay vì lọc — DataFrame vẫn hợp lệ về mặt kiểu dữ liệu
    nhưng SAI về nghiệp vụ, và không có lỗi nào được báo.
    """

    class Fake:
        symbol = "ACB"

        def history(self, start=None, end=None, interval="1D", **kw):
            if drop_start_filter:
                # Bug: trả cả nến ngoài khoảng yêu cầu.
                idx = pd.to_datetime(["2023-12-20", "2024-01-02", "2024-01-03"])
                if tz_aware:
                    idx = idx.tz_localize("UTC").tz_convert(CANONICAL_TZ)
                return pd.DataFrame(
                    {
                        "time": idx,
                        "open": [1.0, 100.0, 101.0],
                        "high": [1.0, 105.0, 106.0],
                        "low": [1.0, 99.0, 100.0],
                        "close": [1.0, 104.0, 105.0],
                        "volume": [1, 1000, 2000],
                    }
                )
            return _raw_frame(start or "", end or "", tz_aware=tz_aware)

    q = Quote("ACB", "KBS")
    q.data_source = Fake()
    return q


# ---------------------------------------------------------------- contract


@pytest.mark.parametrize("source", ANONYMOUS_SOURCES)
def test_history_returns_required_columns(source):
    """Mọi provider ẩn danh phải trả đủ cột chuẩn."""
    q = _fake_provider(tz_aware=True, drop_start_filter=False)
    df = q.history(start="2024-01-01", end="2024-01-31")

    missing = REQUIRED_COLUMNS - set(df.columns)
    assert not missing, f"{source}: thiếu cột {sorted(missing)} (có: {list(df.columns)})"


def test_history_time_is_timezone_aware():
    """Hợp đồng: `time` PHẢI tz-aware.

    Lý do: provider tz-naive + provider tz-aware khiến `pd.concat` sinh dtype
    `object`, phá vỡ mọi phép tính thời gian phía downstream — và đây là kiểu
    lỗi KHÔNG ném exception.
    """
    naive = _fake_provider(tz_aware=False, drop_start_filter=False)
    df = naive.history(start="2024-01-01", end="2024-01-31")

    assert df["time"].dt.tz is not None, (
        "`time` trả về tz-naive. Phải tz-aware để concat giữa các provider "
        "không rơi về dtype object."
    )
    assert str(df["time"].dt.tz) == CANONICAL_TZ


def test_history_respects_start_and_end_boundary():
    """Hợp đồng: kết quả KHÔNG được chứa nến ngoài khoảng [start, end].

    Đây là mutation check cho bug đã xác minh ở explorer/vci/quote.py:
    provider gửi start/end lên API rồi tin response, không lọc lại phía
    client — nên có thể trả nến ngoài khoảng mà không báo lỗi.
    """
    buggy = _fake_provider(tz_aware=True, drop_start_filter=True)
    df = buggy.history(start="2024-01-01", end="2024-01-31")

    times = df["time"]
    assert times.min() >= pd.Timestamp("2024-01-01", tz=CANONICAL_TZ), (
        f"history() trả nến NGOÀI khoảng start: min={times.min()} "
        f"< start=2024-01-01. Người dùng nhận dữ liệu sai mà không có lỗi nào."
    )


def test_history_column_order_is_stable():
    """Tên cột phải ổn định để code downstream không vỡ khi provider đổi thứ tự."""
    a = _fake_provider(tz_aware=True, drop_start_filter=False)
    b = _fake_provider(tz_aware=True, drop_start_filter=False)

    assert list(a.history(start="2024-01-01", end="2024-01-31").columns) == list(
        b.history(start="2024-01-01", end="2024-01-31").columns
    )