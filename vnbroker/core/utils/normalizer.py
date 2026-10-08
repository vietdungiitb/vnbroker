"""Centralized normalization for all provider results.

This module provides a single point of truth for normalizing DataFrames
returned by any provider, ensuring consistent schema across failover events.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytz


def _canonical_tz() -> Any:
    """Timezone chuẩn của thị trường Việt Nam (giờ giao dịch)."""
    return pytz.timezone("Asia/Ho_Chi_Minh")


def _to_canonical_tz(series: pd.Series) -> pd.Series:
    """Chuẩn hoá cột ``time`` thành tz-aware Asia/Ho_Chi_Minh."""
    if getattr(series.dt, "tz", None) is None:
        return series.dt.tz_localize(_canonical_tz())
    return series


def _parse_boundary(value: Any, *, inclusive_end: bool) -> pd.Timestamp | None:
    """Parse ngày biên của lời gọi. Trả None nếu thiếu/không parse được."""
    if value is None or value == "":
        return None
    try:
        ts = pd.to_datetime(value)
    except (ValueError, TypeError):
        return None
    if pd.isna(ts):
        return None
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.tz_localize(_canonical_tz())
    if inclusive_end and ts.hour == 0 and ts.minute == 0 and ts.second == 0:
        ts = ts + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return ts


class Normalizer:
    """Centralized normalization for all provider results."""

    @staticmethod
    def normalize_history(result: Any, start: Any = None, end: Any = None) -> Any:
        """Normalize history result (DataFrame or list[DataFrame])."""
        if isinstance(result, list):
            return [Normalizer._normalize_frame(f, start, end) for f in result]
        return Normalizer._normalize_frame(result, start, end)

    @staticmethod
    def _normalize_frame(df: pd.DataFrame, start: Any, end: Any) -> pd.DataFrame:
        """Normalize a single DataFrame: tz-aware, boundary filter, sort."""
        if not isinstance(df, pd.DataFrame) or "time" not in df.columns:
            return df

        # Copy to avoid mutation
        df = df.copy()

        # Convert time to Asia/Ho_Chi_Minh (tz-aware)
        df["time"] = _to_canonical_tz(pd.to_datetime(df["time"], errors="coerce"))
        # Drop rows with unparseable timestamps
        df = df[df["time"].notna()]

        # Filter by start/end boundaries
        lo = _parse_boundary(start, inclusive_end=False)
        if lo is not None:
            df = df[df["time"] >= lo]

        hi = _parse_boundary(end, inclusive_end=True)
        if hi is not None:
            df = df[df["time"] <= hi]

        # Sort by time and reset index
        return df.sort_values("time").reset_index(drop=True)
