"""Binance public market-data connector (spot, no auth).

Endpoints (Binance Spot API):
- GET /api/v3/klines → OHLCV bars (used by both history and intraday)
- GET /api/v3/ticker/24hr → 24h ticker snapshot (reserved for future use)

Prices are quoted in USDT by default and returned raw (no FX conversion).
``df.attrs["price_unit"]`` is stamped ``"USDT"`` so downstream code never
confuses crypto prices with VND equities.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import logging

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com"
_KLINES_PATH = "/api/v3/klines"

_INTERVAL_MAP: Dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1H": "1h",
    "1h": "1h",
    "1D": "1d",
    "1d": "1d",
    "1W": "1w",
    "1w": "1w",
    "1M": "1M",
}

_KNOWN_QUOTES = ("USDT", "USDC", "BTC", "ETH", "BNB", "TRY", "EUR")

_STANDARD_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


def normalize_symbol(symbol: str, default_quote: str = "USDT") -> str:
    """Normalize a crypto symbol to Binance spot format (e.g. BTC → BTCUSDT)."""
    sym = symbol.strip().upper().replace("/", "").replace("-", "").replace(" ", "")
    if not sym:
        raise ValueError("Crypto symbol must not be empty.")
    for quote in _KNOWN_QUOTES:
        if sym.endswith(quote) and len(sym) > len(quote):
            return sym
    return f"{sym}{default_quote}"


def normalize_interval(interval: str) -> str:
    """Map a vnbroker interval to a Binance kline interval."""
    key = interval.strip()
    mapped = _INTERVAL_MAP.get(key)
    if mapped is None:
        raise ValueError(
            f"Unsupported crypto interval: {interval!r}. "
            f"Choose from: {', '.join(sorted(_INTERVAL_MAP))}."
        )
    return mapped


def _to_ms(date_str: str, end_of_day: bool = False) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return int(dt.timestamp() * 1000)


def _klines_to_df(rows: List[List[Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=_STANDARD_COLUMNS)
    df = pd.DataFrame(rows)
    df = df.iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "volume"]
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True).dt.tz_localize(None)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[_STANDARD_COLUMNS].reset_index(drop=True)


class BinanceClient:
    """Public Binance spot market-data client (no API key needed)."""

    provider_name = "BINANCE"

    def __init__(
        self,
        symbol: str = "BTC",
        base_url: str = BASE_URL,
        timeout_seconds: float = 30.0,
        show_log: bool = False,
    ) -> None:
        self.symbol = normalize_symbol(symbol)
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.show_log = show_log

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _get_klines(self, params: Dict[str, Any]) -> List[List[Any]]:
        resp = requests.get(
            f"{self.base_url}{_KLINES_PATH}",
            params=params,
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        body = resp.json()
        if not isinstance(body, list):
            raise ValueError(f"Unexpected Binance klines response: {body!r}")
        return cast(List[List[Any]], body)

    def history(
        self,
        symbol: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = "1D",
        limit: int = 500,
    ) -> pd.DataFrame:
        """Daily (or coarser/finer) OHLCV bars for a crypto symbol.

        Args:
            symbol: e.g. ``"BTC"`` or ``"BTCUSDT"``. Defaults to init symbol.
            start/end: ``"YYYY-MM-DD"`` bounds (UTC). ``end`` defaults to now.
            interval: one of ``1m,5m,15m,30m,1H,1D,1W,1M``.
            limit: max bars per request (Binance caps at 1000).

        Returns:
            DataFrame ``[time, open, high, low, close, volume]`` priced in
            USDT (``df.attrs["price_unit"] == "USDT"``).
        """
        sym = normalize_symbol(symbol or self.symbol)
        bin_interval = normalize_interval(interval)
        params: Dict[str, Any] = {
            "symbol": sym,
            "interval": bin_interval,
            "limit": max(1, min(int(limit), 1000)),
        }
        if start:
            params["startTime"] = _to_ms(start)
        if end:
            params["endTime"] = _to_ms(end, end_of_day=True)

        rows = self._get_klines(params)
        df = _klines_to_df(rows)
        df.attrs["symbol"] = sym
        df.attrs["source"] = self.provider_name
        df.attrs["interval"] = interval
        df.attrs["price_unit"] = "USDT"
        if self.show_log:
            logger.info("Binance history: %s rows, symbol=%s", len(df), sym)
        return df

    def intraday(
        self,
        symbol: Optional[str] = None,
        interval: str = "1m",
        limit: int = 100,
    ) -> pd.DataFrame:
        """Most recent kline bars (crypto trades 24/7 — no session split).

        Defaults to 1-minute bars; same schema/units as :meth:`history`.
        """
        return self.history(
            symbol=symbol, start=None, end=None, interval=interval, limit=limit
        )
