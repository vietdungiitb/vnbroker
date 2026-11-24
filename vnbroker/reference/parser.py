"""Parse canonical CafeF records into a reference frame and native explorer records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .const import PRICE_SCALE, VALUE_SCALE

REFERENCE_COLUMNS = [
    "time",
    # Legacy tier-1 aliases (kept so the 31 existing tests stay green).
    "open",
    "high",
    "low",
    "close",
    # Canonical P1 columns.
    "symbol",
    "open_raw",
    "high_raw",
    "low_raw",
    "close_raw",
    "close_adjusted",
    "volume",
    "value",
    "put_through_volume",
    "put_through_value",
    "source",
    "price_basis",
    "coverage",
    "fetched_at",
]

TZ = "Asia/Ho_Chi_Minh"


def parse_records(records: list[dict[str, Any]], symbol: str) -> pd.DataFrame:
    """Build the rich reference frame (distinct from the tier-1 6-column frame)."""
    rows: list[dict[str, Any]] = []
    for record in records:
        ts = pd.to_datetime(record["date"]).tz_localize(TZ)
        close_raw = float(record["close_raw"]) * PRICE_SCALE
        open_raw = float(record["open"]) * PRICE_SCALE
        high_raw = float(record["high"]) * PRICE_SCALE
        low_raw = float(record["low"]) * PRICE_SCALE
        rows.append(
            {
                "time": ts,
                "open": open_raw,
                "high": high_raw,
                "low": low_raw,
                "close": close_raw,
                "symbol": str(record.get("symbol") or "").upper(),
                "open_raw": open_raw,
                "high_raw": high_raw,
                "low_raw": low_raw,
                "close_raw": close_raw,
                "close_adjusted": float(record["close_adjusted"]) * PRICE_SCALE,
                "volume": int(record["volume"]),
                "value": float(record["value"]) * VALUE_SCALE,
                "put_through_volume": int(record["put_through_volume"] or 0),
                "put_through_value": float(record["put_through_value"] or 0) * VALUE_SCALE,
                "source": "cafef",
                "price_basis": "both",
                "coverage": "ok",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    frame = pd.DataFrame(rows, columns=REFERENCE_COLUMNS)
    if not frame.empty:
        frame = frame.sort_values("time").reset_index(drop=True)
    frame.attrs["symbol"] = symbol.upper()
    frame.attrs["source"] = "cafef"
    frame.attrs["data_origin"] = "cafef"
    frame.attrs["price_basis"] = "both"
    frame.attrs["coverage"] = "ok"
    return frame


def apply_basis(frame: pd.DataFrame, basis: str) -> pd.DataFrame:
    """Select canonical columns for ``raw``/``adjusted``/``both`` — one code path."""
    if basis not in ("raw", "adjusted", "both"):
        raise ValueError(f"Unsupported basis {basis!r}; expected raw/adjusted/both")
    result = frame.copy()
    if basis == "raw":
        result = result.drop(columns=["close_adjusted"], errors="ignore")
    elif basis == "adjusted":
        result = result.drop(
            columns=["open", "high", "low", "close", "open_raw", "high_raw", "low_raw", "close_raw"],
            errors="ignore",
        )
    result["price_basis"] = basis
    result.attrs.update(frame.attrs)
    result.attrs["price_basis"] = basis
    return result


def to_native_records(frame: pd.DataFrame, source: str) -> list[dict[str, Any]]:
    """Return ``t,o,h,l,c,v`` records matching each explorer's native pipeline.

    KBS renames ``t`` via ``_OHLC_MAP`` and parses it with ``pd.to_datetime``;
    VCI's ``ohlc_to_df`` calls ``.astype(int)`` on ``time`` (epoch seconds), so
    an ISO string would break it (lesson from audit O-1).
    """
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        day = pd.Timestamp(row["time"]).date()
        timestamp: int | str
        if source.upper() == "VCI":
            timestamp = int(
                datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()
            )
        else:
            timestamp = day.strftime("%Y-%m-%d") + " 07:00"
        records.append(
            {
                "t": timestamp,
                "o": row["open"],
                "h": row["high"],
                "l": row["low"],
                "c": row["close_raw"],
                "v": row["volume"],
            }
        )
    return records
