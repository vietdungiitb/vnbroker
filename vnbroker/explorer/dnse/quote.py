"""
vnbroker/explorer/dnse/quote.py

DNSE Quote provider - maps DNSE LightSpeed OpenAPI market data
vào giao diện chuẩn của vnbroker (history, intraday, price_depth).
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from vnbroker.common.data import EmptyProviderResult
from vnbroker.core.exceptions import RateLimitError
from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.parser import get_asset_type
from vnbroker.core.utils.transform import normalize_ohlc_prices, normalize_intraday_prices

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Interval → DNSE resolution mapping
# ---------------------------------------------------------------------------
# DNSE OpenAPI /price/ohlc uses (per docs):
# - type: "STOCK" | "DERIVATIVE" | "INDEX"
# - resolution: "1", "3", "5", "15", "30", "1h", "1D", "1W"
_INTERVAL_TO_RESOLUTION: dict[str, str] = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "1h",
    "1H": "1h",
    "1D": "1D",
    "1W": "1W",
    # Monthly not supported per docs
}

# Alias phổ biến
_INTERVAL_ALIASES: dict[str, str] = {
    "d": "1D",
    "day": "1D",
    "daily": "1D",
    "w": "1W",
    "week": "1W",
    "weekly": "1W",
    "h": "1h",
    "hour": "1h",
    "1h": "1h",
    "1": "1",
    "3": "3",
    "5": "5",
    "15": "15",
    "30": "30",
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
    # DNSE actual field names
    "matchPrice": "price",
    "matchQtty": "volume",
    # Generic aliases
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


_VN_TZ = timezone(timedelta(hours=7))


def _to_vn_day_bounds(date_str: str) -> Tuple[int, int]:
    """Trả về (from_ts, to_ts) Unix seconds cho 1 ngày theo giờ VN (UTC+7)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_start = dt.replace(hour=0, minute=0, second=0, tzinfo=_VN_TZ)
    day_end = dt.replace(hour=23, minute=59, second=59, tzinfo=_VN_TZ)
    return int(day_start.timestamp()), int(day_end.timestamp())


_FAILOVER_MARKERS = (
    "401", "403", "418", "429", "timeout", "timed out", "connection",
    "unauthorized", "forbidden", "rate limit", "too many requests",
    "service unavailable", "temporarily unavailable",
)


def _raise_for_failover(exc: Exception, context: str) -> None:
    """Re-raise auth/network errors as ConnectionError for source_router failover.

    Data-empty cases (404 empty, no data) return empty DF upstream;
    only transient/auth errors should failover.
    """
    msg = str(exc).lower()
    # RateLimitError kế thừa ConnectionError — phải xử lý TRƯỚC để giữ
    # retry_after và để source_router cooldown đúng (SSOT Rev.2 D-09).
    if isinstance(exc, RateLimitError):
        raise exc
    if isinstance(exc, (ConnectionError, TimeoutError)):
        raise ConnectionError(f"DNSE {context} lỗi mạng: {exc}") from exc
    if any(m in msg for m in _FAILOVER_MARKERS):
        raise ConnectionError(f"DNSE {context} lỗi: {exc}") from exc


def _extract_ohlc_list(body: dict | list | None) -> list:
    """Tìm list OHLC bên trong response body."""
    if body is None:
        return []
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        # Check for columnar format (t, o, h, l, c, v arrays)
        if all(key in body for key in ("t", "o", "h", "l", "c", "v")):
            return [body]  # Return as single dict for columnar parsing
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

    # Handle columnar format: single dict with arrays t,o,h,l,c,v
    # (scalar single-row dicts must NOT take this branch)
    if len(records) == 1 and isinstance(records[0], dict):
        rec = records[0]
        if (
            all(key in rec for key in ("t", "o", "h", "l", "c", "v"))
            and isinstance(rec.get("t"), (list, tuple))
        ):
            # Columnar format - convert to row-wise
            t_arr = rec["t"] or []
            n = len(t_arr)
            if n == 0:
                return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
            rows = []
            for i in range(n):
                rows.append({
                    "time": t_arr[i],
                    "open": (rec["o"] or [None]*n)[i],
                    "high": (rec["h"] or [None]*n)[i],
                    "low": (rec["l"] or [None]*n)[i],
                    "close": (rec["c"] or [None]*n)[i],
                    "volume": (rec["v"] or [None]*n)[i],
                })
            df = pd.DataFrame(rows)
        else:
            df = pd.json_normalize(records)
    else:
        df = pd.json_normalize(records)

    # Rename columns
    df.rename(columns={k: v for k, v in _OHLC_COLUMN_MAP.items() if k in df.columns}, inplace=True)

    # Convert timestamp → datetime (DNSE dùng Unix seconds, chuẩn hóa về giờ VN naive
    # để nhất quán với VCI/KBS; trước đây tz_localize(None) ngay sau UTC gây lệch 7h)
    if "time" in df.columns:
        if pd.api.types.is_numeric_dtype(df["time"]):
            df["time"] = (
                pd.to_datetime(df["time"], unit="s", utc=True)
                .dt.tz_convert("Asia/Ho_Chi_Minh")
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
                .dt.tz_convert("Asia/Ho_Chi_Minh")
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
        from vnbroker.connector.dnse.client import DNSEClient

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

        # Trước đây **kwargs bị nuốt, nên `base_url` không bao giờ tới được
        # DNSEClient: tầng explorer chỉ nói được với production. Không có
        # cách nào chạy đường này trên sandbox để kiểm chứng bằng dữ liệu thật.
        # Chỉ truyền các khoá DNSEClient thật sự nhận, phần còn lại bỏ qua.
        _client_opts = {
            key: kwargs[key]
            for key in ("base_url", "timeout_seconds", "api_version", "algorithm")
            if key in kwargs
        }
        self._client = DNSEClient(
            api_key=resolved_key,
            api_secret=resolved_secret,
            show_log=show_log,
            **_client_opts,
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
            end = datetime.now(_VN_TZ).strftime("%Y-%m-%d")

        normalized = _normalize_interval(interval)
        resolution = _INTERVAL_TO_RESOLUTION.get(normalized, "1D")

        from_ts = _to_unix_seconds(start)
        to_ts = _to_unix_seconds(end) + 86399  # đến cuối ngày end

        asset_type = get_asset_type(sym)
        type_param = "STOCK"
        if asset_type == "derivative":
            type_param = "DERIVATIVE"
        elif asset_type == "index":
            type_param = "INDEX"

        query = {
            "symbol": sym,
            "type": type_param,
            "resolution": resolution,
            "from": from_ts,
            "to": to_ts,
        }

        try:
            _, body = self._market.get_ohlc(bar_type=resolution, query=query)
        except Exception as exc:
            _raise_for_failover(exc, "get_ohlc")
            logger.warning("DNSE get_ohlc lỗi: %s", exc)
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        records = _extract_ohlc_list(body)
        df = _parse_ohlc(records)
        df = normalize_ohlc_prices(
            df,
            asset_type=get_asset_type(sym),
            columns=["open", "high", "low", "close"],
        )
        df.attrs["symbol"] = sym
        df.attrs["source"] = "DNSE"
        df.attrs["interval"] = normalized
        if self.show_log:
            logger.info("DNSE history: %s rows, symbol=%s, %s→%s", len(df), sym, start, end)
        return df

    # ------------------------------------------------------------------
    # intraday  (hỗ trợ tape lịch sử theo ngày)
    # ------------------------------------------------------------------
    def intraday(
        self,
        symbol: Optional[str] = None,
        date: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        page_size: Optional[int] = None,
        get_all: bool = False,
        order: str = "asc",
        show_log: Optional[bool] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Lấy dữ liệu lịch sử khớp lệnh (tape) từ DNSE LightSpeed OpenAPI.

        Hỗ trợ cả tape phiên hiện tại lẫn lịch sử theo ngày.

        Tham số:
            symbol (str): Mã CK. Mặc định là symbol khởi tạo.
            date (str): Ngày cụ thể 'YYYY-MM-DD'. Lấy toàn bộ tape 1 ngày.
            start (str): Ngày bắt đầu 'YYYY-MM-DD' cho khoảng ngày.
            end (str): Ngày kết thúc 'YYYY-MM-DD' cho khoảng ngày.
                       Mặc định là hôm nay nếu start được cung cấp.
            page_size (int): Số lệnh tối đa mỗi request API.
                             Mặc định 10 000 khi có date/start, 100 cho phiên hiện tại.
            get_all (bool): Tự động phân trang qua nextPageToken để lấy toàn bộ dữ liệu.
                            Mặc định False.
            order (str): Thứ tự sắp xếp 'asc' (cũ→mới) hoặc 'desc' (mới→cũ).
                         Mặc định 'asc'.
            show_log (bool): Ghi log. Mặc định kế thừa từ __init__.

        Trả về:
            pd.DataFrame với cột: time, price, volume, side

        Ví dụ:
            >>> q = DNSEQuote("ACB", api_key="...", api_secret="...")
            # Tape phiên hiện tại (100 lệnh gần nhất)
            >>> df = q.intraday()
            # Toàn bộ tape ngày 2026-05-15
            >>> df = q.intraday(date="2026-05-15", get_all=True)
            # Tape từ 2026-05-12 đến 2026-05-16
            >>> df = q.intraday(start="2026-05-12", end="2026-05-16", get_all=True)
        """
        sym = (symbol or self.symbol).upper()
        _show = show_log if show_log is not None else self.show_log

        # --- Resolve date range → Unix timestamps (VN timezone UTC+7) ---
        from_ts: Optional[int] = None
        to_ts: Optional[int] = None

        today_str = datetime.now(_VN_TZ).strftime("%Y-%m-%d")

        if date:
            from_ts, to_ts = _to_vn_day_bounds(date)
        elif start:
            from_ts, _ = _to_vn_day_bounds(start)
            _end = end or today_str
            _, to_ts = _to_vn_day_bounds(_end)
        else:
            # Live session: default to today's full day (API requires 'from')
            from_ts, to_ts = _to_vn_day_bounds(today_str)

        # --- Auto page_size (DNSE limit: 1–1000) ---
        if page_size is None:
            page_size = 1000 if (date or start) else 100
        page_size = min(page_size, 1000)  # hard cap

        # --- Fetch (with optional cursor pagination) ---
        all_records: list = []
        next_token: Optional[str] = None

        while True:
            try:
                _, body = self._market.get_trades(
                    symbol=sym,
                    from_date=from_ts,
                    to_date=to_ts,
                    limit=page_size,
                    order=order,
                    next_page_token=next_token,
                )
            except RateLimitError:
                # Rate-limit ở page 2+ KHÔNG được nuốt thành frame cụt (D-09).
                raise
            except Exception as exc:
                # Failover cho lỗi mạng/auth; 404 empty (live trades chưa ổn định)
                # vẫn trả empty best-effort để không fail cứng.
                try:
                    _raise_for_failover(exc, "get_trades")
                except ConnectionError:
                    if not all_records:
                        raise
                logger.warning("DNSE get_trades lỗi: %s", exc)
                break

            if body is None:
                break

            records: list = []
            if isinstance(body, list):
                records = body
            elif isinstance(body, dict):
                for key in ("trades", "data", "items"):
                    val = body.get(key)
                    if isinstance(val, list):
                        records = val
                        break

            all_records.extend(records)

            if not get_all or not records:
                break

            # Cursor pagination
            next_token = None
            if isinstance(body, dict):
                next_token = body.get("nextPageToken") or body.get("next_page_token")
            if not next_token:
                break

        df = _parse_trades(all_records)
        df = normalize_intraday_prices(
            df,
            asset_type=get_asset_type(sym),
            columns=["price"],
        )
        df.attrs["symbol"] = sym
        df.attrs["source"] = "DNSE"
        if _show:
            logger.info(
                "DNSE tape: %s records, symbol=%s, from=%s, to=%s",
                len(df), sym, from_ts, to_ts,
            )
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

        Raises:
            Lỗi vận chuyển/HTTP được **ném nguyên vẹn** — trước đây hàm bắt
            ``Exception`` rồi trả ``DataFrame()``, biến "DNSE không trả lời"
            thành "hôm nay không có giao dịch". Người dùng đọc ``len(df) == 0``
            sẽ kết luận sai nguyên nhân.
            EmptyProviderResult: provider trả về rỗng. Đây là trường hợp
            "không phải lỗi nhưng cũng không dùng được", theo đúng ranh giới
            đã định nghĩa ở `common/data.py:442`.
        """
        sym = (symbol or self.symbol).upper()
        # Không bắt lỗi ở đây: `should_failover` cần nhìn thấy loại lỗi để
        # quyết định có xoay sang provider khác hay không.
        _, body = self._market.get_security_definition(symbol=sym)

        if body is None:
            raise EmptyProviderResult(
                f"DNSE get_security_definition({sym}) tra ve rong: None"
            )
        if isinstance(body, dict):
            if not body:
                raise EmptyProviderResult(
                    f"DNSE get_security_definition({sym}) tra ve dict rong"
                )
            return pd.json_normalize(body)
        if isinstance(body, list):
            if not body:
                raise EmptyProviderResult(
                    f"DNSE get_security_definition({sym}) tra ve list rong"
                )
            return pd.json_normalize(body)
        raise EmptyProviderResult(
            f"DNSE get_security_definition({sym}) tra ve kieu khong mong doi: "
            f"{type(body).__name__}"
        )

    def close_price(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """
        Lấy giá đóng cửa mới nhất cho một mã chứng khoán.

        Tham số:
            symbol (str, tùy chọn): Mã CK. Mặc định là symbol khởi tạo.

        Trả về:
            pd.DataFrame với thông tin giá đóng cửa.
        """
        sym = (symbol or self.symbol).upper()
        try:
            _, body = self._market.get_close_price(symbol=sym)
        except Exception as exc:
            logger.warning("DNSE get_close_price lỗi: %s", exc)
            return pd.DataFrame()

        if body is None:
            return pd.DataFrame()
        if isinstance(body, dict):
            return pd.json_normalize(body)
        if isinstance(body, list):
            return pd.json_normalize(body)
        return pd.DataFrame()

    def latest_trade(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """
        Lấy giao dịch mới nhất cho một mã chứng khoán.

        Tham số:
            symbol (str, tùy chọn): Mã CK. Mặc định là symbol khởi tạo.

        Trả về:
            pd.DataFrame với thông tin giao dịch mới nhất.
        """
        sym = (symbol or self.symbol).upper()
        try:
            _, body = self._market.get_latest_trade(symbol=sym)
        except Exception as exc:
            logger.warning("DNSE get_latest_trade lỗi: %s", exc)
            return pd.DataFrame()

        if body is None:
            return pd.DataFrame()
        if isinstance(body, dict):
            return pd.json_normalize(body)
        if isinstance(body, list):
            return pd.json_normalize(body)
        return pd.DataFrame()

    def working_dates(self) -> pd.DataFrame:
        """
        Lấy danh sách ngày giao dịch (working dates) từ DNSE.

        ⚠ **Đây là lời gọi NETWORK THẬT** sang `GET /market/working-dates`.

        Trước 2026-10-16 method này trả DataFrame rỗng ngay lập tức (0ms) vì
        tầng connector trả về hằng cứng — trông như "không có ngày giao dịch"
        trong khi chưa từng hỏi server. Nay nó gọi thật. Hệ quả cần biết:

        - Trên **sandbox** (`sb-openapi.dnse.com.vn`) path `/market/*` trả 404
          ⇒ rơi vào `except` và trả DataFrame rỗng kèm `logger.warning`.
        - Vì vậy DataFrame rỗng ở đây **không chứng minh** là không có ngày giao
          dịch. Muốn biết chắc thì đọc log, hoặc gọi thẳng
          `DNSEClient.get_working_dates()`.

        Trả về:
            pd.DataFrame **một dòng cho mỗi ngày giao dịch**, cột ``workingDates``.
        """
        try:
            _, body = self._market.get_working_dates()
        except Exception as exc:
            logger.warning(
                "DNSE get_working_dates lỗi (%s) — trả rỗng. Rỗng KHÔNG có nghĩa "
                "là không có ngày giao dịch; xem endpoint /market/working-dates.",
                exc,
            )
            return pd.DataFrame()

        if body is None:
            return pd.DataFrame()
        # Đi qua `normalize_payload` chứ không `pd.json_normalize(body)` trực tiếp:
        # `json_normalize` trên dict có `workingDates` là list-of-scalar cho
        # DataFrame **MỘT dòng** với một cell chứa cả 257 ngày — đúng hình thức
        # "thành công rỗng" mà lát B sinh ra để chữa. `normalize_payload` dùng
        # chung `_to_dataframe` của connector nên tách đúng một dòng mỗi ngày.
        #
        # `normalize_payload` là pass-through với mọi thứ không phải dict/list,
        # nên phải chốt lại kiểu: method khai `-> pd.DataFrame`, trả `str`/`int`
        # sẽ làm người gọi gặp `TypeError` khi `len(df)` hay `df.empty`.
        result = self._client.normalize_payload(body)
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

    # ------------------------------------------------------------------
    # fetch_multiple (bulk operations)
    # ------------------------------------------------------------------
    @classmethod
    def fetch_multiple(
        cls,
        symbols: List[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = "1D",
        show_log: bool = False,
        max_concurrency: int = 8,
    ) -> List[pd.DataFrame]:
        """Fetch history for multiple symbols concurrently.

        Args:
            symbols: List of stock symbols.
            start: Start date 'YYYY-MM-DD'.
            end: End date 'YYYY-MM-DD'.
            interval: Candle interval (default '1D').
            show_log: Enable logging.
            max_concurrency: Max parallel workers (default 8).

        Returns:
            List of DataFrames (one per successful symbol).
        """
        def _fetch_one(symbol: str) -> Optional[pd.DataFrame]:
            try:
                quote = cls(symbol=symbol, show_log=show_log)
                # `history` tự có default cho `start`; chỉ truyền khi caller
                # thực sự chỉ định, để không ghi đè default bằng None.
                history_kwargs: Dict[str, Any] = {"end": end, "interval": interval}
                if start is not None:
                    history_kwargs["start"] = start
                return quote.history(**history_kwargs)
            except Exception:
                return None

        results: List[pd.DataFrame] = []
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            futures = {executor.submit(_fetch_one, sym): sym for sym in symbols}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    results.append(result)

        return results
