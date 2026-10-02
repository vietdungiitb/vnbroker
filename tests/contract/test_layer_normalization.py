"""Test chứng minh TẦNG DATA phải chuẩn hoá kết quả — không phụ thuộc provider.

Bối cảnh (GĐ2 kế hoạch):
`ohlc_to_df` chỉ `tz_convert` cho nhánh `source == 'VCI'`; nhánh `else` để nguyên
`pd.to_datetime(...)` nên `time` ra tz-naive (transform.py:331-338). VCI trả nến
ngoài khoảng start/end vì tin response API, không lọc lại (vci/quote.py:562).

Hệ quả khi bật failover (GĐ3): user gặp rate-limit ở KBS → chuyển VCI → nhận
DataFrame với schema lệch, `pd.concat` rơi về dtype object, KHÔNG exception nào
được ném. Đó là tệ hơn việc lỗi thấy được.

→ Hợp đồng được khoá ở đây, tại một chỗ duy nhất: tầng `data.py`.
Provider mới thêm vào sau này tự động tuân thủ mà không cần sửa từng provider.

Không gọi mạng.
"""

from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.common.data import Quote

CANONICAL_TZ = "Asia/Ho_Chi_Minh"


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


def _quote_returning(df: pd.DataFrame) -> Quote:
    class Fake:
        symbol = "ACB"

        def history(self, start=None, end=None, interval="1D", **kw):
            return df.copy()

        def intraday(self, **kw):
            return df.copy()

    q = Quote("ACB", "KBS")
    q.data_source = Fake()
    return q


# ------------------------------------------------- tz normalization


def test_data_layer_makes_time_tz_aware():
    """Provider trả tz-naive → data layer phải gắn Asia/Ho_Chi_Minh."""
    q = _quote_returning(_frame(naive=True, times=["2024-01-02", "2024-01-03"]))
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert df["time"].dt.tz is not None, (
        "data layer phải chuẩn hoá `time` thành tz-aware. "
        "Nếu không, pd.concat giữa provider tz-naive và tz-aware sẽ ra object dtype."
    )
    assert str(df["time"].dt.tz) == CANONICAL_TZ


def test_data_layer_preserves_instant_when_already_tz_aware():
    """Đã tz-aware thì KHÔNG dịch chuyển — chỉ gắn tz cho khi thiếu.

    Chống hồi quy: localize-naive rồi convert lại sẽ dịch timestamp 7 giờ.
    """
    q = _quote_returning(_frame(naive=False, times=["2024-01-02", "2024-01-03"]))
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert df["time"].iloc[0] == pd.Timestamp("2024-01-02", tz=CANONICAL_TZ), (
        f"Timestamp đã tz-aware bị dịch chuyển: {df['time'].iloc[0]}"
    )


def test_data_layer_does_not_shift_naive_treated_as_utc():
    """Naive được hiểu là GIỜ VIỆT NAM, không phải UTC.

    Provider trả '2024-01-02 09:00' nghĩa là 09:00 VN. Nếu ta localize UTC rồi
    convert sang VN, nó thành 16:00 — sai 7 tiếng, và sai này rất khó phát hiện
    vì vẫn là timestamp hợp lệ.
    """
    naive = _frame(naive=True, times=["2024-01-02 09:00:00"])
    q = _quote_returning(naive)
    df = q.history(start="2024-01-01", end="2024-01-31")

    got = df["time"].iloc[0]
    assert got == pd.Timestamp("2024-01-02 09:00", tz=CANONICAL_TZ), (
        f"Naive timestamp bị dịch sai timezone: {got} "
        f"(mong đợi 2024-01-02 09:00 {CANONICAL_TZ})"
    )


# ------------------------------------------------- boundary filtering


def test_data_layer_drops_rows_before_start():
    q = _quote_returning(
        _frame(naive=False, times=["2023-12-20", "2024-01-02", "2024-01-03"])
    )
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert df["time"].min() >= pd.Timestamp("2024-01-01", tz=CANONICAL_TZ), (
        f"data layer phải lọc nến trước `start`; còn {df['time'].min()}"
    )
    assert len(df) == 2, f"Sau lọc phải còn 2 dòng, thực tế {len(df)}"


def test_data_layer_drops_rows_after_end():
    q = _quote_returning(
        _frame(naive=False, times=["2024-01-02", "2024-01-31", "2024-02-15"])
    )
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert df["time"].max() <= pd.Timestamp("2024-01-31 23:59:59", tz=CANONICAL_TZ), (
        f"data layer phải lọc nến sau `end`; còn {df['time'].max()}"
    )


def test_data_layer_keeps_rows_when_no_boundary_given():
    """Không truyền start/end thì KHÔNG lọc — trả về nguyên trạng."""
    q = _quote_returning(_frame(naive=False, times=["2019-01-02", "2024-01-02"]))
    df = q.history()

    assert len(df) == 2, f"Không có start/end thì phải giữ nguyên, còn {len(df)} dòng"


def test_data_layer_sorts_chronologically():
    """Thứ tự thời gian phải tăng dần, kể cả khi provider trả lộn xộn."""
    q = _quote_returning(
        _frame(naive=False, times=["2024-01-04", "2024-01-02", "2024-01-03"])
    )
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert df["time"].is_monotonic_increasing, (
        f"`time` không tăng dần: {list(df['time'])}"
    )


# ------------------------------------------------- shape preservation


def test_data_layer_preserves_columns_and_does_not_mutate_input():
    original = _frame(naive=True, times=["2023-12-20", "2024-01-02"])
    snapshot = original.copy()
    q = _quote_returning(original)

    df = q.history(start="2024-01-01", end="2024-01-31")

    assert list(df.columns) == list(snapshot.columns), "Không được thêm/bớt cột"
    # Provider object không bị mutate trong quá trình chuẩn hoá.
    assert original["time"].dt.tz is None, "Không được mutate DataFrame của provider"


def test_data_layer_handles_empty_frame():
    """Frame rỗng phải trả về rỗng, không ném lỗi."""
    q = _quote_returning(_frame(naive=False, times=[]))
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert df.empty
    assert "time" in df.columns


@pytest.mark.parametrize("bad_start", ["not-a-date", "", None])
def test_data_layer_tolerates_unparsable_boundary(bad_start):
    """`start` không parse được thì bỏ lọc thay vì ném lỗi lên người dùng."""
    q = _quote_returning(_frame(naive=False, times=["2024-01-02"]))
    df = q.history(start=bad_start, end="2024-01-31")

    assert len(df) == 1