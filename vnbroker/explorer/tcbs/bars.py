"""OHLCV bars cho TCBS (2 endpoint trong `openapi-v1.0.0.json`).

Spec: `GET /nyx/v2/stock/bars-long-term` (D/W/M) và `GET /nyx/v2/stock/bars`
(phút/giờ). Cả hai cùng bộ tham số bắt buộc::

    ticker, type, resolution, to (epoch giây), countBack

Response::

    {ticker: str, data: [{open, high, low, close, volume, tradingDate}]}

`tradingDate` là ISO-8601 **UTC** (vd ``2025-09-12T00:00:00Z``).

⚠ **Không** đi qua ``transform.ohlc_to_df`` / ``Quote._as_df``: ``transform.py:402``
``.dt.tz_localize(None)`` và ``transform.py:406`` ``.dt.date`` cắt tz và cắt giờ,
làm mất tz-aware ``Asia/Ho_Chi_Minh`` và làm ngày giao dịch dịch chứ không
chỉ đổi nhãn UTC. Ở đây ``tz_convert`` được gọi **tường minh** rồi mới chuẩn
hoá giá.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import pandas as pd

from vnbroker.core.utils import client, transform
from vnbroker.core.utils.logger import get_logger

# `get_logger` chưa có chữ ký kiểu. `quote.py` đã có lỗi này trong baseline
# mypy; `bars.py` là file mới nên lỗi đó sẽ bị tính là MỚI — suppress tại
# đúng chỗ thay vì nới `--strict`.
logger = get_logger(__name__)  # type: ignore[no-untyped-call]

# Base URL của spec (`openapi-v1.0.0.json` → servers[0].url). Import cố định
# thay vì import từ `const` để `bars.py` không phụ thuộc thêm bảng của quote.
_BARS_BASE_URL = "https://openapi.tcbs.com.vn"

_BARS_LONG_TERM_PATH = "/nyx/v2/stock/bars-long-term"
_BARS_INTRADAY_PATH = "/nyx/v2/stock/bars"

# --- resolution ------------------------------------------------------------
# AC S1#7: map RIÊNG `D/W/M` ở đây, KHÔNG dùng `_INTERVAL_MAP` (const.py) —
# `_INTERVAL_MAP['1M'] = 'ME'` là tần số pandas (month-end), còn spec TCBS quy
# định `resolution: D | W | M`.
_LONG_TERM_RESOLUTION: Dict[str, str] = {
    "1D": "D",
    "1W": "W",
    "1M": "M",
}

# `/nyx/v2/stock/bars` quy định resolution **tính bằng phút** (vd `60` = nến
# 60 phút), không phải `1H` cũng không phải `1`.
_INTRADAY_RESOLUTION: Dict[str, str] = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1H": "60",
}

LONG_TERM_INTERVALS = tuple(_LONG_TERM_RESOLUTION)
INTRADAY_INTERVALS = tuple(_INTRADAY_RESOLUTION)

# --- tham số `type` --------------------------------------------------------
# Spec: "Ticker type: stock, coveredWarr (covered warrant), index, derivative."
# `InstrumentType` của repo dùng đúng các chuỗi này cho 4 loại trên.
# `bond` KHÔNG có trong spec ⇒ không đoán, ném lỗi rõ ràng.
_SUPPORTED_TICKER_TYPES = frozenset(
    {"stock", "coveredWarr", "index", "derivative"}
)

# --- tính `countBack` ------------------------------------------------------
# `countBack` = số nến lấy ngược từ `to`. Spec không nói cách ánh xạ khoảng
# ngày → số nến, nên dùng hệ số ước lượng có ghi chú (chưa probe server được).
# Số phiên giao dịch trên tổng số ngày dương lịch ~0.70 (HOSE ~250/365).
_TRADING_DAY_RATIO = 0.70

# Số nến mỗi phiên giao dịch, theo độ phân giải phút.
# 1m: HOSE 09:15-11:30 + 13:00-14:45 + ATC ≈ 330 nến.
_INTRADAY_BARS_PER_DAY: Dict[str, int] = {
    "1": 330,
    "5": 66,
    "15": 22,
    "30": 11,
    "60": 6,
}

# Chặn trần để không dựng `countBack` khổng lồ. B-18 (docs/audit/S2_EXPLORER.md)
# đã ghi nhận VCI gửi `countBack=266221` trong MỘT request không phân trang.
_MAX_COUNT_BACK = 20000

_TZ = "Asia/Ho_Chi_Minh"
_STANDARD_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


def resolve_bars_endpoint(interval_key: str) -> Dict[str, Any]:
    """Trả ``{path, resolution}`` cho `interval_key`.

    `bars-long-term` nhận D/W/M; `bars` nhận độ phân giải tính bằng phút.
    """
    if interval_key in _LONG_TERM_RESOLUTION:
        return {
            "path": _BARS_LONG_TERM_PATH,
            "resolution": _LONG_TERM_RESOLUTION[interval_key],
            "long_term": True,
        }
    if interval_key in _INTRADAY_RESOLUTION:
        return {
            "path": _BARS_INTRADAY_PATH,
            "resolution": _INTRADAY_RESOLUTION[interval_key],
            "long_term": False,
        }
    msg = (
        f"TCBS không hỗ trợ interval {interval_key!r} qua endpoint bars. "
        f"Khung dài hạn: {', '.join(LONG_TERM_INTERVALS)}. "
        f"Khung trong phiên: {', '.join(INTRADAY_INTERVALS)}."
    )
    raise ValueError(msg)


def _ticker_type(asset_type: Any) -> str:
    """Chuẩn hoá `asset_type` nội bộ → tham số `type` của spec."""
    raw = getattr(asset_type, "value", asset_type)
    value = str(raw).strip()
    if value not in _SUPPORTED_TICKER_TYPES:
        msg = (
            f"TCBS bars không hỗ trợ loại tài sản {value!r}. "
            f"Spec openapi-v1.0.0.json chỉ liệt kê: "
            f"{', '.join(sorted(_SUPPORTED_TICKER_TYPES))}."
        )
        raise ValueError(msg)
    return value


def _end_epoch(end: str) -> int:
    """`end` ('YYYY-MM-DD') → epoch giây, lấy **cuối ngày** giờ VN.

    Cuối ngày để nến giao dịch của chính `end` (mốc `00:00:00Z` tức
    `07:00+07`) vẫn nằm trong cửa sổ lấy ngược từ `to`.
    """
    day = pd.Timestamp(end).tz_localize(_TZ)
    end_of_day = day + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    epoch_nanos: int = end_of_day.value
    return int(epoch_nanos // 1_000_000_000)


def compute_count_back(interval_key: str, resolution: str, start: str, end: str) -> int:
    """Số nến cần lấy ngược từ `to` để phủ khoảng ``[start, end]``."""
    span_days: int = (pd.Timestamp(end) - pd.Timestamp(start)).days
    days = max(span_days + 1, 1)
    sessions = max(1, math.ceil(days * _TRADING_DAY_RATIO))

    if resolution in _LONG_TERM_RESOLUTION.values():
        per_bar = {"D": 1.0, "W": 5.0, "M": 21.0}[resolution]
        needed = math.ceil(sessions / per_bar)
    else:
        per_day = _INTRADAY_BARS_PER_DAY.get(resolution, 330)
        needed = sessions * per_day

    # +2 nến dự phòng cho phiên chưa đóng / lệch phiên lịch.
    count_back = max(1, needed + 2)
    if count_back > _MAX_COUNT_BACK:
        logger.warning(
            "TCBS bars: countBack=%s bị chặn trần còn %s "
            "(khoảng %s→%s, interval=%s). Phạm vi trả về có thể bị cắt.",
            count_back, _MAX_COUNT_BACK, start, end, interval_key,
        )
        count_back = _MAX_COUNT_BACK
    return count_back


def build_bars_params(
    *,
    symbol: str,
    asset_type: Any,
    interval_key: str,
    start: str,
    end: str,
) -> Dict[str, Any]:
    """Dựng đủ 5 tham số bắt buộc của spec cho 1 lời gọi bars."""
    endpoint = resolve_bars_endpoint(interval_key)
    resolution = endpoint["resolution"]
    return {
        "ticker": symbol,
        "type": _ticker_type(asset_type),
        "resolution": resolution,
        "to": _end_epoch(end),
        "countBack": compute_count_back(
            interval_key, resolution, start, end
        ),
    }


def _empty_frame(symbol: str, asset_type: Any, interval_key: str) -> pd.DataFrame:
    """Frame rỗng nhưng **vẫn đúng schema + tz-aware** như frame có dữ liệu."""
    df = pd.DataFrame({col: pd.Series(dtype="object") for col in _STANDARD_COLUMNS})
    df["time"] = pd.Series(dtype=f"datetime64[ns, {_TZ}]")
    for col in ("open", "high", "low", "close"):
        df[col] = pd.Series(dtype="float64")
    df["volume"] = pd.Series(dtype="int64")
    df = transform.normalize_ohlc_prices(
        df,
        asset_type=asset_type,
        columns=["open", "high", "low", "close"],
        floating=2,
    )
    df.attrs["symbol"] = symbol
    df.attrs["source"] = "TCBS"
    df.attrs["interval"] = interval_key
    return df


def bars_to_frame(
    payload: Optional[Dict[str, Any]],
    *,
    symbol: str,
    asset_type: Any,
    interval_key: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    show_log: bool = False,
) -> pd.DataFrame:
    """Parse response `bars` → frame chuẩn ``time, open, high, low, close, volume``.

    Mọi field đọc bằng ``.get()``: server TCBS còn trả field **không có trong
    spec** (quan sát thật: ``dataT1: null``, không nằm trong cả
    `openapi-v1.0.0.json` lẫn tài liệu developers), và frame đầu ra chỉ giữ
    đúng 6 cột chuẩn.
    """
    records = (payload or {}).get("data") or []
    if not records:
        if show_log:
            logger.info(
                "TCBS bars: %s không có dữ liệu cho interval %s",
                symbol, interval_key,
            )
        return _empty_frame(symbol, asset_type, interval_key)

    rows = [
        {
            "time": record.get("tradingDate"),
            "open": record.get("open"),
            "high": record.get("high"),
            "low": record.get("low"),
            "close": record.get("close"),
            "volume": record.get("volume"),
        }
        for record in records
        if isinstance(record, dict)
    ]
    if not rows:
        return _empty_frame(symbol, asset_type, interval_key)

    # `columns=` cố định ⇒ frame KHÔNG bao giờ mang field lạ của server.
    df = pd.DataFrame(rows, columns=_STANDARD_COLUMNS)

    # `tradingDate` là ISO-8601 UTC. `utc=True` để hiểu đúng hậu tố `Z`, rồi
    # `tz_convert` **tường minh** sang giờ giao dịch VN. Không dùng
    # `tz_localize` ở đây: `Normalizer` (core/utils/normalizer.py:22-24) chỉ
    # `tz_localize` khi cột chưa có tz, nên frame UTC sẽ đi qua nguyên vẹn.
    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    df = df.dropna(subset=["time"])
    if df.empty:
        return _empty_frame(symbol, asset_type, interval_key)
    df["time"] = df["time"].dt.tz_convert(_TZ)

    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    df = transform.normalize_ohlc_prices(
        df,
        asset_type=asset_type,
        columns=["open", "high", "low", "close"],
        floating=2,
    )

    df = df[_STANDARD_COLUMNS]
    df = df.sort_values("time").reset_index(drop=True)

    if start:
        lower = pd.Timestamp(start).tz_localize(_TZ)
        df = df[df["time"] >= lower]
    if end:
        upper = (
            pd.Timestamp(end).tz_localize(_TZ)
            + pd.Timedelta(days=1)
            - pd.Timedelta(seconds=1)
        )
        df = df[df["time"] <= upper]
    df = df.reset_index(drop=True)

    # Volume là số cổ phiếu/hợp đồng. Ép int64 chỉ khi không mất dữ liệu.
    try:
        df["volume"] = df["volume"].round().astype("int64")
    except (TypeError, ValueError, OverflowError):
        logger.debug("TCBS bars: volume không ép int64 được, giữ float.")

    df.attrs["symbol"] = symbol
    df.attrs["source"] = "TCBS"
    df.attrs["interval"] = interval_key
    if start:
        df.attrs["start"] = start
    if end:
        df.attrs["end"] = end

    if show_log:
        logger.info(
            "TCBS bars: %s interval=%s trả về %d nến "
            "(%s → %s, tz-aware %s)",
            symbol, interval_key, len(df), start, end, _TZ,
        )
    return df


def fetch_bars(
    *,
    symbol: str,
    headers: Dict[str, str],
    asset_type: Any,
    start: str,
    end: str,
    interval_key: str,
    proxy_mode: Any = None,
    proxy_list: Optional[List[Any]] = None,
    show_log: bool = False,
) -> pd.DataFrame:
    """Gọi đúng endpoint bars theo `interval_key` và trả frame đã chuẩn hoá."""
    endpoint = resolve_bars_endpoint(interval_key)
    params = build_bars_params(
        symbol=symbol,
        asset_type=asset_type,
        interval_key=interval_key,
        start=start,
        end=end,
    )
    url = f"{_BARS_BASE_URL}{endpoint['path']}"

    try:
        payload = client.send_request(
            url=url,
            headers=headers,
            method="GET",
            params=params,
            show_log=show_log,
            proxy_list=proxy_list,
            proxy_mode=proxy_mode if proxy_mode is not None else "try",
        )
    except Exception as exc:
        if "401" in str(exc) or "Unauthorized" in str(exc):
            raise ConnectionError(
                "TCBS iFlash OpenAPI requires valid JWT token cho endpoint "
                "bars. Get JWT by exchanging API key + OTP via "
                "POST /gaia/v1/oauth2/openapi/token, then set "
                "TCBS_JWT_TOKEN=<JWT> environment variable."
            ) from exc
        raise

    return bars_to_frame(
        payload,
        symbol=symbol,
        asset_type=asset_type,
        interval_key=interval_key,
        start=start,
        end=end,
        show_log=show_log,
    )