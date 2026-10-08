"""Unit tests for the Normalizer class.

Tests that DataFrames are properly normalized: tz-aware, boundary-filtered,
sorted, and safe on empty inputs.
"""

from __future__ import annotations

import pandas as pd

from vnbroker.core.utils.normalizer import Normalizer

CANONICAL_TZ = "Asia/Ho_Chi_Minh"


def _make_df(times: list[str], *, naive: bool = True) -> pd.DataFrame:
    """Create a test DataFrame with time column."""
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


# ------------------------------------------------------------------ single df


def test_normalize_single_df():
    """Single DataFrame gets tz-aware."""
    df = _make_df(["2024-01-02", "2024-01-03"], naive=True)
    result = Normalizer.normalize_history(df)

    assert isinstance(result, pd.DataFrame)
    assert result["time"].dt.tz is not None
    assert str(result["time"].dt.tz) == CANONICAL_TZ


def test_normalize_single_df_already_tz_aware():
    """Already tz-aware DataFrame stays tz-aware."""
    df = _make_df(["2024-01-02", "2024-01-03"], naive=False)
    result = Normalizer.normalize_history(df)

    assert isinstance(result, pd.DataFrame)
    assert result["time"].dt.tz is not None
    assert str(result["time"].dt.tz) == CANONICAL_TZ


# ------------------------------------------------------------------ list of dfs


def test_normalize_list_df():
    """List of DataFrames all get normalized."""
    df1 = _make_df(["2024-01-02"], naive=True)
    df2 = _make_df(["2024-01-03"], naive=True)
    df3 = _make_df(["2024-01-04"], naive=False)

    result = Normalizer.normalize_history([df1, df2, df3])

    assert isinstance(result, list)
    assert len(result) == 3
    for df in result:
        assert isinstance(df, pd.DataFrame)
        assert df["time"].dt.tz is not None
        assert str(df["time"].dt.tz) == CANONICAL_TZ


def test_normalize_empty_list():
    """Empty list returns empty list."""
    result = Normalizer.normalize_history([])
    assert isinstance(result, list)
    assert len(result) == 0


# ------------------------------------------------------------------ boundary filter


def test_boundary_filter():
    """Start/end boundaries are respected."""
    df = _make_df(
        ["2024-01-01", "2024-01-05", "2024-01-10", "2024-01-15", "2024-01-20"],
        naive=True,
    )

    result = Normalizer.normalize_history(df, "2024-01-05", "2024-01-15")

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3
    times = result["time"].dt.strftime("%Y-%m-%d").tolist()
    assert times == ["2024-01-05", "2024-01-10", "2024-01-15"]


def test_boundary_filter_start_only():
    """Only start boundary filters correctly."""
    df = _make_df(["2024-01-01", "2024-01-05", "2024-01-10"], naive=True)

    result = Normalizer.normalize_history(df, "2024-01-05", None)

    assert len(result) == 2
    times = result["time"].dt.strftime("%Y-%m-%d").tolist()
    assert times == ["2024-01-05", "2024-01-10"]


def test_boundary_filter_end_only():
    """Only end boundary filters correctly."""
    df = _make_df(["2024-01-01", "2024-01-05", "2024-01-10"], naive=True)

    result = Normalizer.normalize_history(df, None, "2024-01-05")

    assert len(result) == 2
    times = result["time"].dt.strftime("%Y-%m-%d").tolist()
    assert times == ["2024-01-01", "2024-01-05"]


# ------------------------------------------------------------------ empty df safety


def test_empty_df_safe():
    """Empty DataFrame doesn't crash."""
    df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    result = Normalizer.normalize_history(df)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_empty_df_in_list_safe():
    """Empty DataFrame in a list doesn't crash."""
    empty_df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    normal_df = _make_df(["2024-01-02"], naive=True)

    result = Normalizer.normalize_history([empty_df, normal_df])

    assert isinstance(result, list)
    assert len(result) == 2
    assert len(result[0]) == 0
    assert len(result[1]) == 1


# ---------------------------------- empty-day vs unusable-empty (AC-7 regression)


def test_empty_df_with_schema_stays_tz_aware():
    """Regression: ngày giao dịch rỗng VẪN phải đạt hợp đồng tz.

    `test_empty_df_safe` trên chỉ kiểm `len(result) == 0` nên không bắt được
    hợp đồng tầng 1 (`vnbroker/common/data.py`, docstring `_normalize_quote_result`:
    mọi provider trả cùng schema, `time` luôn tz-aware). Frame rỗng mà cột
    `time` là object/NaT thì `concat` với frame thật sẽ hỏng — đúng loại lỗi âm
    thầm mà `history` trả về cho ngày nghỉ.
    """
    df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    result = Normalizer.normalize_history(df)

    assert len(result) == 0
    assert "time" in result.columns, "Frame rỗng vẫn phải giữ schema"
    assert str(result["time"].dt.tz) == CANONICAL_TZ, (
        f"Ngày giao dịch rỗng vẫn phải tz-aware, thực tế: {result['time'].dtype}"
    )


def test_schema_less_df_passes_through_unchanged():
    """Regression: frame KHÔNG schema đi thẳng qua, không được chuẩn hoá.

    Ghi lại điều kiện mà quyết định "rỗng = không dùng được" của
    `_is_unusable_provider_result` dựa vào: normalizer KHÔNG cứu được frame
    thiếu cột `time` (nó trả về đúng object gốc, 0 cột). Vì vậy tầng failover
    (`_run_with_failover`) phải tự loại trước, nếu không frame 0 cột sẽ lọt
    thẳng tới người dùng.

    Nếu ai đó sửa normalizer để xử lý frame thiếu schema, test này đỏ và quyết
    định ở `data.py` cần được xem lại.
    """
    df = pd.DataFrame()
    result = Normalizer.normalize_history(df)

    assert result is df, "Normalizer phải trả nguyên frame khi không có cột time"
    assert len(result.columns) == 0
    assert "time" not in result.columns


# ------------------------------------------------------------------ sorting


def test_result_is_sorted():
    """Result is sorted by time ascending."""
    df = _make_df(["2024-01-05", "2024-01-01", "2024-01-03"], naive=True)

    result = Normalizer.normalize_history(df)

    assert result["time"].is_monotonic_increasing


def test_index_is_reset():
    """Index is reset after normalization."""
    df = _make_df(["2024-01-03", "2024-01-01"], naive=True)
    df.index = [10, 20]  # Non-default index

    result = Normalizer.normalize_history(df)

    assert list(result.index) == [0, 1]


# ------------------------------------------------------------------ non-df input


def test_non_df_passthrough():
    """Non-DataFrame input passes through unchanged."""
    assert Normalizer.normalize_history(None) is None
    assert Normalizer.normalize_history("string") == "string"
    assert Normalizer.normalize_history(42) == 42


def test_df_without_time_column_passthrough():
    """DataFrame without 'time' column passes through unchanged."""
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    result = Normalizer.normalize_history(df)
    assert result is df
