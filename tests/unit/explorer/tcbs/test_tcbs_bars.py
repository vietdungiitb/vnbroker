"""Unit test cho `vnbroker.explorer.tcbs.bars` + wiring vào `Quote.history()`.

Nguồn chuẩn: `openapi-v1.0.0.json`
- ``GET /nyx/v2/stock/bars-long-term`` — resolution ``D`` / ``W`` / ``M``
- ``GET /nyx/v2/stock/bars`` — resolution tính bằng phút

Cả hai cùng bộ tham số bắt buộc: ``ticker, type, resolution, to, countBack``.
Response: ``{ticker, data: [{open, high, low, close, volume, tradingDate}]}``,
``tradingDate`` là ISO-8601 **UTC** (hậu tố ``Z``).
"""

from unittest.mock import patch

import ast
import pandas as pd
import pytest

from vnbroker.core.utils.parser import InstrumentType
from vnbroker.explorer.tcbs import bars
from vnbroker.explorer.tcbs.quote import Quote as TCBSQuote


def _source_of(module) -> str:
    with open(module.__file__, encoding="utf-8") as handle:
        return handle.read()


ACB_BARS_PAYLOAD = {
    "ticker": "ACB",
    "data": [
        {
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 103.0,
            "volume": 1_000_000,
            "tradingDate": "2025-09-11T00:00:00Z",
            "dataT1": None,
        },
        {
            "open": 103.0,
            "high": 108.0,
            "low": 102.0,
            "close": 107.5,
            "volume": 2_000_000,
            "tradingDate": "2025-09-12T00:00:00Z",
            "dataT1": None,
        },
    ],
}


# --- AC1: cột đúng ---------------------------------------------------------


@pytest.mark.unit
def test_bars_to_frame_returns_exactly_standard_columns():
    df = bars.bars_to_frame(
        ACB_BARS_PAYLOAD,
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="1D",
    )

    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]


# --- AC2 + AC3: tz-aware Asia/Ho_Chi_Minh, gọi tz_convert tường minh ------


@pytest.mark.unit
def test_bars_to_frame_time_column_is_tz_aware_ho_chi_minh():
    df = bars.bars_to_frame(
        ACB_BARS_PAYLOAD,
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="1D",
    )

    assert isinstance(df["time"].dtype, pd.DatetimeTZDtype)
    assert str(df["time"].dt.tz) == "Asia/Ho_Chi_Minh"


@pytest.mark.unit
def test_bars_to_frame_uses_tz_convert_not_tz_localize():
    """`tz_convert` là hành vi **bắt buộc**.

    `Normalizer` (core/utils/normalizer.py:22-24) chỉ `tz_localize` khi cột
    `time` chưa có tz. Nếu `bars.py` chỉ `tz_localize`, frame UTC sẽ đi qua
    nguyên vẹn và giờ 07:00 VN sẽ thành 00:00 UTC — sai ngày giao dịch.
    """
    from pandas.core.indexes.accessors import DatetimeProperties

    calls = []
    real_tz_convert = DatetimeProperties.tz_convert

    def spy_tz_convert(self, tz):
        calls.append(str(tz))
        return real_tz_convert(self, tz)

    with patch.object(DatetimeProperties, "tz_convert", spy_tz_convert):
        df = bars.bars_to_frame(
            ACB_BARS_PAYLOAD,
            symbol="ACB",
            asset_type=InstrumentType.STOCK,
            interval_key="1D",
        )

    assert "Asia/Ho_Chi_Minh" in calls
    assert str(df["time"].dt.tz) == "Asia/Ho_Chi_Minh"


@pytest.mark.unit
def test_bars_to_frame_trading_date_is_same_day_in_vietnam_time():
    """AC3: `2025-09-12T00:00:00Z` -> `2025-09-12 07:00:00+07:00`.

    Ngày giao dịch KHÔNG dịch: 00:00Z + 7h vẫn là 12/09.
    """
    df = bars.bars_to_frame(
        ACB_BARS_PAYLOAD,
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="1D",
    )

    last = df["time"].iloc[-1]
    assert last.strftime("%Y-%m-%d") == "2025-09-12"
    assert last.strftime("%Y-%m-%d %H:%M:%S") == "2025-09-12 07:00:00"
    assert last.utcoffset() == pd.Timedelta(hours=7)


# --- AC4: field lạ của server không lọt vào frame -------------------------


@pytest.mark.unit
def test_unknown_server_field_data_t1_does_not_leak_into_frame():
    """Server thật trả `dataT1: null`, không có trong spec."""
    df = bars.bars_to_frame(
        ACB_BARS_PAYLOAD,
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="1D",
    )

    assert "dataT1" not in df.columns
    assert set(df.columns) == {"time", "open", "high", "low", "close", "volume"}


@pytest.mark.unit
def test_record_missing_optional_fields_yields_none_not_keyerror():
    payload = {
        "ticker": "ACB",
        "data": [{"tradingDate": "2025-09-12T00:00:00Z", "close": 107.5}],
    }

    df = bars.bars_to_frame(
        payload,
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="1D",
    )

    assert len(df) == 1
    assert pd.isna(df["open"].iloc[0])
    assert df["close"].iloc[0] == 107.5


# --- AC5: history() nối được bars, không NotImplementedError ---------------


@pytest.mark.unit
def test_history_daily_multiday_no_longer_raises_not_implemented():
    quote = TCBSQuote("ACB", show_log=False)
    with patch("vnbroker.core.utils.client.send_request") as mock_send:
        mock_send.return_value = ACB_BARS_PAYLOAD
        df = quote.history(start="2025-09-11", end="2025-09-12", interval="1D")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]


@pytest.mark.unit
def test_history_daily_multiday_calls_bars_long_term_endpoint():
    quote = TCBSQuote("ACB", show_log=False)
    with patch("vnbroker.core.utils.client.send_request") as mock_send:
        mock_send.return_value = ACB_BARS_PAYLOAD
        quote.history(start="2025-09-11", end="2025-09-12", interval="1D")

    assert mock_send.call_count == 1
    url = mock_send.call_args.kwargs["url"]
    assert url == "https://openapi.tcbs.com.vn/nyx/v2/stock/bars-long-term"


@pytest.mark.unit
def test_history_intraday_interval_calls_bars_endpoint():
    quote = TCBSQuote("ACB", show_log=False)
    with patch("vnbroker.core.utils.client.send_request") as mock_send:
        mock_send.return_value = ACB_BARS_PAYLOAD
        quote.history(start="2025-09-12", end="2025-09-12", interval="5m")

    url = mock_send.call_args.kwargs["url"]
    assert url == "https://openapi.tcbs.com.vn/nyx/v2/stock/bars"


# --- AC6: docstring cũ không còn khẳng định sai ---------------------------


@pytest.mark.unit
def test_stale_claim_about_missing_bars_endpoint_is_gone():
    source = TCBSQuote.history.__doc__ or ""
    combined = source + (TCBSQuote._compute_ohlc_from_intraday.__doc__ or "")
    assert "does not support historical multi-day" not in combined
    assert "OHLC bars endpoint is not available" not in combined


# --- AC7: map D/W/M riêng, không dùng _INTERVAL_MAP (map 1M -> 'ME') ------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("interval_key", "expected_path", "expected_resolution"),
    [
        ("1D", "/nyx/v2/stock/bars-long-term", "D"),
        ("1W", "/nyx/v2/stock/bars-long-term", "W"),
        ("1M", "/nyx/v2/stock/bars-long-term", "M"),
        ("1m", "/nyx/v2/stock/bars", "1"),
        ("5m", "/nyx/v2/stock/bars", "5"),
        ("15m", "/nyx/v2/stock/bars", "15"),
        ("30m", "/nyx/v2/stock/bars", "30"),
        ("1H", "/nyx/v2/stock/bars", "60"),
    ],
)
def test_resolve_bars_endpoint_maps_interval(interval_key, expected_path, expected_resolution):
    resolved = bars.resolve_bars_endpoint(interval_key)

    assert resolved["path"] == expected_path
    assert resolved["resolution"] == expected_resolution


@pytest.mark.unit
def test_month_interval_never_maps_to_pandas_me():
    """`_INTERVAL_MAP['1M'] = 'ME'` là tần số pandas, spec TCBS quy định `M`."""
    from vnbroker.explorer.tcbs.const import _INTERVAL_MAP

    assert _INTERVAL_MAP["1M"] == "ME"
    assert bars.resolve_bars_endpoint("1M")["resolution"] == "M"


@pytest.mark.unit
def test_unsupported_interval_raises_value_error_with_guidance():
    with pytest.raises(ValueError, match="không hỗ trợ interval"):
        bars.resolve_bars_endpoint("2H")


# --- AC8: _TIMEFRAME_MAP nằm ở const.py (tránh circular import) ----------


@pytest.mark.unit
def test_timeframe_map_lives_in_const_and_is_reexported_by_quote():
    from vnbroker.explorer.tcbs.const import _TIMEFRAME_MAP
    from vnbroker.explorer.tcbs.quote import _TIMEFRAME_MAP as quote_map

    assert quote_map is _TIMEFRAME_MAP
    assert _TIMEFRAME_MAP["1M"] == "1M"


@pytest.mark.unit
def test_bars_module_does_not_import_quote():
    """`quote.py` import `bars`; nếu `bars` import ngược lại `quote` sẽ vòng.

    Quét **cây AST** (`import ... from`), không quét chuỗi thô — docstring của
    `bars.py` nhắc tới `Quote._as_df` để giải thích AC9, đó là comment chứ
    không phải import.
    """
    import vnbroker.explorer.tcbs.bars as bars_module

    tree = ast.parse(_source_of(bars_module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.name)
                if node.module:
                    imported.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)

    assert not any("quote" in name for name in imported), imported


# --- AC9: không đi qua _as_df / ohlc_to_df (transform cắt tz) --------------


@pytest.mark.unit
def test_bars_module_does_not_call_ohlc_to_df():
    """AC9: `bars.py` phải tự dựng frame, không đi qua `transform.ohlc_to_df`.

    `transform.py:402` `.dt.tz_localize(None)` + `:406` `.dt.date` cắt tz và
    cắt giờ. Quét **tên hàm được gọi** trong AST, bỏ qua docstring/comment.
    """
    import vnbroker.explorer.tcbs.bars as bars_module

    tree = ast.parse(_source_of(bars_module))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    called |= {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "ohlc_to_df" not in called
    assert "_as_df" not in called
    # Vẫn được phép chuẩn hoá giá (không đụng cột `time`).
    assert "normalize_ohlc_prices" in called


@pytest.mark.unit
def test_bars_path_keeps_time_of_day_intraday():
    """`transform.ohlc_to_df` cắt giờ (transform.py:402,406) nên nến trong
    phiên sẽ mất HH:MM. Frame của `bars` phải giữ trọn."""
    payload = {
        "ticker": "ACB",
        "data": [
            {
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "volume": 1000,
                "tradingDate": "2025-09-12T02:15:00Z",
            }
        ],
    }

    df = bars.bars_to_frame(
        payload,
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="5m",
    )

    assert df["time"].iloc[0].strftime("%Y-%m-%d %H:%M:%S") == "2025-09-12 09:15:00"


# --- AC10: quote.py <= 800L -------------------------------------------------


@pytest.mark.unit
def test_quote_module_stays_under_800_lines():
    import vnbroker.explorer.tcbs.quote as quote_module

    line_count = len(_source_of(quote_module).splitlines())

    assert line_count <= 800, f"quote.py dài {line_count} dòng (>800)"


# --- tham số bắt buộc của spec --------------------------------------------


@pytest.mark.unit
def test_build_bars_params_sends_all_five_required_params():
    params = bars.build_bars_params(
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="1D",
        start="2025-09-01",
        end="2025-09-12",
    )

    assert set(params) == {"ticker", "type", "resolution", "to", "countBack"}
    assert params["ticker"] == "ACB"
    assert params["type"] == "stock"
    assert params["resolution"] == "D"
    assert isinstance(params["to"], int)
    assert params["countBack"] >= 1


@pytest.mark.unit
def test_end_epoch_is_end_of_day_vietnam_time():
    """`to` là mốc cuối; lấy cuối ngày giờ VN để nến của chính `end` nằm
    trong cửa sổ lấy ngược."""
    epoch = bars._end_epoch("2025-09-12")

    assert pd.Timestamp(epoch, unit="s", tz="UTC").tz_convert(
        "Asia/Ho_Chi_Minh"
    ).strftime("%Y-%m-%d %H:%M:%S") == "2025-09-12 23:59:59"


@pytest.mark.unit
def test_index_asset_type_uses_spec_type_value():
    params = bars.build_bars_params(
        symbol="VNINDEX",
        asset_type=InstrumentType.INDEX,
        interval_key="1D",
        start="2025-09-01",
        end="2025-09-12",
    )

    assert params["type"] == "index"


@pytest.mark.unit
def test_unsupported_asset_type_raises_value_error():
    with pytest.raises(ValueError, match="không hỗ trợ loại tài sản"):
        bars.build_bars_params(
            symbol="ACB",
            asset_type="bond",
            interval_key="1D",
            start="2025-09-01",
            end="2025-09-12",
        )


# --- frame rỗng vẫn đúng schema + tz --------------------------------------


@pytest.mark.unit
def test_empty_response_returns_typed_empty_frame_with_tz():
    df = bars.bars_to_frame(
        {"ticker": "ACB", "data": []},
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="1D",
    )

    assert df.empty
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert str(df["time"].dtype) == f"datetime64[ns, Asia/Ho_Chi_Minh]"


@pytest.mark.unit
def test_none_payload_returns_typed_empty_frame():
    df = bars.bars_to_frame(
        None,
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="1W",
    )

    assert df.empty
    assert str(df["time"].dtype) == f"datetime64[ns, Asia/Ho_Chi_Minh]"


# --- lọc khoảng + sắp xếp --------------------------------------------------


@pytest.mark.unit
def test_bars_to_frame_filters_and_sorts_by_time():
    df = bars.bars_to_frame(
        ACB_BARS_PAYLOAD,
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="1D",
        start="2025-09-12",
        end="2025-09-12",
    )

    assert len(df) == 1
    assert df["time"].iloc[0].strftime("%Y-%m-%d") == "2025-09-12"
    assert df["time"].is_monotonic_increasing


@pytest.mark.unit
def test_bars_to_frame_sets_metadata_attrs():
    df = bars.bars_to_frame(
        ACB_BARS_PAYLOAD,
        symbol="ACB",
        asset_type=InstrumentType.STOCK,
        interval_key="1D",
        start="2025-09-11",
        end="2025-09-12",
    )

    assert df.attrs["symbol"] == "ACB"
    assert df.attrs["source"] == "TCBS"
    assert df.attrs["interval"] == "1D"
    assert df.attrs["start"] == "2025-09-11"
    assert df.attrs["end"] == "2025-09-12"


# --- countBack ---------------------------------------------------------------


@pytest.mark.unit
def test_count_back_scales_with_window_length():
    short = bars.compute_count_back("1D", "D", "2025-09-11", "2025-09-12")
    long = bars.compute_count_back("1D", "D", "2025-01-01", "2025-09-12")

    assert 0 < short < long


@pytest.mark.unit
def test_count_back_is_capped_to_guard_rail():
    capped = bars.compute_count_back("1m", "1", "2000-01-01", "2025-09-12")

    assert capped == bars._MAX_COUNT_BACK


@pytest.mark.unit
def test_count_back_minimum_is_at_least_one():
    assert bars.compute_count_back("1D", "D", "2025-09-12", "2025-09-12") >= 1