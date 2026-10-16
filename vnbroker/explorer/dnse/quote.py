"""
vnbroker/explorer/dnse/quote.py

DNSE Quote provider - maps DNSE LightSpeed OpenAPI market data
vÃ o giao diá»‡n chuáº©n cá»§a vnbroker (history, intraday, price_depth).
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from vnbroker.common.data import EmptyProviderResult
from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.parser import get_asset_type
from vnbroker.core.utils.transform import normalize_ohlc_prices, normalize_intraday_prices

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Interval â†’ DNSE resolution mapping
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

# Alias phá»• biáº¿n
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

# OHLC response key aliases - DNSE cÃ³ thá»ƒ tráº£ vá» nhiá»u tÃªn khÃ¡c nhau
_OHLC_RESPONSE_KEYS = ("bars", "data", "items", "candles", "ohlc")

# Mapping cá»™t raw â†’ standard
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
    """Chuáº©n hoÃ¡ chuá»—i interval vá» dáº¡ng chuáº©n ('1D', '1W', ...)."""
    norm = interval.strip()
    lower = norm.lower()
    return _INTERVAL_ALIASES.get(lower, norm)


def _to_unix_seconds(date_str: str) -> int:
    """Convert YYYY-MM-DD string sang Unix timestamp (giÃ¢y, UTC)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


_VN_TZ = timezone(timedelta(hours=7))


def _to_vn_day_bounds(date_str: str) -> Tuple[int, int]:
    """Tráº£ vá» (from_ts, to_ts) Unix seconds cho 1 ngÃ y theo giá» VN (UTC+7)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_start = dt.replace(hour=0, minute=0, second=0, tzinfo=_VN_TZ)
    day_end = dt.replace(hour=23, minute=59, second=59, tzinfo=_VN_TZ)
    return int(day_start.timestamp()), int(day_end.timestamp())


_FAILOVER_MARKERS = (
    "401", "403", "429", "timeout", "timed out", "connection",
    "unauthorized", "forbidden", "rate limit", "too many requests",
    "service unavailable", "temporarily unavailable",
)


def _raise_for_failover(exc: Exception, context: str) -> None:
    """Re-raise auth/network errors as ConnectionError for source_router failover.

    Data-empty cases (404 empty, no data) return empty DF upstream;
    only transient/auth errors should failover.
    """
    msg = str(exc).lower()
    if isinstance(exc, (ConnectionError, TimeoutError)):
        raise ConnectionError(f"DNSE {context} lá»—i máº¡ng: {exc}") from exc
    if any(m in msg for m in _FAILOVER_MARKERS):
        raise ConnectionError(f"DNSE {context} lá»—i: {exc}") from exc


def _extract_ohlc_list(body: dict | list | None) -> list:
    """TÃ¬m list OHLC bÃªn trong response body."""
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
    """Parse list raw OHLC records â†’ DataFrame chuáº©n."""
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

    # Convert timestamp â†’ datetime (DNSE dÃ¹ng Unix seconds, chuáº©n hÃ³a vá» giá» VN naive
    # Ä‘á»ƒ nháº¥t quÃ¡n vá»›i VCI/KBS; trÆ°á»›c Ä‘Ã¢y tz_localize(None) ngay sau UTC gÃ¢y lá»‡ch 7h)
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

    # Äáº£m báº£o cÃ¡c cá»™t sá»‘ Ä‘Ãºng dtype
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")

    # Sáº¯p xáº¿p theo thá»i gian
    if "time" in df.columns:
        df = df.sort_values("time").reset_index(drop=True)

    # Chá»‰ giá»¯ cÃ¡c cá»™t chuáº©n
    keep = [c for c in ("time", "open", "high", "low", "close", "volume") if c in df.columns]
    return df[keep]


def _parse_trades(records: list) -> pd.DataFrame:
    """Parse list raw trade records â†’ DataFrame chuáº©n."""
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

    Láº¥y dá»¯ liá»‡u giÃ¡ lá»‹ch sá»­ vÃ  giao dá»‹ch intraday tá»« DNSE LightSpeed OpenAPI.
    Cáº§n cÃ³ DNSE_API_KEY vÃ  DNSE_API_SECRET (mÃ´i trÆ°á»ng hoáº·c tham sá»‘ trá»±c tiáº¿p).

    VÃ­ dá»¥:
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
                "DNSE cáº§n api_key vÃ  api_secret. "
                "Cung cáº¥p trá»±c tiáº¿p hoáº·c Ä‘áº·t biáº¿n mÃ´i trÆ°á»ng DNSE_API_KEY vÃ  DNSE_API_SECRET. "
                "ÄÄƒng kÃ½ táº¡i: https://developers.dnse.com.vn/"
            )

        # TrÆ°á»›c Ä‘Ã¢y **kwargs bá»‹ nuá»‘t, nÃªn `base_url` khÃ´ng bao giá» tá»›i Ä‘Æ°á»£c
        # DNSEClient: táº§ng explorer chá»‰ nÃ³i Ä‘Æ°á»£c vá»›i production. KhÃ´ng cÃ³
        # cÃ¡ch nÃ o cháº¡y Ä‘Æ°á»ng nÃ y trÃªn sandbox Ä‘á»ƒ kiá»ƒm chá»©ng báº±ng dá»¯ liá»‡u tháº­t.
        # Chá»‰ truyá»n cÃ¡c khoÃ¡ DNSEClient tháº­t sá»± nháº­n, pháº§n cÃ²n láº¡i bá» qua.
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
        Láº¥y dá»¯ liá»‡u OHLCV lá»‹ch sá»­ tá»« DNSE.

        Tham sá»‘:
            symbol (str, tÃ¹y chá»n): MÃ£ CK. Máº·c Ä‘á»‹nh lÃ  symbol khá»Ÿi táº¡o.
            start (str): NgÃ y báº¯t Ä‘áº§u 'YYYY-MM-DD'. Máº·c Ä‘á»‹nh '2024-01-01'.
            end (str, tÃ¹y chá»n): NgÃ y káº¿t thÃºc 'YYYY-MM-DD'. Máº·c Ä‘á»‹nh hÃ´m nay.
            interval (str): Khung thá»i gian '1D','1W','1M','1H','1m','5m','15m','30m'.

        Tráº£ vá»:
            pd.DataFrame vá»›i cá»™t: time, open, high, low, close, volume
        """
        sym = (symbol or self.symbol).upper()
        if not end:
            end = datetime.now(_VN_TZ).strftime("%Y-%m-%d")

        normalized = _normalize_interval(interval)
        resolution = _INTERVAL_TO_RESOLUTION.get(normalized, "1D")

        from_ts = _to_unix_seconds(start)
        to_ts = _to_unix_seconds(end) + 86399  # Ä‘áº¿n cuá»‘i ngÃ y end

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
            logger.warning("DNSE get_ohlc lá»—i: %s", exc)
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
            logger.info("DNSE history: %s rows, symbol=%s, %sâ†’%s", len(df), sym, start, end)
        return df

    # ------------------------------------------------------------------
    # intraday  (há»— trá»£ tape lá»‹ch sá»­ theo ngÃ y)
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
        Láº¥y dá»¯ liá»‡u lá»‹ch sá»­ khá»›p lá»‡nh (tape) tá»« DNSE LightSpeed OpenAPI.

        Há»— trá»£ cáº£ tape phiÃªn hiá»‡n táº¡i láº«n lá»‹ch sá»­ theo ngÃ y.

        Tham sá»‘:
            symbol (str): MÃ£ CK. Máº·c Ä‘á»‹nh lÃ  symbol khá»Ÿi táº¡o.
            date (str): NgÃ y cá»¥ thá»ƒ 'YYYY-MM-DD'. Láº¥y toÃ n bá»™ tape 1 ngÃ y.
            start (str): NgÃ y báº¯t Ä‘áº§u 'YYYY-MM-DD' cho khoáº£ng ngÃ y.
            end (str): NgÃ y káº¿t thÃºc 'YYYY-MM-DD' cho khoáº£ng ngÃ y.
                       Máº·c Ä‘á»‹nh lÃ  hÃ´m nay náº¿u start Ä‘Æ°á»£c cung cáº¥p.
            page_size (int): Sá»‘ lá»‡nh tá»‘i Ä‘a má»—i request API.
                             Máº·c Ä‘á»‹nh 10 000 khi cÃ³ date/start, 100 cho phiÃªn hiá»‡n táº¡i.
            get_all (bool): Tá»± Ä‘á»™ng phÃ¢n trang qua nextPageToken Ä‘á»ƒ láº¥y toÃ n bá»™ dá»¯ liá»‡u.
                            Máº·c Ä‘á»‹nh False.
            order (str): Thá»© tá»± sáº¯p xáº¿p 'asc' (cÅ©â†’má»›i) hoáº·c 'desc' (má»›iâ†’cÅ©).
                         Máº·c Ä‘á»‹nh 'asc'.
            show_log (bool): Ghi log. Máº·c Ä‘á»‹nh káº¿ thá»«a tá»« __init__.

        Tráº£ vá»:
            pd.DataFrame vá»›i cá»™t: time, price, volume, side

        VÃ­ dá»¥:
            >>> q = DNSEQuote("ACB", api_key="...", api_secret="...")
            # Tape phiÃªn hiá»‡n táº¡i (100 lá»‡nh gáº§n nháº¥t)
            >>> df = q.intraday()
            # ToÃ n bá»™ tape ngÃ y 2026-05-15
            >>> df = q.intraday(date="2026-05-15", get_all=True)
            # Tape tá»« 2026-05-12 Ä‘áº¿n 2026-05-16
            >>> df = q.intraday(start="2026-05-12", end="2026-05-16", get_all=True)
        """
        sym = (symbol or self.symbol).upper()
        _show = show_log if show_log is not None else self.show_log

        # --- Resolve date range â†’ Unix timestamps (VN timezone UTC+7) ---
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

        # --- Auto page_size (DNSE limit: 1â€“1000) ---
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
            except Exception as exc:
                # Failover cho lá»—i máº¡ng/auth; 404 empty (live trades chÆ°a á»•n Ä‘á»‹nh)
                # váº«n tráº£ empty best-effort Ä‘á»ƒ khÃ´ng fail cá»©ng.
                try:
                    _raise_for_failover(exc, "get_trades")
                except ConnectionError:
                    if not all_records:
                        raise
                logger.warning("DNSE get_trades lá»—i: %s", exc)
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
        Tráº£ vá» thÃ´ng tin security definition tá»« DNSE (dÃ¹ng thay tháº¿ price_depth cÆ¡ báº£n).

        Tham sá»‘:
            symbol (str, tÃ¹y chá»n): MÃ£ CK.

        Tráº£ vá»:
            pd.DataFrame vá»›i thÃ´ng tin Ä‘á»‹nh nghÄ©a chá»©ng khoÃ¡n.

        Raises:
            Lá»—i váº­n chuyá»ƒn/HTTP Ä‘Æ°á»£c **nÃ©m nguyÃªn váº¹n** â€” trÆ°á»›c Ä‘Ã¢y hÃ m báº¯t
            ``Exception`` rá»“i tráº£ ``DataFrame()``, biáº¿n "DNSE khÃ´ng tráº£ lá»i"
            thÃ nh "hÃ´m nay khÃ´ng cÃ³ giao dá»‹ch". NgÆ°á»i dÃ¹ng Ä‘á»c ``len(df) == 0``
            sáº½ káº¿t luáº­n sai nguyÃªn nhÃ¢n.
            EmptyProviderResult: provider tráº£ vá» rá»—ng. ÄÃ¢y lÃ  trÆ°á»ng há»£p
            "khÃ´ng pháº£i lá»—i nhÆ°ng cÅ©ng khÃ´ng dÃ¹ng Ä‘Æ°á»£c", theo Ä‘Ãºng ranh giá»›i
            Ä‘Ã£ Ä‘á»‹nh nghÄ©a á»Ÿ `common/data.py:442`.
        """
        sym = (symbol or self.symbol).upper()
        # KhÃ´ng báº¯t lá»—i á»Ÿ Ä‘Ã¢y: `should_failover` cáº§n nhÃ¬n tháº¥y loáº¡i lá»—i Ä‘á»ƒ
        # quyáº¿t Ä‘á»‹nh cÃ³ xoay sang provider khÃ¡c hay khÃ´ng.
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
        Láº¥y giÃ¡ Ä‘Ã³ng cá»­a má»›i nháº¥t cho má»™t mÃ£ chá»©ng khoÃ¡n.

        Tham sá»‘:
            symbol (str, tÃ¹y chá»n): MÃ£ CK. Máº·c Ä‘á»‹nh lÃ  symbol khá»Ÿi táº¡o.

        Tráº£ vá»:
            pd.DataFrame vá»›i thÃ´ng tin giÃ¡ Ä‘Ã³ng cá»­a.
        """
        sym = (symbol or self.symbol).upper()
        try:
            _, body = self._market.get_close_price(symbol=sym)
        except Exception as exc:
            logger.warning("DNSE get_close_price lá»—i: %s", exc)
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
        Láº¥y giao dá»‹ch má»›i nháº¥t cho má»™t mÃ£ chá»©ng khoÃ¡n.

        Tham sá»‘:
            symbol (str, tÃ¹y chá»n): MÃ£ CK. Máº·c Ä‘á»‹nh lÃ  symbol khá»Ÿi táº¡o.

        Tráº£ vá»:
            pd.DataFrame vá»›i thÃ´ng tin giao dá»‹ch má»›i nháº¥t.
        """
        sym = (symbol or self.symbol).upper()
        try:
            _, body = self._market.get_latest_trade(symbol=sym)
        except Exception as exc:
            logger.warning("DNSE get_latest_trade lá»—i: %s", exc)
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
        Láº¥y danh sÃ¡ch ngÃ y giao dá»‹ch (working dates) tá»« DNSE.

        âš  **ÄÃ¢y lÃ  lá»i gá»i NETWORK THáº¬T** sang `GET /market/working-dates`.

        TrÆ°á»›c 2026-10-16 method nÃ y tráº£ DataFrame rá»—ng ngay láº­p tá»©c (0ms) vÃ¬
        táº§ng connector tráº£ vá» háº±ng cá»©ng â€” trÃ´ng nhÆ° "khÃ´ng cÃ³ ngÃ y giao dá»‹ch"
        trong khi chÆ°a tá»«ng há»i server. Nay nÃ³ gá»i tháº­t. Há»‡ quáº£ cáº§n biáº¿t:

        - TrÃªn **sandbox** (`sb-openapi.dnse.com.vn`) path `/market/*` tráº£ 404
          â‡’ rÆ¡i vÃ o `except` vÃ  tráº£ DataFrame rá»—ng kÃ¨m `logger.warning`.
        - VÃ¬ váº­y DataFrame rá»—ng á»Ÿ Ä‘Ã¢y **khÃ´ng chá»©ng minh** lÃ  khÃ´ng cÃ³ ngÃ y giao
          dá»‹ch. Muá»‘n biáº¿t cháº¯c thÃ¬ Ä‘á»c log, hoáº·c gá»i tháº³ng
          `DNSEClient.get_working_dates()`.

        Tráº£ vá»:
            pd.DataFrame **má»™t dÃ²ng cho má»—i ngÃ y giao dá»‹ch**, cá»™t ``workingDates``.
        """
        try:
            _, body = self._market.get_working_dates()
        except Exception as exc:
            logger.warning(
                "DNSE get_working_dates lá»—i (%s) â€” tráº£ rá»—ng. Rá»—ng KHÃ”NG cÃ³ nghÄ©a "
                "lÃ  khÃ´ng cÃ³ ngÃ y giao dá»‹ch; xem endpoint /market/working-dates.",
                exc,
            )
            return pd.DataFrame()

        if body is None:
            return pd.DataFrame()
        # Äi qua `normalize_payload` chá»© khÃ´ng `pd.json_normalize(body)` trá»±c tiáº¿p:
        # `json_normalize` trÃªn dict cÃ³ `workingDates` lÃ  list-of-scalar cho
        # DataFrame **Má»˜T dÃ²ng** vá»›i má»™t cell chá»©a cáº£ 257 ngÃ y â€” Ä‘Ãºng hÃ¬nh thá»©c
        # "thÃ nh cÃ´ng rá»—ng" mÃ  lÃ¡t B sinh ra Ä‘á»ƒ chá»¯a. `normalize_payload` dÃ¹ng
        # chung `_to_dataframe` cá»§a connector nÃªn tÃ¡ch Ä‘Ãºng má»™t dÃ²ng má»—i ngÃ y.
        return self._client.normalize_payload(body)

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
                # `history` tá»± cÃ³ default cho `start`; chá»‰ truyá»n khi caller
                # thá»±c sá»± chá»‰ Ä‘á»‹nh, Ä‘á»ƒ khÃ´ng ghi Ä‘Ã¨ default báº±ng None.
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
