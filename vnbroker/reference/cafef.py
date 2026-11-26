"""Public facade for the CafeF reference/cross-check layer."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Union

import pandas as pd

from vnbroker.core.exceptions import ProviderBadRequestError

from .client import bulk_year as fetch_bulk_year
from .client import fetch_ohlc
from .const import EXCHANGES
from .parser import REFERENCE_COLUMNS, apply_basis, parse_records
from .reconcile import ReconcileReport, reconcile

logger = logging.getLogger(__name__)


class CafefReference:
    """Read-only reference source: raw + adjusted OHLC and reconciliation.

    This class is deliberately NOT a tier-1 provider: it is never registered
    with ``ProviderRegistry`` and never joins the AUTO failover pool.
    """

    def __init__(self, exchange: str = "HOSE", show_log: bool = False) -> None:
        if exchange not in EXCHANGES:
            raise ValueError(f"Unsupported exchange {exchange!r}; expected one of {EXCHANGES}")
        self.exchange = exchange
        self.show_log = show_log
        self.source = "cafef"

    def history(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1D",
        to_df: bool = True,
    ) -> Union[pd.DataFrame, str]:
        """Return a reference frame with both raw and adjusted close.

        Args:
            symbol: Stock symbol, e.g. ``TPB``.
            start: ISO date ``YYYY-MM-DD``. Defaults to ``2018-01-01``.
            end: ISO date ``YYYY-MM-DD``. Defaults to today.
            interval: Only ``1D`` is served by CafeF's public API.
            to_df: False returns JSON records instead of a DataFrame.
        """
        if interval != "1D":
            raise ProviderBadRequestError(
                "CafeF reference chỉ phục vụ khung daily (1D); "
                "dùng KBS/VCI cho intraday.",
                http_status=400,
            )
        resolved_start = start or "2018-01-01"
        resolved_end = end or datetime.now().strftime("%Y-%m-%d")

        records = fetch_ohlc(
            symbol.upper(),
            resolved_start,
            resolved_end,
            exchange=self.exchange,
            show_log=self.show_log,
        )
        if not to_df:
            return json.dumps(records, ensure_ascii=False, default=str)
        return parse_records(records, symbol)

    def daily_bars(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        exchange: str | None = None,
        basis: str = "both",
    ) -> pd.DataFrame:
        """Canonical daily frame for one symbol (SSOT surface for vninvest).

        Default ``start=2011-01-01`` (earliest CafeF dataset year) is paired with
        explicit ``coverage`` metadata. For full-market backfill use ``bulk_year``
        instead of ``symbol='ALL'``.

        An empty response is classified: ``coverage='missing'`` when the symbol is
        absent from the ALL export for that year (e.g. TPB 2011), otherwise
        ``'no_trading_days'`` — never a silent "no trading day" frame.
        """
        if exchange and exchange != self.exchange:
            self.exchange = exchange
        resolved_start = start or "2011-01-01"
        resolved_end = end or datetime.now().strftime("%Y-%m-%d")
        frame = self.history(symbol, resolved_start, resolved_end)
        if isinstance(frame, str):
            raise TypeError("daily_bars needs a DataFrame reference frame")
        if frame.empty:
            coverage = self._classify_coverage(symbol, resolved_start)
            frame["coverage"] = pd.Series(dtype=str)
            frame.attrs["coverage"] = coverage
            frame.attrs["price_basis"] = basis
            return frame
        return apply_basis(frame, basis)

    def _classify_coverage(self, symbol: str, start: str) -> str:
        """Distinguish 'symbol absent from CafeF' from 'no bars in this range'."""
        try:
            year = int(str(start)[:4])
            records = fetch_bulk_year(self.exchange, year, show_log=self.show_log)
            if any(str(rec.get("symbol", "")).upper() == symbol.upper() for rec in records):
                return "no_trading_days"
        except Exception:  # network/parse failure -> report missing, never silent
            return "missing"
        return "missing"

    def bulk_year(
        self, exchange: str, year: int, *, end_date=None, use_cache: bool = True
    ) -> pd.DataFrame:
        """One XLSX ALL request per exchange/year; frame includes ``symbol``."""
        records = fetch_bulk_year(
            exchange, year, show_log=self.show_log,
            end_date=end_date, use_cache=use_cache,
        )
        if not records:
            return pd.DataFrame(columns=REFERENCE_COLUMNS)
        return parse_records(records, "ALL")

    def reconcile(
        self,
        frame: pd.DataFrame,
        symbol: str = "",
        start: str | None = None,
        end: str | None = None,
        tolerance: float = 0.005,
    ) -> ReconcileReport:
        """Compare an existing provider frame with CafeF adjusted prices."""
        frame_symbol = getattr(frame, "name", None)
        resolved_symbol = symbol or frame_symbol
        if not resolved_symbol:
            raise ValueError("reconcile needs an explicit symbol (or frame.name)")
        if symbol and frame_symbol and str(frame_symbol).upper() != str(symbol).upper():
            raise ValueError(
                f"symbol mismatch: frame.name={frame_symbol!r}, symbol={symbol!r}"
            )
        resolved_start = start or "2018-01-01"
        resolved_end = end or datetime.now().strftime("%Y-%m-%d")
        cafef_frame = self.history(resolved_symbol, resolved_start, resolved_end)
        if isinstance(cafef_frame, str):
            raise TypeError("reconcile needs a DataFrame reference frame")
        return reconcile(frame, cafef_frame, symbol=symbol, tolerance=tolerance)
