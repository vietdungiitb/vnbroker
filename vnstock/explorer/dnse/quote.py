"""
vnstock/explorer/dnse/quote.py

DNSE Quote provider - maps DNSE LightSpeed OpenAPI market data
vào giao diện chuẩn của vnstock (history, intraday, price_depth).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from vnstock.core.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Interval → DNSE bar_type mapping
# ---------------------------------------------------------------------------
_INTERVAL_TO_BAR_TYPE: dict[str, str] = {
    "1m": "1",        # 1-minute (DNSE dùng số cho intraday)
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1H": "60",
    "1D": "D",
    "1W": "W",
    "1M": "M",
}

# Alias phổ biến
_INTERVAL_ALIASES: dict[str, str] = {
    "d": "1D",
    "day": "1D",
    "daily": "1D",
    "w": "1W",
    "week": "1W",
    "weekly": "1W",
    "m": "1M",
    "month": "1M",
    "monthly": "1M",
    "h": "1H",
    "hour": "1H",
    "1h": "1H",
}

# OHLC response key aliases - DNSE có thể trả về nhiều tên khác nhau
_OHLC_RESPONSE_KEYS = ("bars", "data", "items", "candles", "ohlc")

# Mapping cột raw → standard
_OHLC_COLUMN_MAP: dict[str, str] = {
    "t": "time",
    "time": "time",
    "timestamp": "time",
    "o": "open",
    "open": "open",
    "h": "high",
    "high": "high",
    "l": "low",
    "low": "low",
    "c": "close",
    "close": "close",
    "v": "volume",
    "volume": "volume",
    "vol": "volume",
}

_TRADES_COLUMN_MAP: dict[str, str] = {
    "t": "time",
    "time": "time",
    "p": "price",
    "price": "price",
    "v": "volume",
    "volume": "volume",
    "q": "volume",
    "qty": "volume",
    "s": "side",
    "side": "side",
    "bs": "side",
}


def _normalize_interval(interval: str) -> str:
    """Chuẩn hoá chuỗi interval về dạng chuẩn ('1D', '1W', ...)."""
    norm = interval.strip()
    lower = norm.lower()
    return _INTERVAL_ALIASES.get(lower, norm)


def _to_unix_seconds(date_str: str) -> int:
    """Convert YYYY-MM-DD string sang Unix timestamp (giây, UTC)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _extract_ohlc_list(body: dict | list | None) -> list:
    """Tìm list OHLC bên trong response body."""
    if body is None:
        return []
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        if any(key in body for key in ("t", "time", "timestamp", "o", "open", "h", "high", "l", "low", "c", "close", "v", "volume")):
            return [body]
    for key in _OHLC_RESPONSE_KEYS:
        value = body.get(key)
        if isinstance(value, list):
            return value
    return []


def _parse_ohlc(records: list) -> pd.DataFrame:
    """Parse list raw OHLC records → DataFrame chuẩn."""
    if not records:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    df = pd.json_normalize(records)
    # Rename columns
    df.rename(columns={k: v for k, v in _OHLC_COLUMN_MAP.items() if k in df.columns}, inplace=True)

    # Convert timestamp → datetime (DNSE dùng Unix seconds)
    if "time" in df.columns:
        if pd.api.types.is_numeric_dtype(df["time"]):
            df["time"] = (
                pd.to_datetime(df["time"], unit="s", utc=True)
                .dt.tz_localize(None)
                .astype("datetime64[ns]")
            )
        else:
            df["time"] = pd.to_datetime(df["time"], errors="coerce")

    # Đảm bảo các cột số đúng dtype
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")

    # Sắp xếp theo thời gian
    if "time" in df.columns:
        df = df.sort_values("time").reset_index(drop=True)

    # Chỉ giữ các cột chuẩn
    keep = [c for c in ("time", "open", "high", "low", "close", "volume") if c in df.columns]
    return df[keep]


def _parse_trades(records: list) -> pd.DataFrame:
    """Parse list raw trade records → DataFrame chuẩn."""
    if not records:
        return pd.DataFrame(columns=["time", "price", "volume", "side"])

    df = pd.json_normalize(records)
    df.rename(columns={k: v for k, v in _TRADES_COLUMN_MAP.items() if k in df.columns}, inplace=True)

    if "time" in df.columns:
        if pd.api.types.is_numeric_dtype(df["time"]):
            df["time"] = (
                pd.to_datetime(df["time"], unit="s", utc=True)
                .dt.tz_localize(None)
                .astype("datetime64[ns]")
            )
        else:
            df["time"] = pd.to_datetime(df["time"], errors="coerce")

    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")

    keep = [c for c in ("time", "price", "volume", "side") if c in df.columns]
    return df[keep]


class DNSEQuote:
    """
    DNSE Quote provider.

    Lấy dữ liệu giá lịch sử và giao dịch intraday từ DNSE LightSpeed OpenAPI.
    Cần có DNSE_API_KEY và DNSE_API_SECRET (môi trường hoặc tham số trực tiếp).

    Ví dụ:
        >>> q = DNSEQuote("VNM", api_key="...", api_secret="...")
        >>> df = q.history(start="2024-01-01", end="2024-06-30")
    """

    def __init__(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        **kwargs,
    ):
        from vnstock.connector.dnse.client import DNSEClient

        self.symbol = symbol.upper()
        self.show_log = show_log
        resolved_key = api_key or os.environ.get("DNSE_API_KEY", "")
        resolved_secret = api_secret or os.environ.get("DNSE_API_SECRET", "")

        if not resolved_key or not resolved_secret:
            raise ValueError(
                "DNSE cần api_key và api_secret. "
                "Cung cấp trực tiếp hoặc đặt biến môi trường DNSE_API_KEY và DNSE_API_SECRET. "
                "Đăng ký tại: https://developers.dnse.com.vn/"
            )

        self._client = DNSEClient(
            api_key=resolved_key,
            api_secret=resolved_secret,
            show_log=show_log,
        )
        self._market = self._client._market

    # ------------------------------------------------------------------
    # history
    # ------------------------------------------------------------------
    def history(
        self,
        symbol: Optional[str] = None,
        start: str = "2024-01-01",
        end: Optional[str] = None,
        interval: str = "1D",
        **kwargs,
    ) -> pd.DataFrame:
        """
        Lấy dữ liệu OHLCV lịch sử từ DNSE.

        Tham số:
            symbol (str, tùy chọn): Mã CK. Mặc định là symbol khởi tạo.
            start (str): Ngày bắt đầu 'YYYY-MM-DD'. Mặc định '2024-01-01'.
            end (str, tùy chọn): Ngày kết thúc 'YYYY-MM-DD'. Mặc định hôm nay.
            interval (str): Khung thời gian '1D','1W','1M','1H','1m','5m','15m','30m'.

        Trả về:
            pd.DataFrame với cột: time, open, high, low, close, volume
        """
        sym = (symbol or self.symbol).upper()
        if not end:
            end = datetime.now().strftime("%Y-%m-%d")

        _ = _normalize_interval(interval)
        bar_type = "STOCK"

        from_ts = _to_unix_seconds(start)
        to_ts = _to_unix_seconds(end) + 86399  # đến cuối ngày end

        query = {
            "symbol": sym,
            "from": from_ts,
            "to": to_ts,
        }

        try:
            _, body = self._market.get_ohlc(bar_type=bar_type, query=query)
        except Exception as exc:
            logger.warning("DNSE get_ohlc lỗi: %s", exc)
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        records = _extract_ohlc_list(body)
        df = _parse_ohlc(records)
        if self.show_log:
            logger.info("DNSE history: %s rows, symbol=%s, %s→%s", len(df), sym, start, end)
        return df

    # ------------------------------------------------------------------
    # intraday
    # ------------------------------------------------------------------
    def intraday(
        self,
        symbol: Optional[str] = None,
        page_size: int = 100,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Lấy dữ liệu giao dịch intraday (khớp lệnh) từ DNSE.

        Tham số:
            symbol (str, tùy chọn): Mã CK.
            page_size (int): Số lệnh tối đa trả về. Mặc định 100.

        Trả về:
            pd.DataFrame với cột: time, price, volume, side
        """
        sym = (symbol or self.symbol).upper()
        try:
            _, body = self._market.get_trades(symbol=sym, limit=page_size)
        except Exception as exc:
            logger.warning("DNSE get_trades lỗi: %s", exc)
            return pd.DataFrame(columns=["time", "price", "volume", "side"])

        if body is None:
            return pd.DataFrame(columns=["time", "price", "volume", "side"])

        records: list = []
        if isinstance(body, list):
            records = body
        elif isinstance(body, dict):
            for key in ("trades", "data", "items"):
                val = body.get(key)
                if isinstance(val, list):
                    records = val
                    break

        df = _parse_trades(records)
        if self.show_log:
            logger.info("DNSE intraday: %s records, symbol=%s", len(df), sym)
        return df

    # ------------------------------------------------------------------
    # price_depth
    # ------------------------------------------------------------------
    def price_depth(
        self,
        symbol: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Trả về thông tin security definition từ DNSE (dùng thay thế price_depth cơ bản).

        Tham số:
            symbol (str, tùy chọn): Mã CK.

        Trả về:
            pd.DataFrame với thông tin định nghĩa chứng khoán.
        """
        sym = (symbol or self.symbol).upper()
        try:
            _, body = self._market.get_security_definition(symbol=sym)
        except Exception as exc:
            logger.warning("DNSE get_security_definition lỗi: %s", exc)
            return pd.DataFrame()

        if body is None:
            return pd.DataFrame()
        if isinstance(body, dict):
            return pd.json_normalize(body)
        if isinstance(body, list):
            return pd.json_normalize(body)
        return pd.DataFrame()
