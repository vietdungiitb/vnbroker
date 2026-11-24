"""Public facade for the CafeF reference/cross-check layer."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Union

import pandas as pd

from vnbroker.core.exceptions import ProviderBadRequestError

from .client import fetch_ohlc
from .const import EXCHANGES
from .parser import parse_records
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
