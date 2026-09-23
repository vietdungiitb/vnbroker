"""
vnbroker/explorer/ssi/quote.py

SSI Quote provider - OHLC history native via broker-lane SSIMarketService,
normalized to the KBS/VCI schema ([time, open, high, low, close, volume]).

SSI REST has no tick intraday / price-depth endpoints: those raise
NotImplementedError with guidance (fallback lanes or broker stream).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from vnbroker.broker.ssi.market import SSIMarketService
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.lookback import get_start_date_from_lookback
from vnbroker.explorer.ssi._auth import get_shared_session, resolve_credentials

logger = get_logger(__name__)

_INTERVAL_MAP: Dict[str, str] = {
    "1D": "1d",
    "1d": "1d",
    "d": "1d",
    "day": "1d",
    "daily": "1d",
    "1W": "1w",
    "1w": "1w",
    "w": "1w",
    "week": "1w",
    "weekly": "1w",
    "1M": "1M",
    "1H": "1h",
    "1h": "1h",
    "h": "1h",
    "hour": "1h",
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
}

_HISTORY_COLUMNS = ["time", "open", "high", "low", "close", "volume"]
_PRICE_COLUMNS = ["open", "high", "low", "close"]
_PAGE_SIZE = 1000
_MAX_PAGES = 10
_DEFAULT_LOOKBACK_DAYS = 365

_UNSUPPORTED_MESSAGE = (
    "SSI REST không hỗ trợ {method}; "
    "dùng source='KBS'/'VCI' hoặc vn.broker(provider='ssi').stream"
)


def _validate_date(value: str, name: str) -> str:
    """Strict YYYY-MM-DD validation in the explorer (never leak broker errors)."""
    text = (value or "").strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"{name} phải định dạng YYYY-MM-DD. Nhận: {value!r}"
        ) from None
    return text


class SSIQuote:
    """
    SSI Quote provider (market-data lane).

    Args:
        symbol: Stock symbol (e.g. 'ACB').
        api_key: SSI consumerID (falls back to ``VNBROKER_BROKER_SSI_API_KEY``).
        api_secret: SSI consumerSecret (falls back to ``VNBROKER_BROKER_SSI_API_SECRET``).
        show_log: Show log messages.
        _service: Test hook — inject an ``SSIMarketService`` double (no network).

    Example:
        >>> q = SSIQuote("ACB", api_key="...", api_secret="...")
        >>> df = q.history(start="2024-01-01", end="2024-12-31")
    """

    def __init__(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        _service: Optional[SSIMarketService] = None,
        **kwargs: Any,
    ) -> None:
        self.symbol = (symbol or "").upper()
        self.show_log = show_log
        if not show_log:
            logger.setLevel("CRITICAL")
        # Fail fast on missing credentials (offline — no network here).
        key, secret = resolve_credentials(api_key, api_secret)
        self._api_key = key
        self._api_secret = secret
        self._service = _service

    def _market(self) -> SSIMarketService:
        """Lazy service construction (first network use authenticates)."""
        if self._service is None:
            self._service = get_shared_session(
                self._api_key, self._api_secret
            ).market_service()
        return self._service

    def _resolve_timeframe(self, interval: str) -> str:
        """Map standard interval to SSI timeframe (pre-validated, no leakage)."""
        token = (interval or "").strip()
        if token == "30m":
            raise NotImplementedError(
                "SSI không hỗ trợ interval 30m; dùng 15m hoặc source KBS/VCI."
            )
        mapped = _INTERVAL_MAP.get(token)
        if mapped is None:
            raise ValueError(
                f"interval không hỗ trợ: {interval!r}. "
                "Dùng 1m/3m/5m/15m/30m/1H/1D/1W/1M."
            )
        return mapped

    def history(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = "1D",
        to_df: bool = True,
        count_back: Optional[int] = None,
        floating: int = 2,
        length: Union[str, int, None] = None,
        get_all: bool = False,
        **kwargs: Any,
    ) -> Union[pd.DataFrame, str]:
        """
        Fetch OHLCV history normalized to ``[time, open, high, low, close, volume]``.

        Args:
            start: Start date ``YYYY-MM-DD`` (default: end − 365 days, or ``length``).
            end: End date ``YYYY-MM-DD`` (default: today).
            interval: Standard interval (``30m`` raises ``NotImplementedError``).
            to_df: ``False`` returns a JSON string of records.
            count_back: Keep only the last N rows.
            floating: Price rounding decimals.
            length: Lookback (e.g. ``'3M'``, ``150``) used when ``start`` is None.
            get_all: Loop pages until the hard stop rule; keeps the ``value`` column.

        Returns:
            DataFrame (or JSON string) with VND prices and ``attrs`` metadata.
        """
        timeframe = self._resolve_timeframe(interval)
        end_norm = _validate_date(end, "end") if end else date.today().strftime("%Y-%m-%d")
        if start:
            start_norm = _validate_date(start, "start")
        elif length is not None:
            start_norm = get_start_date_from_lookback(
                lookback_length=length, end_date=end_norm
            )
        else:
            start_norm = (
                datetime.strptime(end_norm, "%Y-%m-%d").date()
                - timedelta(days=_DEFAULT_LOOKBACK_DAYS)
            ).strftime("%Y-%m-%d")
        if start_norm > end_norm:
            raise ValueError(
                f"start ({start_norm}) phải <= end ({end_norm})."
            )
        from_ssi = start_norm.replace("-", "/")
        to_ssi = end_norm.replace("-", "/")

        service = self._market()
        frames: List[pd.DataFrame] = []
        page = 1
        while True:
            chunk = service.get_ohlc(
                symbol=self.symbol,
                timeframe=timeframe,
                from_date=from_ssi,
                to_date=to_ssi,
                page=page,
                size=_PAGE_SIZE,
            )
            if not isinstance(chunk, pd.DataFrame):
                chunk = pd.DataFrame(chunk)
            if not chunk.empty:
                frames.append(chunk)
            rows = len(chunk)
            if not get_all:
                break
            # Hard stop rule: empty page, short page, or safety cap.
            if chunk.empty or rows < _PAGE_SIZE or page >= _MAX_PAGES:
                break
            page += 1

        if not frames:
            empty = pd.DataFrame(columns=_HISTORY_COLUMNS)
            empty.attrs.update(
                {
                    "symbol": self.symbol,
                    "source": "SSI",
                    "source_used": "SSI",
                    "interval": interval,
                    "start": start_norm,
                    "end": end_norm,
                }
            )
            return empty

        raw = pd.concat(frames, ignore_index=True)
        out = pd.DataFrame(
            {
                "time": pd.to_datetime(raw["trading_date"], errors="coerce"),
                "open": pd.to_numeric(raw["open"], errors="coerce"),
                "high": pd.to_numeric(raw["high"], errors="coerce"),
                "low": pd.to_numeric(raw["low"], errors="coerce"),
                "close": pd.to_numeric(raw["close"], errors="coerce"),
                "volume": pd.to_numeric(raw["volume"], errors="coerce").astype("Int64"),
            }
        )
        if get_all and "value" in raw.columns:
            out["value"] = pd.to_numeric(raw["value"], errors="coerce").astype("float64")
        out = out.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
        for col in _PRICE_COLUMNS:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(int(floating))
        if count_back is not None:
            out = out.tail(int(count_back)).reset_index(drop=True)
        out.attrs.update(
            {
                "symbol": self.symbol,
                "source": "SSI",
                "source_used": "SSI",
                "interval": interval,
                "start": start_norm,
                "end": end_norm,
            }
        )
        if not to_df:
            return json.dumps(out.to_dict("records"), default=str)
        return out

    def intraday(self, **kwargs: Any) -> pd.DataFrame:
        """Tick data is not available via SSI REST (use KBS/VCI or broker stream)."""
        raise NotImplementedError(_UNSUPPORTED_MESSAGE.format(method="intraday"))

    def price_depth(self, **kwargs: Any) -> pd.DataFrame:
        """Order-book depth is not available via SSI REST (use VCI or broker stream)."""
        raise NotImplementedError(_UNSUPPORTED_MESSAGE.format(method="price_depth"))


ProviderRegistry.register("quote", "ssi", SSIQuote)
